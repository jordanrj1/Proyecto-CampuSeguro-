# Manual de Pruebas en Equipo – Campus Seguro

**Versión:** Sprint 2 – Junio 2026
**Proyecto:** Campus Seguro – Sistema ERP institucional de mantención e incidencias

| Integrante | Rol en el equipo | Responsabilidad en las pruebas |
|---|---|---|
| Jordan Garcia | Gestor del sistema + responsable del servidor de pruebas | Levanta el servidor, comparte la URL, aprueba cuentas, gestiona el entorno |
| Moisés | Integrante del equipo | Pruebas funcionales: registro, navegación, reporte de errores |
| Ignacio Palma | Integrante del equipo | Pruebas funcionales: registro, navegación, reporte de errores |

> **Nota sobre responsabilidades:** Jordan opera el servidor compartido no porque tenga más autoridad, sino porque tiene el rol gestor configurado en el sistema y es quien administra las credenciales de Auth0. Moisés e Ignacio participan como usuarios del sistema para verificar que los flujos funcionan correctamente desde la perspectiva de un usuario final.

---

## Propósito de este manual

Permitir que el equipo realice pruebas funcionales coordinadas del sistema Campus Seguro, con todos los datos centralizados en un solo entorno, sin que Moisés ni Ignacio necesiten instalar ni configurar nada en sus computadores.

---

## Cómo funciona (sin tecnicismos)

Normalmente cada computador tiene su propia base de datos separada. Si Ignacio registra una cuenta en su computador, Jordan no la puede ver en el suyo.

La solución es que Jordan levanta el sistema en su máquina y usa una herramienta llamada **ngrok** que crea una dirección web pública. Moisés e Ignacio abren esa dirección en su navegador y están usando el sistema de Jordan, con la base de datos de Jordan. Por eso Jordan lo ve todo desde su panel del gestor.

---

## PARTE 1: Responsabilidades de Jordan

Jordan es el único que necesita tener el proyecto instalado y corriendo. Su responsabilidad es dejar el sistema disponible para que el equipo pueda probar.

### Antes de la primera sesión (hacer una sola vez)

**Verificar que ngrok está configurado:**
```
ngrok version
```
Debe mostrar `ngrok version 3.39.6` o superior.

**Verificar que el gestor existe:**
```bash
python manage.py crear_gestor
```
Si dice "Ya existe un usuario con ese correo" → está listo.

---

### Al inicio de cada sesión de pruebas

**Paso 1 — Abrir dos terminales** en la carpeta del proyecto.

**Paso 2 — Terminal 1: levantar Django**
```bash
python manage.py runserver
```

**Paso 3 — Terminal 2: levantar ngrok**
```
C:\Users\usuario\AppData\Local\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe http 8000
```
ngrok mostrará:
```
Forwarding   https://abc123.ngrok-free.app -> http://localhost:8000
```
Copiar la URL HTTPS.

**Paso 4 — Actualizar `.env`** con la URL recibida (sección NGROK al final del archivo):

```
# Comentar esta línea:
# AUTH0_LOGOUT_RETURN_URL=http://localhost:8000/login/

# Descomentar estas cuatro y actualizar con la URL nueva:
CSRF_TRUSTED_ORIGINS=https://abc123.ngrok-free.app
USE_X_FORWARDED_HOST=True
SECURE_PROXY_SSL_HEADER=True
AUTH0_LOGOUT_RETURN_URL=https://abc123.ngrok-free.app/login/
```

**Paso 5 — Actualizar Auth0 Dashboard:**
Applications → Campus Seguro Web → Settings → `Allowed Logout URLs`:
```
http://localhost:8000/login/, https://abc123.ngrok-free.app/login/
```
Clic en **Save Changes**.

**Paso 6 — Reiniciar Django** (Ctrl+C → `python manage.py runserver`).

**Paso 7 — Enviar la URL** a Moisés e Ignacio.

---

### Si Moisés o Ignacio ya habían creado cuentas antes en sus propios computadores

Esas cuentas están en Auth0 pero no en la base de datos de Jordan. Para traerlas y poder gestionarlas:
```bash
python manage.py sincronizar_auth0
```

