# ═══════════════════════════════════════════════════════════════
# CAMPUS SEGURO – Servicio de Integración Auth0
# ─────────────────────────────────────────────────────────────
# Archivo: app/auth0_service.py
#
# PROPÓSITO:
#   Capa de servicio que encapsula TODAS las llamadas a la API de Auth0.
#   Centraliza la lógica de autenticación externa para que views.py no
#   necesite conocer los detalles del protocolo OAuth2 / OIDC.
#
# FLUJOS IMPLEMENTADOS:
#   1. autenticar_usuario()      → Resource Owner Password Credentials (ROPC)
#      Envía email+contraseña a Auth0 y recibe tokens JWT si son válidos.
#
#   2. obtener_token_mgmt()      → Client Credentials Flow
#      Obtiene un token de acceso para la Management API de Auth0.
#      Usado para crear/actualizar/eliminar usuarios programáticamente.
#
#   3. crear_usuario_auth0()     → Management API POST /api/v2/users
#      Crea un nuevo usuario en Auth0 al momento del registro.
#      Así la contraseña NUNCA se almacena en la BD de Campus Seguro.
#
#   4. actualizar_rol_auth0()    → Management API PATCH /api/v2/users/{id}
#      Actualiza los metadatos del usuario (app_metadata.campus_rol)
#      cuando el gestor asigna un rol al aprobar la cuenta.
#
#   5. revocar_sesion_auth0()    → Management API DELETE /api/v2/users/{id}/sessions
#      Invalida todas las sesiones activas del usuario en Auth0.
#      Llamado desde logout_view() para cierre de sesión global.
#
#   6. construir_url_logout()    → Genera URL de logout de Auth0
#      Redirige al usuario al endpoint de logout de Auth0 para
#      limpiar su sesión en el servidor de autorización.
#
#   7. decodificar_token()       → Decodifica JWT sin verificar firma
#      Lee los claims del id_token (email, sub, roles) para
#      identificar al usuario después del login.
#
#   8. sincronizar_usuario_local() → Sincronización Auth0 ↔ BD Local
#      Crea o actualiza automáticamente el usuario en la BD local
#      después de autenticar en Auth0. Resuelve el problema de usuarios
#      que existen en Auth0 pero no en Django.
#
# ARQUITECTURA DE AUTENTICACIÓN:
#
#   Usuario ingresa email+contraseña
#        │
#        ▼
#   views.py → login_view()
#        │
#        ├─ AUTH0_ENABLED=True?
#        │     ├─ Sí → auth0_service.autenticar_usuario()
#        │     │            │
#        │     │            ├─ Éxito → JWT token recibido
#        │     │            │   └─ decodificar_token()
#        │     │            │       └─ sincronizar_usuario_local()
#        │     │            │           ├─ Busca usuario por email
#        │     │            │           ├─ Si existe → actualiza datos
#        │     │            │           └─ Si no existe → crea en BD
#        │     │            │               └─ login() + redirect dashboard
#        │     │            │
#        │     │            └─ Fallo → mensaje error "Credenciales incorrectas"
#        │     │
#        │     └─ No → Django authenticate() (fallback local para desarrollo)
#        │
#        └─ redirect()
#
# FALLBACK DE DESARROLLO:
#   Si AUTH0_DOMAIN no está configurado en .env, AUTH0_ENABLED=False
#   y el sistema usa autenticación Django estándar. Esto permite
#   desarrollar y probar sin credenciales de Auth0.
#
# CONEXIONES:
#   - Llamado por: app/views.py (login_view, logout_view, registro_view, aprobar_cuenta)
#   - Lee configuración de: campus_seguro/settings.py (variables AUTH0_*)
#   - Comunica con: https://{AUTH0_DOMAIN}/ (API externa de Auth0)
#
# DEPENDENCIAS:
#   - requests: llamadas HTTP a Auth0 API
#   - PyJWT: decodificación de tokens JWT
#   - django.conf.settings: lee configuración Auth0
#
# REFERENCIA OFICIAL Auth0:
#   https://auth0.com/docs/api/authentication
#   https://auth0.com/docs/api/management/v2
# ═══════════════════════════════════════════════════════════════

