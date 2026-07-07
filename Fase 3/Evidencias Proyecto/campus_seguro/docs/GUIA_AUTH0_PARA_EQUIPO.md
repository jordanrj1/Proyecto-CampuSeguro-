# Guía Auth0 para el Equipo – Campus Seguro

> **Para quién es esto:** Cualquier integrante del equipo que quiera entender por qué se usó Auth0, qué hace, y cómo afecta al flujo del sistema. No se necesita ser experto en seguridad para leer esto.

---

## ¿Qué es Auth0?

Auth0 es un servicio externo especializado en autenticación y seguridad de usuarios. En términos simples: **Auth0 se encarga de verificar que la persona que intenta entrar al sistema es quien dice ser**, y guarda las contraseñas de forma segura.

Imagínalo como el guardia de seguridad del edificio: Campus Seguro le dice a Auth0 "este usuario quiere entrar con esta contraseña", Auth0 verifica, y si todo está bien, emite un "pase digital" (token JWT) que el sistema acepta para dejar entrar al usuario.

---

## ¿Por qué se implementó?

### El problema anterior

Antes, cuando un usuario se registraba, Campus Seguro guardaba la contraseña directamente en su propia base de datos (SQLite). Eso tiene varios riesgos:

- Si alguien accede a la base de datos, obtiene todas las contraseñas.
- El proyecto tenía que implementar todo el sistema de seguridad de contraseñas por sí solo.
- No había protección automática contra ataques de fuerza bruta (intentar miles de combinaciones).
- El cierre de sesión solo limpiaba la sesión local de Django, pero la sesión de Auth0 seguía activa.

### La solución con Auth0

Ahora, Campus Seguro **no guarda ninguna contraseña en su base de datos**. La contraseña la maneja Auth0, que es una empresa especializada en seguridad con infraestructura profesional.

| Antes | Ahora |
|-------|-------|
| Contraseña guardada en SQLite de Campus Seguro | Contraseña guardada en Auth0 (nunca toca nuestra BD) |
| Sin protección anti-fuerza bruta | Auth0 bloquea automáticamente intentos repetidos |
| Cierre de sesión solo local | Cierre de sesión invalida también la sesión en Auth0 |
| Validación de contraseña manual | Auth0 aplica políticas de seguridad automáticamente |

---

## Beneficios concretos

### 1. Seguridad de contraseñas
Las contraseñas nunca se almacenan en nuestra base de datos. Si alguien extrae el SQLite del proyecto, no obtiene ninguna contraseña. Auth0 las guarda cifradas con estándares industriales.

### 2. Protección anti-fuerza bruta
Si alguien intenta adivinar la contraseña de un usuario haciendo muchos intentos seguidos, Auth0 lo detecta y bloquea automáticamente. Campus Seguro no tiene que implementar eso.

### 3. Cierre de sesión global
Cuando el usuario hace clic en "Cerrar Sesión", el sistema:
1. Elimina la sesión local de Django.
2. Redirige a Auth0 para que también invalide su sesión allá.

Eso significa que si el usuario tenía la sesión abierta en otro navegador, también se cierra.

### 4. Sin responsabilidad sobre contraseñas
Campus Seguro (el equipo) no tiene acceso a las contraseñas de los usuarios. Si alguien pregunta "¿cuál era mi contraseña?", la respuesta honesta es "no lo sabemos, está en Auth0".

### 5. Política de contraseñas automática
Auth0 exige que las contraseñas cumplan ciertos requisitos (mínimo 8 caracteres, al menos 3 de estos 4 grupos: minúsculas, MAYÚSCULAS, números, caracteres especiales). Eso se aplica automáticamente al registrarse.

---

## ¿Qué se puede hacer en el dashboard de Auth0?