---

### Al finalizar la sesión

Volver el `.env` a modo local:
```
# Descomentar esta línea:
AUTH0_LOGOUT_RETURN_URL=http://localhost:8000/login/

# Comentar las cuatro líneas ngrok
```
Cerrar ngrok (Ctrl+C en Terminal 2).

---

### Para limpiar cuentas de prueba entre sesiones

```bash
# Ver qué se eliminaría sin borrar nada
python manage.py limpiar_cuentas --dry-run

# Limpiar de ambos lados (BD local + Auth0)
python manage.py limpiar_cuentas --auth0
```

El gestor de Jordan nunca se elimina con este comando.

---

## PARTE 2: Responsabilidades de Moisés e Ignacio

### Lo que necesitan

- Un computador con conexión a internet.
- Un navegador web (Chrome, Edge, Firefox o Safari).
- La URL que Jordan les envíe por WhatsApp o Discord.

### Lo que NO necesitan instalar

| Cosa | Por qué no es necesaria |
|------|------------------------|
| Python o Django | El sistema ya corre en el computador de Jordan |
| Clonar el repositorio | No van a correr el código, solo a usar la interfaz |
| SQLite o base de datos | La base de datos es la de Jordan |
| El archivo `.env` | Solo Jordan lo configura |
| ngrok | Solo Jordan lo usa para compartir su servidor |

### Pasos para Moisés e Ignacio

**Paso 1 — Recibir la URL del día**
Jordan enviará algo como `https://abc123.ngrok-free.app`. Esta URL puede cambiar cada sesión. Pedir la URL actualizada antes de cada sesión de pruebas.

**Paso 2 — Abrir la URL**
Escribirla en la barra de direcciones del navegador. La primera vez ngrok muestra una pantalla con el mensaje *"You are about to visit..."* — hacer clic en **"Visit Site"**. Esto pasa solo una vez por sesión.

**Paso 3 — Registrar una cuenta**
En la pantalla de login, hacer clic en el enlace para crear cuenta. Completar con:
- Nombre y apellido reales
- Correo institucional (`nombre@duocuc.cl`)
- Contraseña: mínimo 8 caracteres, con mayúsculas, minúsculas, número y símbolo

El sistema confirmará: *"Solicitud enviada correctamente."*

**Paso 4 — Esperar aprobación de Jordan**
La cuenta queda en estado **pendiente**. Jordan la verá en su panel y la aprobará.

**Paso 5 — Ingresar al sistema**
Cuando Jordan confirme la aprobación, volver a la URL y entrar con el correo y contraseña registrados.

---

### Qué hacer si el navegador muestra un error

| Error que ves | Qué significa | Qué hacer |
|---|---|---|
| "Este sitio no existe" | ngrok no está activo o cambió la URL | Pedir la URL actualizada a Jordan |
| "Tu cuenta está pendiente" | Jordan aún no aprobó | Avisarle para que apruebe |
| "Tu cuenta no está registrada" | La cuenta está en otro entorno | Avisar a Jordan para que ejecute `sincronizar_auth0` |
| "Correo o contraseña incorrectos" | Credenciales equivocadas | Verificar correo y contraseña |

---

## PARTE 3: Flujo completo de prueba coordinada

Para verificar que el sistema funciona de extremo a extremo:

1. **Jordan** levanta el servidor + ngrok y envía la URL.
2. **Moisés o Ignacio** abre la URL y se registra.
3. **Jordan** abre su panel del gestor y ve la solicitud nueva.
4. **Jordan** aprueba la solicitud y asigna el rol correspondiente.
5. **Moisés o Ignacio** inicia sesión y accede al dashboard de su rol.
6. **Todos** verifican que el flujo se completó correctamente.

---

## Referencia rápida de comandos (solo Jordan)

```bash
python manage.py runserver                  # Servidor
python manage.py sincronizar_auth0          # Importar usuarios de Auth0
python manage.py limpiar_cuentas --dry-run  # Ver qué se limpiaría
python manage.py limpiar_cuentas --auth0    # Limpiar ambos lados
python manage.py crear_gestor              # Crear gestor en BD nueva
```