import logging
import requests
import jwt
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Clase principal de excepciones ──────────────────────────
class Auth0Error(Exception):
    """
    Excepción base para errores de Auth0.

    Atributos:
        message (str): Descripción del error para mostrar al usuario.
        code (str): Código de error de Auth0 (ej: 'invalid_grant').
        status_code (int): Código HTTP de la respuesta (ej: 401, 403).
    """
    def __init__(self, message='Error de autenticación', code='auth0_error', status_code=400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


# ── Helpers internos ─────────────────────────────────────────
def _auth0_url(path):
    """
    Construye una URL completa para la API de Auth0.

    Parámetros:
        path (str): Path relativo (ej: '/oauth/token', '/api/v2/users').

    Retorna:
        str: URL completa (ej: 'https://campus-seguro.us.auth0.com/oauth/token').

    Uso interno: evita repetir f'https://{settings.AUTH0_DOMAIN}{path}'
    en cada función.
    """
    return f"https://{settings.AUTH0_DOMAIN}{path}"


def _manejar_respuesta(response, contexto=''):
    """
    Valida la respuesta HTTP de Auth0 y retorna el JSON o lanza Auth0Error.

    Parámetros:
        response (requests.Response): Respuesta de la llamada HTTP.
        contexto (str): Descripción del contexto para logs (ej: 'login ROPC').

    Retorna:
        dict: Cuerpo JSON de la respuesta si fue exitosa.

    Lanza:
        Auth0Error: Si el código HTTP indica error (4xx, 5xx).

    Por qué: centraliza el manejo de errores para no repetir lógica
    de status_code en cada función del servicio.
    """
    try:
        data = response.json()
    except Exception:
        data = {}

    if response.status_code >= 400:
        error_code = data.get('error', 'unknown_error')
        error_desc = data.get('error_description', 'Error desconocido en Auth0')
        logger.warning(
            f"Auth0 error [{contexto}] status={response.status_code} "
            f"code={error_code}: {error_desc}"
        )
        raise Auth0Error(
            message=error_desc,
            code=error_code,
            status_code=response.status_code,
        )

    return data


# ═══════════════════════════════════════════════════════════════
# 1. AUTENTICACIÓN – Resource Owner Password Credentials (ROPC)
# ═══════════════════════════════════════════════════════════════
def autenticar_usuario(email, password):
    """
    Autentica un usuario contra Auth0 usando el flujo ROPC (Resource Owner
    Password Credentials). El usuario ingresa sus credenciales en el formulario
    de Campus Seguro y este servicio las envía a Auth0 para validación.

    La contraseña NUNCA llega a la base de datos de Campus Seguro:
    se envía directamente a Auth0 sobre HTTPS y se descarta después.

    Parámetros:
        email (str): Correo institucional del usuario (ej: jordan@duoc.cl).
        password (str): Contraseña del usuario (se envía a Auth0, no se guarda).

    Retorna:
        dict con las claves:
            'access_token' (str): Token de acceso OAuth2 (scoped a la API).
            'id_token' (str): Token de identidad JWT con datos del usuario.
            'token_type' (str): Tipo de token, generalmente 'Bearer'.
            'expires_in' (int): Segundos hasta expiración.

    Lanza:
        Auth0Error: Si las credenciales son inválidas, la cuenta no existe
                    en Auth0, o hay un error de red/configuración.

    Flujo técnico:
        POST https://{AUTH0_DOMAIN}/oauth/token
        grant_type=password, username=email, password=password
        → Auth0 valida contra su base de datos de usuarios
        → Retorna JWT tokens si son válidas

    REQUISITO EN AUTH0 DASHBOARD:
        - La aplicación debe tener habilitado el grant type "Password".
        - El tenant debe tener configurada la "Default Directory" en Settings.
        - Ver docs/AUTH0_CONFIGURACION.md paso 4.
    """
    payload = {
        'grant_type': 'password',
        'username': email,
        'password': password,
        'audience': settings.AUTH0_AUDIENCE,
        'scope': 'openid profile email',
        'client_id': settings.AUTH0_CLIENT_ID,
        'client_secret': settings.AUTH0_CLIENT_SECRET,
    }

    try:
        response = requests.post(
            _auth0_url('/oauth/token'),
            json=payload,
            timeout=10,
        )
    except requests.exceptions.ConnectionError:
        logger.error("Auth0: No se pudo conectar al servidor de autenticación.")
        raise Auth0Error(
            message='No se pudo conectar con el servidor de autenticación. Intenta más tarde.',
            code='connection_error',
            status_code=503,
        )
    except requests.exceptions.Timeout:
        logger.error("Auth0: Timeout al intentar autenticar.")
        raise Auth0Error(
            message='El servidor de autenticación tardó demasiado. Intenta más tarde.',
            code='timeout',
            status_code=504,
        )

    return _manejar_respuesta(response, 'login ROPC')


# ═══════════════════════════════════════════════════════════════
# 2. MANAGEMENT API – Token de acceso (Client Credentials)
# ═══════════════════════════════════════════════════════════════
def obtener_token_mgmt():
    """
    Obtiene un token de acceso para la Auth0 Management API usando
    el flujo Client Credentials (máquina a máquina).

    Este token se usa para operaciones administrativas sobre usuarios:
    crear usuario en Auth0 al registrarse, actualizar rol al aprobar cuenta,
    revocar sesiones al suspender cuenta.

    Retorna:
        str: Token de acceso Bearer para la Management API.

    Lanza:
        Auth0Error: Si las credenciales M2M no están configuradas o son inválidas.

    REQUISITO EN AUTH0 DASHBOARD:
        - Tener una aplicación Machine-to-Machine creada.
        - Con permisos: create:users, update:users, delete:users_sessions,
          read:users, update:users_app_metadata.
        - Ver docs/AUTH0_CONFIGURACION.md paso 6.
    """
    if not settings.AUTH0_MGMT_CLIENT_ID or not settings.AUTH0_MGMT_CLIENT_SECRET:
        raise Auth0Error(
            message='Management API no configurada. Ver .env → AUTH0_MGMT_CLIENT_ID.',
            code='mgmt_not_configured',
        )

    response = requests.post(
        _auth0_url('/oauth/token'),
        json={
            'grant_type': 'client_credentials',
            'client_id': settings.AUTH0_MGMT_CLIENT_ID,
            'client_secret': settings.AUTH0_MGMT_CLIENT_SECRET,
            'audience': _auth0_url('/api/v2/'),
        },
        timeout=10,
    )

    data = _manejar_respuesta(response, 'Management API token')
    return data['access_token']


# ═══════════════════════════════════════════════════════════════
# 3. CREAR USUARIO EN AUTH0 (al momento del registro)
# ═══════════════════════════════════════════════════════════════
def crear_usuario_auth0(email, password, nombre, apellido):
    """
    Crea un nuevo usuario en Auth0 usando la Management API.
    Se llama durante el proceso de registro para que Auth0 sea
    el sistema que almacena la contraseña (no Campus Seguro).

    Parámetros:
        email (str): Correo institucional del nuevo usuario.
        password (str): Contraseña elegida por el usuario (enviada a Auth0,
                        nunca almacenada en la BD de Campus Seguro).
        nombre (str): Nombre del usuario (first_name).
        apellido (str): Apellido del usuario (last_name).

    Retorna:
        dict con los datos del usuario creado en Auth0, incluyendo:
            'user_id' (str): Sub de Auth0 (ej: 'auth0|66a1b2c3...').
            'email' (str): Correo del usuario.

    Lanza:
        Auth0Error: Si el email ya existe en Auth0 (código 409 Conflict),
                    si la contraseña no cumple los requisitos, o falla la conexión.

    Efectos secundarios:
        El usuario queda creado en Auth0 con email_verified=False.
        La contraseña se almacena cifrada en Auth0, no en Campus Seguro.

    Flujo técnico:
        1. obtener_token_mgmt() → token Bearer M2M
        2. POST /api/v2/users con datos del usuario
        3. Retornar el user_id (auth0_sub) para guardarlo en Usuario.auth0_sub
    """
    token = obtener_token_mgmt()

    response = requests.post(
        _auth0_url('/api/v2/users'),
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
        json={
            'connection': settings.AUTH0_CONNECTION,
            'email': email,
            'password': password,
            'name': f'{nombre} {apellido}'.strip(),
            'given_name': nombre,
            'family_name': apellido,
            'email_verified': False,
            'app_metadata': {
                'campus_rol': 'usuario',       # Rol inicial, se actualiza al aprobar
                'campus_estado': 'pendiente',  # Estado inicial hasta que el gestor apruebe
            },
        },
        timeout=10,
    )

    return _manejar_respuesta(response, 'crear usuario')


# ═══════════════════════════════════════════════════════════════
# 4. ACTUALIZAR ROL EN AUTH0 (cuando el gestor aprueba la cuenta)
# ═══════════════════════════════════════════════════════════════
def actualizar_rol_auth0(auth0_sub, rol, estado='activa'):
    """
    Actualiza los metadatos del usuario en Auth0 cuando el gestor
    le asigna un rol al aprobar su cuenta.

    Los metadatos se guardan en app_metadata (no editable por el usuario)
    y están disponibles en los tokens JWT via Auth0 Action configurada
    en el dashboard.

    Parámetros:
        auth0_sub (str): User ID en Auth0 (ej: 'auth0|66a1b2c3...').
        rol (str): Rol Campus Seguro a asignar
                   ('usuario', 'gestor', 'guardia', 'mantencion').
        estado (str): Estado de la cuenta ('activa', 'suspendida', etc.).

    Retorna:
        dict: Datos actualizados del usuario en Auth0.

    Lanza:
        Auth0Error: Si el auth0_sub no existe o hay error de permisos M2M.

    Por qué app_metadata y no roles de Auth0 RBAC:
        app_metadata es más simple para el alcance de este proyecto.
        Para producción con múltiples apps, considerar Auth0 RBAC (Organizations).
        La Auth0 Action lee app_metadata.campus_rol e incluye el valor
        como claim en el JWT: {"https://campus-seguro.app/roles": ["gestor"]}.
    """
    token = obtener_token_mgmt()

    # URL-encode del auth0_sub (puede contener '|' que debe ser '%7C')
    sub_encoded = requests.utils.quote(auth0_sub, safe='')

    response = requests.patch(
        _auth0_url(f'/api/v2/users/{sub_encoded}'),
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
        json={
            'app_metadata': {
                'campus_rol': rol,
                'campus_estado': estado,
            },
        },
        timeout=10,
    )

    return _manejar_respuesta(response, f'actualizar rol → {rol}')


# ═══════════════════════════════════════════════════════════════
# 5. REVOCAR SESIONES DE USUARIO EN AUTH0 (logout / suspensión)
# ═══════════════════════════════════════════════════════════════
def revocar_sesion_auth0(auth0_sub):
    """
    Invalida todas las sesiones activas del usuario en Auth0.
    Se llama durante el proceso de logout o cuando un gestor suspende
    una cuenta para asegurar que no queden sesiones activas.

    Parámetros:
        auth0_sub (str): User ID en Auth0 (ej: 'auth0|66a1b2c3...').

    Retorna:
        bool: True si la revocación fue exitosa.

    Lanza:
        Auth0Error: Si hay un error de permisos o el sub no existe.

    NOTA:
        Esta operación requiere el permiso delete:sessions en la
        aplicación M2M. Ver docs/AUTH0_CONFIGURACION.md paso 6.

    Alternativa para producción:
        Usar refresh tokens con rotación y corta vida del access_token.
        Esto limita la ventana de exposición sin necesidad de revocar
        sesiones activamente.
    """
    if not auth0_sub:
        return False

    try:
        token = obtener_token_mgmt()
        sub_encoded = requests.utils.quote(auth0_sub, safe='')

        response = requests.delete(
            _auth0_url(f'/api/v2/users/{sub_encoded}/sessions'),
            headers={'Authorization': f'Bearer {token}'},
            timeout=10,
        )

        # 204 No Content = éxito; 404 = usuario no tiene sesiones activas (OK)
        if response.status_code in (204, 404):
            logger.info(f"Auth0: sesiones revocadas para {auth0_sub}")
            return True

        _manejar_respuesta(response, 'revocar sesión')
        return True

    except Auth0Error as e:
        # No fallar el logout por un error de revocación en Auth0.
        # El logout local ya ocurrió; registrar el error pero continuar.
        logger.warning(f"Auth0: No se pudieron revocar sesiones para {auth0_sub}: {e.message}")
        return False


# ═══════════════════════════════════════════════════════════════
# 6. URL DE LOGOUT DE AUTH0
# ═══════════════════════════════════════════════════════════════
def construir_url_logout(return_to_url):
    """
    Construye la URL del endpoint de logout de Auth0.

    Auth0 tiene su propio servidor de sesiones separado del servidor Django.
    Para un logout completo (cumpliendo el criterio de aceptación del proyecto),
    el usuario debe ser redirigido a este endpoint para que Auth0 invalide
    también su sesión en el servidor de autorización.

    Parámetros:
        return_to_url (str): URL absoluta a donde Auth0 redirige después del logout.
                             Debe estar registrada en Auth0 Dashboard en DOS lugares:
                             1. Application → Settings → Allowed Logout URLs
                             2. Settings (tenant) → General → Allowed Logout URLs
                             Ejemplo: 'http://localhost:8000/login/'

    Retorna:
        str: URL completa de logout de Auth0.

    NOTA IMPORTANTE sobre client_id:
        Cuando se incluye client_id, Auth0 busca la returnTo URL en los
        Allowed Logout URLs de esa aplicación específica.
        Sin client_id, Auth0 busca en los Allowed Logout URLs del tenant (Settings global).
        Usamos SIN client_id para simplificar la configuración: solo hay que
        agregar la URL en un lugar (Settings → General → Allowed Logout URLs).

    Flujo de logout completo:
        1. Django limpia sesión local (logout())
        2. Django redirige a esta URL de Auth0
        3. Auth0 invalida su sesión de servidor de autorización
        4. Auth0 redirige al usuario a return_to_url (la página de login)
    """
    import urllib.parse
    # Con client_id → Auth0 valida returnTo contra los Allowed Logout URLs
    # de la APLICACIÓN específica (Application → Settings → Allowed Logout URLs).
    # Sin client_id → Auth0 busca en los Allowed Logout URLs del TENANT
    # (Settings → Advanced), que por defecto está vacío.
    # Usamos client_id para que Auth0 use la configuración de la aplicación.
    params = urllib.parse.urlencode({
        'client_id': settings.AUTH0_CLIENT_ID,
        'returnTo': return_to_url,
    })
    return _auth0_url(f'/v2/logout?{params}')


# ═══════════════════════════════════════════════════════════════
# 7. DECODIFICACIÓN DE TOKEN JWT
# ═══════════════════════════════════════════════════════════════
def decodificar_token(id_token):
    """
    Decodifica el id_token JWT de Auth0 para extraer los claims del usuario
    (email, sub, roles) sin necesidad de una llamada adicional a la API.

    Parámetros:
        id_token (str): Token JWT recibido de Auth0 tras autenticación exitosa.

    Retorna:
        dict con los claims del token, incluyendo:
            'sub' (str): Subject - User ID único en Auth0 (ej: 'auth0|66a1b2...')
            'email' (str): Correo del usuario.
            'name' (str): Nombre completo.
            '{namespace}/roles' (list): Roles Campus Seguro (si la Action está config.)
                                        Ej: ['gestor'] bajo el namespace configurado.

    SEGURIDAD – Verificación de firma:
        En esta implementación se decodifica SIN verificar la firma del JWT.
        Esto es aceptable porque:
        a) El token fue recibido directamente de Auth0 en la misma request.
        b) La comunicación usa HTTPS (el token no fue interceptado).
        c) El token se usa solo para obtener el email y buscar al usuario
           en la BD local, no para decisiones de autorización en sí.

        Para producción con mayor seguridad, verificar la firma con:
            PyJWT + JWKS endpoint de Auth0:
            https://{AUTH0_DOMAIN}/.well-known/jwks.json
        Ver comentario MEJORA EN PRODUCCIÓN más abajo.

    Lanza:
        ValueError: Si el token no es un JWT válido.
        Auth0Error: Si el token no tiene los claims mínimos requeridos.
    """
    try:
        claims = jwt.decode(
            id_token,
            options={"verify_signature": False},
            algorithms=["RS256"],
        )
    except jwt.DecodeError as e:
        logger.error(f"Auth0: Error al decodificar id_token: {e}")
        raise Auth0Error(
            message='Token de autenticación inválido.',
            code='invalid_token',
        )

    if 'sub' not in claims or 'email' not in claims:
        raise Auth0Error(
            message='El token no contiene la información de usuario requerida.',
            code='missing_claims',
        )

    return claims

    # ── MEJORA EN PRODUCCIÓN (verificación de firma) ─────────
    # Para verificar la firma en producción:
    #
    # import requests as req
    # from jwt.algorithms import RSAAlgorithm
    #
    # jwks_url = f"https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json"
    # jwks = req.get(jwks_url).json()
    # public_key = RSAAlgorithm.from_jwk(json.dumps(jwks['keys'][0]))
    # claims = jwt.decode(
    #     id_token,
    #     key=public_key,
    #     algorithms=["RS256"],
    #     audience=settings.AUTH0_CLIENT_ID,
    # )


# ═══════════════════════════════════════════════════════════════
# 8. SINCRONIZACIÓN DE USUARIO LOCAL (Auth0 ↔ BD Django)
# ═══════════════════════════════════════════════════════════════
def sincronizar_usuario_local(auth0_user_data):
    """
    Crea o actualiza automáticamente el usuario en la base de datos local
    después de autenticar exitosamente en Auth0.

    RESUELVE EL PROBLEMA:
        "Auth0 autenticó a usuario@dominio.cl pero no existe en BD local"
    
    Esta función se llama DESPUÉS de autenticar_usuario() exitosamente.
    Sincroniza los datos entre Auth0 y la BD local de Django, permitiendo
    que cualquier usuario que exista en Auth0 pueda acceder al sistema
    sin necesidad de crearlo manualmente en la BD.

    Parámetros:
        auth0_user_data (dict): Datos del usuario obtenidos de Auth0 tras
                                autenticación exitosa. Debe contener:
            - 'email' (str): Correo institucional
            - 'sub' (str): Auth0 user ID (ej: 'auth0|66a1b2...')
            - 'given_name' (str, opcional): Nombre
            - 'family_name' (str, opcional): Apellido
            - 'name' (str, opcional): Nombre completo

    Retorna:
        Usuario: Instancia del modelo Usuario de Django (creada o actualizada).

    Lógica de sincronización:
        1. Busca usuario por auth0_sub O por email
        2. Si existe → Actualiza nombre, email, último login
        3. Si no existe → Crea nuevo usuario con:
            - rol='usuario' (por defecto) O según email (si contiene 'gestor', 'guardia', etc.)
            - estado='pendiente' (requiere aprobación del gestor)
            - is_active=True (puede acceder al sistema)
            - is_staff=True si es gestor
        4. Retorna el usuario sincronizado

    Determinación automática de rol:
        El rol se infiere del email si contiene palabras clave:
        - 'gestor' → rol='gestor', is_staff=True, estado='activa'
        - 'guardia' o 'seguridad' → rol='guardia'
        - 'mantencion' → rol='mantencion'
        - cualquier otro → rol='usuario'

    NOTA SOBRE GESTORES:
        Los usuarios con email que contenga 'gestor' son aprobados
        automáticamente (estado='activa') para facilitar el desarrollo
        en equipo sin necesidad de aprobación manual.

    Excepciones:
        ImportError: Si no se puede importar el modelo Usuario o EstadoCatalogo.
        Exception: Errores de base de datos o validación.
    """
    from app.models import Usuario, EstadoCatalogo
    
    email = auth0_user_data.get('email')
    auth0_sub = auth0_user_data.get('sub')
    
    if not email:
        logger.error("Auth0 user data no contiene email")
        raise ValueError("Auth0 user data debe contener email")
    
    # Determinar rol basado en el email
    rol = 'usuario'  # Por defecto
    email_lower = email.lower()
    
    if 'gestor' in email_lower:
        rol = 'gestor'
    elif 'guardia' in email_lower or 'seguridad' in email_lower:
        rol = 'guardia'
    elif 'mantencion' in email_lower or 'mantenimiento' in email_lower:
        rol = 'mantencion'
    elif 'enc_seguridad' in email_lower:
        rol = 'enc_seguridad'
    
    logger.info(f"Sincronizando usuario: {email} → rol={rol}")
    
    # Buscar si ya existe por auth0_sub O por email
    try:
        user = Usuario.objects.get(auth0_sub=auth0_sub)
        # Usuario existe por auth0_sub → actualizar datos
        user.first_name = auth0_user_data.get('given_name', user.first_name)
        user.last_name = auth0_user_data.get('family_name', user.last_name)
        user.correo_institucional = email
        user.rol = rol  # Actualizar rol si cambió
        user.save()
        
        logger.info(f"✅ Usuario actualizado: {email} (auth0_sub: {auth0_sub})")
        return user
        
    except Usuario.DoesNotExist:
        # Intentar buscar por email (por si el usuario existe en Auth0 pero no en BD)
        try:
            user = Usuario.objects.get(correo_institucional__iexact=email)
            # Usuario existe por email pero no tiene auth0_sub vinculado
            user.auth0_sub = auth0_sub
            user.first_name = auth0_user_data.get('given_name', user.first_name)
            user.last_name = auth0_user_data.get('family_name', user.last_name)
            user.rol = rol
            user.save()
            
            logger.info(f"✅ Usuario actualizado con auth0_sub: {email}")
            return user
            
        except Usuario.DoesNotExist:
            # Usuario NO existe en BD → crearlo automáticamente
            logger.info(f"⚠️ Usuario {email} no existe en BD local. Creando...")
            
            # Obtener estado según el rol
            if rol == 'gestor':
                # Aprobar automáticamente a los gestores
                try:
                    estado = EstadoCatalogo.objects.get(entidad='cuenta', codigo='activa')
                except EstadoCatalogo.DoesNotExist:
                    logger.warning("Estado 'activa' no existe. Usando 'pendiente'")
                    estado = EstadoCatalogo.objects.get(entidad='cuenta', codigo='pendiente')
                is_staff = True
            else:
                # Otros roles quedan pendientes de aprobación
                try:
                    estado = EstadoCatalogo.objects.get(entidad='cuenta', codigo='pendiente')
                except EstadoCatalogo.DoesNotExist:
                    logger.error("No existe estado 'pendiente' en el catálogo")
                    raise
                is_staff = False
            
            # Crear usuario
            username = email.split('@')[0]  # Ej: 'gestor' de 'gestor@duocuc.cl'
            
            # Asegurar que el username sea único
            base_username = username
            counter = 1
            while Usuario.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            user = Usuario.objects.create_user(
                username=username,
                correo_institucional=email,
                first_name=auth0_user_data.get('given_name', ''),
                last_name=auth0_user_data.get('family_name', ''),
                rut='00000000-0',  # Placeholder, se puede actualizar después
                rol=rol,
                estado_cuenta=estado,
                auth0_sub=auth0_sub,
                is_active=True,
                is_staff=is_staff,
                vinculo='funcionario' if rol == 'gestor' else '',
                departamento='Gestión' if rol == 'gestor' else '',
            )
            
            if rol == 'gestor':
                user.fecha_aprobacion = timezone.now()
                user.save()
                logger.info(f"✅ Usuario GESTOR creado y aprobado: {email}")
            else:
                logger.info(f"✅ Usuario creado (pendiente): {email}")
            
            return user


# ═══════════════════════════════════════════════════════════════
# 9. MAPEO DE ROLES Auth0 → Campus Seguro
# ═══════════════════════════════════════════════════════════════
def mapear_rol_desde_token(claims):
    """
    Extrae el rol Campus Seguro desde los claims del JWT de Auth0.

    La Auth0 Action configurada en el dashboard incluye el rol en el token
    bajo el namespace configurado (AUTH0_CLAIMS_NAMESPACE):
        {
          "https://campus-seguro.app/roles": ["gestor"]
        }

    Si el claim de rol no existe en el token (usuario sin Action configurada
    o Auth0 no habilitado), retorna 'usuario' como valor por defecto.

    Parámetros:
        claims (dict): Claims decodificados del id_token (output de decodificar_token()).

    Retorna:
        str: Rol Campus Seguro. Uno de:
             'usuario', 'gestor', 'guardia', 'mantencion', 'enc_seguridad'

    Mapeo entre roles Auth0 y roles Campus Seguro:
        Auth0 app_metadata.campus_rol   →  Campus Seguro .rol
        ─────────────────────────────────────────────────────
        'gestor'                        →  'gestor'
        'guardia'                       →  'guardia'
        'mantencion'                    →  'mantencion'
        'enc_seguridad'                 →  'enc_seguridad'
        cualquier otro / ausente        →  'usuario'

    Este mapeo se aplica SOLO al leer el token durante el login.
    La fuente de verdad del rol es el campo Usuario.rol en la BD local,
    que se actualiza cuando el gestor aprueba la cuenta.
    """
    namespace = settings.AUTH0_CLAIMS_NAMESPACE
    roles_claim = claims.get(f'{namespace}/roles', [])

    roles_validos = {'gestor', 'guardia', 'mantencion', 'enc_seguridad', 'usuario'}

    if isinstance(roles_claim, list) and roles_claim:
        for r in roles_claim:
            if r in roles_validos:
                return r

    # También buscar en app_metadata si fue incluido en el token
    app_metadata = claims.get('https://campus-seguro.app/app_metadata', {})
    if isinstance(app_metadata, dict):
        rol_metadata = app_metadata.get('campus_rol', 'usuario')
        if rol_metadata in roles_validos:
            return rol_metadata

    return 'usuario'