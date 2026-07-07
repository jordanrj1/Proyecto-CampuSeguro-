# Guía de Setup – Nuevo Entorno de Desarrollo

> **Para quién es esto:** Cualquier integrante del equipo que clone el repositorio
> y necesite levantar Campus Seguro en su máquina local para **desarrollo de código**.
>
> **Si solo quieres hacer pruebas funcionales**, no necesitas esta guía.
> Solo pídele la URL ngrok a Jordan y ábrela en el navegador.

> **Historial de versiones**
> - **v1 – Sprint 1:** Setup básico con SQLite y Auth0 fallback. Sin comandos de gestión.
> - **v2 – Sprint 2 (Junio 2026):** Se reemplaza la creación manual del gestor por `crear_gestor`. Se agregan `sincronizar_auth0` y `limpiar_cuentas`. Se documenta la distinción entre desarrollo local y pruebas compartidas (ngrok).
> - **v3 – Sprint 2 (Junio 2026):** Setup completamente automático via señal `post_migrate`. Ya no se requiere `crear_gestor` ni script manual de admin. Solo `migrate` + `runserver`.

---

## Antes de empezar: ¿necesito mi propia cuenta de Auth0?

**No.** El equipo comparte un mismo tenant (instancia) de Auth0. El archivo `.env`
ya viene incluido en el repositorio con las credenciales reales configuradas.
Al clonar el repo ya tienes todo lo necesario.

> Si por alguna razón no aparece el archivo `.env` después de clonar, pide
> el archivo directamente a Jordan.

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

Instala: Django 5.2, Pillow, python-dotenv, requests, PyJWT y demás dependencias.

---

### 4. Variables de entorno (`.env`)

#### v1 – Sprint 1 _(referencia histórica)_

En Sprint 1 el `.env` no estaba en el repositorio y debía pedirse a Jordan.
Las variables de Auth0 podían dejarse vacías para usar autenticación local Django.

#### v2 – Sprint 2

El archivo `.env` ya viene en el repositorio con todas las credenciales configuradas.
**No necesitas crear nada.** Verifica que exista en la raíz del proyecto:

```
campus_seguro/
├── .env          ← debe estar aquí después de clonar
├── manage.py
├── requirements.txt
└── ...
```

---

### 5. Aplicar migraciones

```bash
python manage.py migrate
```

Crea todas las tablas en `db.sqlite3`. A partir de **v3**, este paso también:

- Puebla automáticamente todos los catálogos de estados (50+ registros)
- Crea las 217 ubicaciones del campus (Edificio E y H)
- Crea el usuario `gestor@duocuc.cl` con acceso a Django Admin

> Las migraciones son acumulativas. Correr `migrate` en cualquier momento
> aplica solo lo que falta; no borra datos existentes.

**En v3 ya no se necesita ningún paso adicional después de `migrate`.**

---

### 6. Crear el usuario Gestor

#### v1 – Sprint 1 _(referencia histórica)_

Se creaba manualmente desde el Django shell con un bloque Python, asignando
campos uno a uno. El proceso era propenso a errores y requería conocer
el ID exacto de `EstadoCatalogo`.

#### v2 – Sprint 2 _(referencia histórica)_

Se usaba el comando `crear_gestor` interactivo:

```bash
python manage.py crear_gestor
```

#### v3 – Sprint 2 (actual)

**No se requiere ningún comando.** El gestor se crea automáticamente durante `migrate`
via la señal `post_migrate` en `app/apps.py`. Credenciales resultantes:

| | |
|--|--|
| Login app (`/login/`) | Usar credenciales de Auth0 |
| Django Admin (`/admin/`) | `gestor@duocuc.cl` / `CampusAdmin2024!` |

---

### 7. Sincronizar usuarios desde Auth0 (v2 – Sprint 2)

> Este paso no existía en v1.

Cuando otros integrantes crearon cuentas desde sus propios entornos locales
antes de adoptar ngrok, esos usuarios están en Auth0 pero no en tu SQLite local.
Importarlos con:

```bash
python manage.py sincronizar_auth0
```

Para ver qué se importaría sin crear nada:

```bash
python manage.py sincronizar_auth0 --dry-run
```

> Si eres un integrante nuevo que clona el repo para desarrollo local,
> este paso trae a tu SQLite todos los usuarios que ya existen en Auth0.

---

### 8. Limpiar cuentas de prueba (v2 – Sprint 2)

> Este paso no existía en v1.

Para resetear el entorno antes de una nueva sesión de pruebas,
sin borrar toda la base de datos (tickets, ubicaciones, catálogos se preservan):

```bash
# Ver qué se eliminaría (sin borrar nada)
python manage.py limpiar_cuentas --dry-run

# Eliminar solo de la BD local
python manage.py limpiar_cuentas

# Eliminar de la BD local Y de Auth0 (limpieza total)
python manage.py limpiar_cuentas --auth0
```

> El gestor nunca se elimina con este comando.

---

### 9. Levantar el servidor

```bash
python manage.py runserver
```

Navega a `http://localhost:8000/login/` e ingresa con el gestor.

---

### 10. Verificar que Auth0 funciona

1. Ve a `http://localhost:8000/login/`
2. Ingresa con las credenciales del gestor configurado en Auth0
3. Si ves el panel del gestor → funciona correctamente
4. Haz clic en "Cerrar Sesión" → debe redirigirte al login sin error

Si al cerrar sesión hay error (`invalid_request`):
- Verifica que `http://localhost:8000/login/` esté en `Allowed Logout URLs`
  en Auth0 Dashboard → Application → Settings
- Debe coincidir exactamente con `AUTH0_LOGOUT_RETURN_URL` en tu `.env`

---

## Resumen de comandos (v3 – Sprint 2, actual)

```bash
# Clonar y preparar
git clone <repo-url> && cd campus_seguro
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt

# Base de datos + catálogos + gestor admin (todo en uno)
python manage.py migrate

# Levantar servidor
python manage.py runserver
```

**Comandos opcionales:**

```bash
# Traer usuarios que existen en Auth0 pero no en la BD local
python manage.py sincronizar_auth0

# Limpiar cuentas de prueba
python manage.py limpiar_cuentas

---

## Distinción importante: desarrollo local vs pruebas compartidas

| Escenario | Qué usar |
|-----------|----------|
| Escribir y probar código en tu máquina | `python manage.py runserver` en tu entorno local |
| Probar flujos completos con otros integrantes | Abrir la URL ngrok que Jordan comparte |
| Ver todas las solicitudes de cuenta del equipo | Acceder por la URL ngrok (van al SQLite de Jordan) |

Cuando se trabaja en entorno local propio, la base de datos es independiente.
Para pruebas cruzadas entre integrantes, siempre usar la URL ngrok.