El dashboard está en [manage.auth0.com](https://manage.auth0.com). Requiere las credenciales del equipo (las mismas del `.env`).

### Gestión de Usuarios (`User Management → Users`)

Esta es la sección que el equipo usará con más frecuencia:

**Ver y buscar usuarios:**
- Lista completa de todos los usuarios registrados en el sistema.
- Ver fecha de creación, último inicio de sesión, y si la cuenta está bloqueada.
- Buscar por correo electrónico para encontrar un usuario específico.

**Cambiar la contraseña de un usuario:**
1. Haz clic en el usuario en la lista.
2. Ve a la pestaña `Actions` dentro del perfil del usuario.
3. Haz clic en `Send Password Reset Email` → Auth0 envía un correo al usuario con un enlace para que él mismo cambie su contraseña.
> El equipo de Campus Seguro NO puede ver ni copiar la contraseña. Solo Auth0 puede iniciar el flujo de recuperación.

**Bloquear/desbloquear un usuario:**
- En el perfil del usuario, hay un botón `Block` (bloquear) o `Unblock`.
- Un usuario bloqueado en Auth0 NO puede iniciar sesión aunque su cuenta en Campus Seguro esté activa.
- Útil para casos de emergencia sin necesidad de acceder al panel de Campus Seguro.

**Eliminar un usuario:**
- Botón `Delete` en el perfil del usuario.
- Si se elimina de Auth0, el campo `auth0_sub` en Campus Seguro queda huérfano. Se debe eliminar también desde el panel del gestor o Django admin.

**Ver el `user_id` (auth0_sub):**
- En el perfil del usuario, aparece como `User ID: auth0|XXXXXXXXXXXX`.
- Este valor es el que Campus Seguro guarda en el campo `auth0_sub` del modelo `Usuario`.
- Sirve para vincular manualmente un usuario si algo falló durante el registro.

**Ver logs de inicio de sesión:**
- `Monitoring → Logs` en el menú lateral.
- Muestra cada intento de login con IP, resultado (éxito/fallo), y timestamp.
- Útil para detectar intentos de acceso no autorizados o diagnosticar errores de login.

### Aplicaciones (`Applications → Applications`)

Hay DOS aplicaciones configuradas para Campus Seguro:

**1. Campus Seguro Web (Regular Web Application)**
- Es la aplicación que usa el navegador para autenticarse.
- Aquí están las URLs de login/logout. Si cambias de `localhost` a otro dominio, actualiza aquí:
  - `Allowed Callback URLs`: `http://localhost:8000/dashboard/`
  - `Allowed Logout URLs`: `http://localhost:8000/login/`
  - `Allowed Web Origins`: `http://localhost:8000`
- El **Client ID** y **Client Secret** son las credenciales que van en `.env` como `AUTH0_CLIENT_ID` y `AUTH0_CLIENT_SECRET`.

**2. Campus Seguro Backend (Machine to Machine)**
- Es la "aplicación interna" que permite al backend Django crear/actualizar usuarios en Auth0 sin que el usuario lo vea.
- Se usa al registrarse (crea usuario en Auth0), al aprobar cuenta (actualiza rol en Auth0), y al hacer logout (revoca sesión en Auth0).
- Sus credenciales van en `.env` como `AUTH0_MGMT_CLIENT_ID` y `AUTH0_MGMT_CLIENT_SECRET`.

### Reglas y Acciones (`Actions → Flows`)

Las Actions son scripts JavaScript que Auth0 ejecuta automáticamente durante el flujo de login:

**Action configurada: `Agregar Rol Campus Seguro al Token`**
- Se ejecuta cada vez que un usuario inicia sesión.
- Lee el rol desde `app_metadata.campus_rol` (que Campus Seguro actualiza cuando el gestor aprueba la cuenta).
- Incluye el rol en el token JWT para que Campus Seguro pueda leerlo.
- Sin esta Action, el sistema igual funciona (lee el rol desde la BD local), pero no está disponible en el token.

Para ver o editar la Action: `Actions → Library → Custom` → seleccionar la Action.

### Monitoreo y Seguridad

**Protección automática (ya activa):**
- Auth0 detecta automáticamente ataques de fuerza bruta (muchos intentos fallidos desde la misma IP) y bloquea temporalmente al atacante.
- Si un usuario tiene demasiados intentos fallidos, Auth0 puede bloquear su cuenta automáticamente.

**Logs de actividad (`Monitoring → Logs`):**
- Cada login, logout, o intento fallido queda registrado en Auth0 con IP y timestamp.
- Complementa el `LogAuditoria` que mantiene Campus Seguro internamente.

**Notificaciones (si se configuran):**
- Auth0 puede enviar correos automáticos cuando se crea una cuenta, cuando se bloquea, o cuando se detecta actividad sospechosa.
- Se configuran en `Branding → Email Templates`.
- Para Campus Seguro, el correo de "Verificación de email" y "Recuperación de contraseña" son los más relevantes.

---

## ¿Qué pasa cuando se registra una cuenta nueva?

Este es el flujo completo desde que alguien llena el formulario hasta que puede entrar al sistema:

```
1. Usuario llena el formulario en /registro/
         ↓
2. Campus Seguro envía los datos a Auth0 (Management API)
   → Auth0 crea el usuario con su contraseña
   → Auth0 devuelve un ID único: auth0|XXXXXXXXX
         ↓
3. Campus Seguro guarda en su propia BD:
   → Nombre, RUT, correo, sede, carrera (datos institucionales)
   → El auth0_sub (ID de Auth0) para vincular ambos registros
   → Estado: PENDIENTE, Activo: NO
   → Rol: usuario (temporal, el gestor lo cambia)
   → Contraseña: NO SE GUARDA (set_unusable_password)
         ↓
4. La cuenta queda BLOQUEADA hasta que el gestor la apruebe
   → El usuario NO puede iniciar sesión todavía
         ↓
5. El gestor entra a /gestor/solicitudes/ y revisa la cuenta
   → Puede APROBAR y asignar un rol real (alumno, guardia, técnico, etc.)
   → Puede RECHAZAR si los datos no son correctos
         ↓
6. Si aprueba: estado → activa, is_active → True, rol actualizado
   → Auth0 también recibe la actualización de rol
   → El usuario recibe una notificación en el sistema
   → Ya puede iniciar sesión en /login/
```

**Punto clave:** En ningún paso Campus Seguro toca ni almacena la contraseña. Solo Auth0 la conoce.

---

## ¿Qué controla el Gestor?

El gestor es el administrador institucional del sistema. Tiene control total sobre las cuentas:

| Acción | Dónde | Resultado |
|--------|-------|-----------|
| Ver solicitudes pendientes | `/gestor/solicitudes/` | Lista de cuentas nuevas esperando revisión |
| Aprobar una cuenta | Botón "Aprobar" + seleccionar rol | Cuenta activada, usuario puede entrar |
| Rechazar una cuenta | Botón "Rechazar" | Cuenta rechazada, usuario recibe notificación |
| Asignar/cambiar rol | Al aprobar o desde gestión de usuarios | Rol actualizado en Campus Seguro y en Auth0 |
| Desactivar una cuenta | Desde gestión de usuarios | Usuario no puede iniciar sesión |
| Ver todos los usuarios activos | `/gestor/usuarios/` | Lista completa con filtros por rol y estado |

**Lo que el gestor NO controla:** Las contraseñas. Si un usuario olvidó su contraseña, debe recuperarla a través de Auth0 (flujo de recuperación por email). El gestor de Campus Seguro no puede ver ni cambiar contraseñas.

---

## Resumen en una línea

> **Auth0 custodia las contraseñas de los usuarios; Campus Seguro custodia los datos institucionales y los roles. El gestor controla quién puede entrar y con qué permisos.**

---

## Datos técnicos del tenant (para referencia interna)

| Variable | Valor |
|----------|-------|
| Dominio Auth0 | `dev-0fnyqt3tlgffohdh.us.auth0.com` |
| Conexión | `Username-Password-Authentication` |
| Namespace de claims | `https://campus-seguro.app` |
| URL de logout configurada | `http://localhost:8000/login/` |

Las credenciales completas (Client ID, Client Secret, etc.) están en el archivo `.env` del proyecto, que **no se sube a git** por seguridad.

---

*Para configuración técnica detallada, ver `docs/AUTH0_CONFIGURACION.md`.*  
*Para diagramas del flujo de autenticación, ver `docs/FLUJO_AUTENTICACION.md`.*  
*Para la arquitectura general del sistema, ver `docs/ARQUITECTURA_GENERAL.md`.*
