# Guía de Configuración Auth0 – Campus Seguro

## ¿Qué es Auth0 y por qué lo usamos?

Auth0 es un servicio de autenticación externo (Identity Provider). Lo usamos porque:
- Las contraseñas **nunca se guardan** en la base de datos de Campus Seguro.
- Auth0 maneja el cifrado, recuperación de contraseñas y seguridad de credenciales.
- Cumple con el criterio de aceptación: _"No se guarda contraseña en BD de Campus Seguro"_.

---

## Lo que necesitas hacer tú (Jordan) en el dashboard de Auth0

### Paso 1 – Crear cuenta en Auth0

1. Ve a [auth0.com](https://auth0.com) y crea una cuenta gratuita.
2. Al crear el tenant, elige la región más cercana (ej: `US` o `EU`).
3. Anota el dominio de tu tenant: `tu-nombre.us.auth0.com`.

---

### Paso 2 – Crear la Aplicación Principal (Regular Web Application)

1. En el dashboard de Auth0: **Applications → Applications → Create Application**.
2. Nombre: `Campus Seguro Web`.
3. Tipo: **Regular Web Applications**.
4. Haz clic en **Create**.

---

### Paso 3 – Configurar URLs de la Aplicación

En la pantalla de Settings de la aplicación:

| Campo | Valor para desarrollo local |
|-------|----------------------------|
| Allowed Callback URLs | `http://localhost:8000/dashboard/` |
| Allowed Logout URLs | `http://localhost:8000/login/` |
| Allowed Web Origins | `http://localhost:8000` |

Haz clic en **Save Changes**.

---

### Paso 4 – Habilitar el Grant Type "Password" (ROPC)

> Este paso es necesario para que Campus Seguro envíe credenciales
> directamente a Auth0 desde el formulario de login.

1. En la aplicación creada, ve a la pestaña **Settings**.
2. Baja hasta **Advanced Settings → Grant Types**.
3. Activa el checkbox **Password**.
4. Haz clic en **Save Changes**.

**Además**, en el nivel de tenant:

1. Ve a **Settings** (menú lateral) → **General**.
2. Baja hasta **API Authorization Settings**.
3. En **Default Directory**, escribe: `Username-Password-Authentication`.
4. Guarda.

---

### Paso 5 – Obtener las credenciales de la aplicación

En la pantalla de Settings de tu aplicación (Campus Seguro Web):

- Copia el **Domain** → va a `AUTH0_DOMAIN` en tu `.env`
- Copia el **Client ID** → va a `AUTH0_CLIENT_ID` en tu `.env`
- Copia el **Client Secret** → va a `AUTH0_CLIENT_SECRET` en tu `.env`

Para `AUTH0_AUDIENCE`, copia el dominio y agrega `/api/v2/`:
```
AUTH0_AUDIENCE=https://tu-tenant.us.auth0.com/api/v2/
```

---

### Paso 6 – Crear Aplicación Machine-to-Machine (Management API)

> Esta aplicación le permite al backend de Campus Seguro crear usuarios
> en Auth0 cuando alguien se registra, sin que el usuario tenga que
> interactuar con el dashboard de Auth0.

1. **Applications → Applications → Create Application**.
2. Nombre: `Campus Seguro Backend`.
3. Tipo: **Machine to Machine Applications**.
4. Haz clic en **Create**.
5. En la pantalla siguiente, selecciona la **Auth0 Management API**.
6. Habilita los siguientes **permisos (scopes)**:
   - `create:users`
   - `read:users`
   - `update:users`
   - `update:users_app_metadata`
   - `delete:users_sessions`
7. Haz clic en **Authorize**.

Luego en Settings de esta app M2M:
- Copia el **Client ID** → `AUTH0_MGMT_CLIENT_ID` en `.env`
- Copia el **Client Secret** → `AUTH0_MGMT_CLIENT_SECRET` en `.env`

---

### Paso 7 – Crear la Auth0 Action (para incluir roles en el JWT)

> Sin este paso, el token JWT que recibe Campus Seguro no incluirá
> el rol del usuario. La vista de login leerá el rol desde la BD local,
> pero esta Action es importante para futuras integraciones.

1. Ve a **Actions → Flows → Login**.
2. Haz clic en el botón **+** para agregar una acción custom.
3. Selecciona **Build Custom**.
4. Nombre: `Agregar Rol Campus Seguro al Token`.
5. En el editor de código, pega lo siguiente:

```javascript
exports.onExecutePostLogin = async (event, api) => {
  // Namespace para los custom claims (debe coincidir con AUTH0_CLAIMS_NAMESPACE en .env)
  const namespace = 'https://campus-seguro.app';

  // Leer el rol desde app_metadata (se actualiza cuando el gestor aprueba la cuenta)
  const campusRol = event.user.app_metadata?.campus_rol || 'usuario';
  const campusEstado = event.user.app_metadata?.campus_estado || 'pendiente';

  // Incluir el rol en el id_token y access_token
  api.idToken.setCustomClaim(`${namespace}/roles`, [campusRol]);
  api.accessToken.setCustomClaim(`${namespace}/roles`, [campusRol]);
  api.idToken.setCustomClaim(`${namespace}/estado`, campusEstado);
};
```

6. Haz clic en **Deploy**.
7. Arrastra la Action al flujo de Login (entre **Start** y **Complete**).
8. Haz clic en **Apply**.

---

### Paso 8 – Llenar el archivo `.env`

Abre el archivo `.env` en la raíz del proyecto y completa:

```env
DJANGO_SECRET_KEY=tu-clave-secreta-generada
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=*

AUTH0_DOMAIN=tu-tenant.us.auth0.com
AUTH0_CLIENT_ID=tu_client_id
AUTH0_CLIENT_SECRET=tu_client_secret
AUTH0_AUDIENCE=https://tu-tenant.us.auth0.com/api/v2/
AUTH0_CLAIMS_NAMESPACE=https://campus-seguro.app

AUTH0_MGMT_CLIENT_ID=tu_m2m_client_id
AUTH0_MGMT_CLIENT_SECRET=tu_m2m_client_secret
AUTH0_CONNECTION=Username-Password-Authentication
```

---

### Paso 9 – Crear usuarios iniciales en Auth0

Para los usuarios que ya existen en la BD local (creados antes de Auth0),
puedes crearlos en Auth0 manualmente:

1. Auth0 Dashboard → **User Management → Users → Create User**.
2. Ingresa el mismo email que tiene el usuario en la BD de Campus Seguro.
3. Asigna una contraseña temporal.
4. Ejecuta en Django shell para vincular el auth0_sub:

```python
python manage.py shell

from app.models import Usuario
u = Usuario.objects.get(correo_institucional='correo@ejemplo.cl')
u.auth0_sub = 'auth0|el_id_que_aparece_en_auth0'
u.save()
```

---

## Cómo verificar que todo funciona

1. Reinicia el servidor Django: `python manage.py runserver`
2. Navega a `http://localhost:8000/login/`
3. Ingresa las credenciales de un usuario que existe en Auth0
4. Si ves el dashboard → la integración funciona correctamente

Si hay problemas, revisa los logs del servidor. El servicio `auth0_service.py`
loguea los errores con detalle.

---

## Fallback para desarrollo sin Auth0

Si no tienes credenciales de Auth0, el sistema funciona en modo local:
- Deja vacías las variables `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET` en `.env`.
- `AUTH0_ENABLED` será `False` automáticamente.
- El login usará autenticación Django estándar (contraseña local).
- Usuarios existentes en la BD pueden seguir iniciando sesión normalmente.
