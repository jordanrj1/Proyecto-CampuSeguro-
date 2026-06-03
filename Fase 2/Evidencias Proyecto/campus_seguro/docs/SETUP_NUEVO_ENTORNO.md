# Guía de Setup – Nuevo Entorno de Desarrollo

> **Para quién es esto:** Cualquier integrante del equipo que clone el repositorio por primera vez y necesite levantar Campus Seguro en su máquina local.

---

## Antes de empezar: ¿necesito mi propia cuenta de Auth0?

**No.** El equipo comparte un mismo tenant (instancia) de Auth0. Jordan tiene las credenciales y debe
compartir el archivo `.env` por un canal seguro (WhatsApp, correo directo, USB). **No se sube a git.**

Si por alguna razón necesitas tu propio tenant de Auth0 (ej: entorno de producción separado), sigue la guía en `docs/AUTH0_CONFIGURACION.md`.

---

## Pasos de instalación

### 1. Clonar el repositorio

```bash
git clone <URL-del-repositorio>
cd campus_seguro
```

---

### 2. Crear y activar el entorno virtual

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

> Por qué: el entorno virtual aísla las dependencias del proyecto de las del sistema.

---

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

Esto instala: Django 5.2, Pillow, python-dotenv, requests, PyJWT, certifi.

---

### 4. Variables de entorno (`.env`)

El archivo `.env` ya viene incluido en el repositorio con las credenciales reales de Auth0.
**No necesitas crear nada ni pedirle nada.** Al clonar el repo ya lo tienes.

Solo verifica que el archivo exista en la raíz del proyecto (junto a `manage.py`):

```
campus_seguro/
├── .env          ← debe estar aquí después de clonar
├── manage.py
├── requirements.txt
└── ...
```

> Si por alguna razón no aparece el archivo `.env`, es posible que tu cliente de git
> no descargue archivos que empiezan con punto en algunos sistemas. En ese caso
> pide el archivo directamente al responsable (Jordan).

---

### 5. Aplicar migraciones

```bash
python manage.py migrate
```

Esto crea todas las tablas en `db.sqlite3`, incluyendo la tabla `app_usuario`
con el campo `auth0_sub` (ID de Auth0, puede ser nulo en desarrollo local).

> Por qué hay 8+ migraciones: el proyecto evolucionó iterativamente. La migración
> más reciente (`0008_add_auth0_sub_to_usuario`) agregó el campo `auth0_sub`
> al modelo `Usuario` para vincular cada usuario con su identidad en Auth0.

---

### 6. Crear el usuario Gestor

El sistema requiere al menos un usuario con `rol='gestor'` para aprobar cuentas nuevas.
Los usuarios de prueba del desarrollo **no deben existir en tu entorno local**.

> Por qué este usuario: el gestor es el único rol que puede aprobar solicitudes de cuentas.
> Sin él, cualquier usuario que se registre queda bloqueado en estado 'pendiente' y no puede entrar.

---

### 7. Eliminar usuarios de prueba

Si clonaste el repositorio y ya tiene datos de prueba en `db.sqlite3`
(ej: `alumnoo@duocuc.cl`, `prueba@duocuc.cl`, etc.), límpialos;



### 8. Levantar el servidor

```bash
python manage.py runserver
```

Navega a `http://localhost:8000/login/` e ingresa con el gestor que creaste.

---

### 9. Verificar que Auth0 funciona (si tienes el .env real)

1. Ve a `http://localhost:8000/login/`
2. Ingresa con las credenciales del gestor que existe en Auth0 (las que Jordan configuró)
3. Si ves el panel del gestor → Auth0 está funcionando correctamente
4. Haz clic en "Cerrar Sesión" → debe redirigirte de vuelta a la pantalla de login sin error

Si al cerrar sesión aparece un error de Auth0 (`invalid_request` o similar):
- Verifica que en Auth0 Dashboard → Application → Settings → `Allowed Logout URLs`
  incluya exactamente `http://localhost:8000/login/`
- El valor debe coincidir con `AUTH0_LOGOUT_RETURN_URL` en tu `.env`

---

## Resumen de comandos

```bash
# 1. Clonar
git clone <repo-url> && cd campus_seguro

# 2. Entorno virtual
python -m venv venv && venv\Scripts\activate

# 3. Dependencias
pip install -r requirements.txt

# 4. .env ya viene en el repo — no se necesita ningún comando

# 5. Base de datos
python manage.py migrate

# 6. Crear gestor (pegar el bloque Python del paso 6 en el shell)
python manage.py shell

# 7. Servidor
python manage.py runserver
```

