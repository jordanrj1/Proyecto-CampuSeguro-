# Solución: Entornos Compartidos y Base de Datos Centralizada

**Proyecto:** Campus Seguro  
**Sprint:** 2  
**Responsable:** Jordan Garcia  
**Fecha:** Junio 2026  

---

## 1. Contexto y Problema Identificado

Durante las pruebas funcionales del sistema se detectó que las solicitudes de cuenta creadas por compañeros de equipo en sus propios entornos de desarrollo **no eran visibles para el gestor principal**. Esto impedía probar el flujo completo de gestión de cuentas (registro → revisión → aprobación) entre distintos integrantes del equipo.

Las cuentas creadas sí aparecían en el panel de Auth0 (tenant compartido), pero no en el panel del gestor dentro de la aplicación Django.

---

## 2. Diagnóstico Técnico

### Causa raíz

El proyecto utiliza **SQLite** como motor de base de datos (`db.sqlite3`). SQLite es un archivo local que reside en la máquina de cada desarrollador. Al clonar el repositorio y levantar Django, cada integrante genera su propio archivo de base de datos completamente aislado.

Cuando un compañero registra una solicitud de cuenta desde su entorno local:

- Auth0 recibe y registra al usuario en el tenant compartido → **visible para todos** en el dashboard de Auth0.
- Django guarda el registro del usuario (`Usuario`, estado `pendiente`, notificación al gestor) en **el `db.sqlite3` de esa máquina** → invisible para el resto.

El gestor (Jordan), corriendo Django en su propia máquina, consulta su propio `db.sqlite3` y no tiene registro de esas solicitudes. Por eso el error que aparecía en los logs era:

```
Auth0 autenticó a ig.palmam@duocuc.cl pero no existe en BD local.
```

Auth0 confirmó que el usuario existe; Django no lo encontró en su base de datos local.

### Por qué Auth0 funciona como recurso compartido y SQLite no

| Recurso      | Naturaleza        | Resultado                             |
|--------------|-------------------|---------------------------------------|
| Auth0        | Servicio remoto   | Compartido entre todos los entornos   |
| `db.sqlite3` | Archivo local     | Aislado por máquina                   |

Auth0 es un servicio externo al que todos se conectan con las mismas credenciales (definidas en `.env`). SQLite es un archivo que Django lee y escribe directamente en disco; no hay servidor que centralice las escrituras.

---

## 3. Solución Implementada

Se optó por la solución **ngrok como servidor central de pruebas**, manteniendo SQLite como motor de base de datos (sin migrar a PostgreSQL u otro motor de servidor).

### Principio de la solución

Jordan levanta su instancia de Django en su máquina y la expone públicamente mediante ngrok, una herramienta que crea un túnel seguro HTTPS entre internet y el servidor local.

Todos los compañeros acceden a través de esa URL pública. Al ser un único punto de entrada, todas las solicitudes de cuenta, aprobaciones y acciones quedan registradas en la base de datos de Jordan. El gestor ve todo porque todo pasa por su entorno.

Los compañeros no necesitan levantar Django localmente para probar el sistema; solo necesitan la URL.

### Tecnologías utilizadas

- **ngrok** (versión 3.39.6 o superior): túnel seguro HTTPS hacia `localhost:8000`.
- **Django 5.2**: servidor web del proyecto.
- **SQLite**: base de datos local (sin cambios).
- **Auth0**: autenticación externa (sin cambios).

---

## 4. Cambios Realizados en el Código

### 4.1. `campus_seguro/settings.py`

Se agregó soporte para tres variables de entorno necesarias cuando Django opera detrás de un proxy HTTPS como ngrok:

**`CSRF_TRUSTED_ORIGINS`**  
Django 4.0 en adelante exige que los orígenes HTTPS que envían formularios POST estén explícitamente autorizados. Sin esta variable, todos los formularios (login, registro, gestión) fallan con error 403 CSRF cuando se accede desde la URL ngrok.

**`USE_X_FORWARDED_HOST`**  
Cuando ngrok reenvía la solicitud a Django, incluye el header `X-Forwarded-Host` con el dominio original. Activar esta opción permite que Django construya URLs absolutas correctas (usado en redirects después del logout, entre otros).

**`SECURE_PROXY_SSL_HEADER`**  
ngrok termina la conexión SSL externamente y reenvía la solicitud a Django como HTTP. Este header (`X-Forwarded-Proto: https`) le indica a Django que la conexión original fue segura.

Las tres variables se leen desde `.env` y tienen valores por defecto que no alteran el comportamiento cuando no están definidas, por lo que no rompen los entornos locales de los compañeros.

### 4.2. `.env.example`

Se documenta la sección de configuración para ngrok con los pasos detallados para quien deba activarlo.

### 4.3. `.env` (local, no va a git)

Se agregan las variables ngrok comentadas como plantilla lista para descomentar cuando se inicia una sesión de pruebas compartidas.

---

## 5. Comandos de Gestión Creados

Se crearon tres comandos Django (`manage.py`) para gestionar el ciclo de vida de usuarios en entornos de desarrollo.

### 5.1. `crear_gestor`

**Archivo:** `app/management/commands/crear_gestor.py`

**Propósito:** Crea el usuario gestor inicial en una base de datos recién migrada. Es el primer paso después de ejecutar `migrate` en un entorno nuevo.

**Por qué es necesario:** Django no incluye por defecto un comando para crear usuarios con campos personalizados como `correo_institucional`, `rut`, `rol` y `estado_cuenta`. El `createsuperuser` estándar no cumple con los requisitos del modelo `Usuario` del proyecto.

**Comportamiento:**
- Verifica que el catálogo de estados esté poblado (requiere migraciones aplicadas).
- Solicita correo institucional, RUT, nombre y apellido.
- Crea el usuario con `rol='gestor'`, `estado_cuenta='activa'`, `is_active=True`.
- No guarda contraseña (`set_unusable_password`); Auth0 la gestiona.
- El campo `auth0_sub` se vincula automáticamente en el primer inicio de sesión (el flujo de login ya contempla esto en la línea 179 de `views.py`).

**Uso:**
```bash
python manage.py crear_gestor
python manage.py crear_gestor --email gestor@duocuc.cl --rut 12.345.678-9 --nombre Jordan --apellido Garcia
```

---

### 5.2. `sincronizar_auth0`

**Archivo:** `app/management/commands/sincronizar_auth0.py`

**Propósito:** Consulta Auth0 Management API y crea en la BD local los registros de usuarios que existen en Auth0 pero no en el `db.sqlite3` local.

**Por qué es necesario:** Cuando compañeros registran cuentas desde sus propios entornos (antes de adoptar ngrok, o accidentalmente), los usuarios quedan en Auth0 pero no en la BD local del gestor. Sin este comando, esos usuarios producen el error "Auth0 autenticó a X pero no existe en BD local" al intentar ingresar.

**Comportamiento:**
- Llama a `GET /api/v2/users` con paginación (hasta 100 por página).
- Por cada usuario de Auth0, verifica si existe en la BD local por `correo_institucional` o por `auth0_sub`.
- Si no existe, lo crea con los datos disponibles en Auth0 (`email`, `given_name`, `family_name`, `app_metadata`).
- El campo `rol` y `estado_cuenta` se toman del `app_metadata` de Auth0 (`campus_rol`, `campus_estado`).
- El RUT se asigna como placeholder temporal (`SYNC-` + últimos 7 caracteres del `user_id`) por no estar disponible en Auth0. El gestor puede corregirlo al aprobar la cuenta.
- **Nunca sobreescribe** usuarios ya existentes.

**Uso:**
```bash
python manage.py sincronizar_auth0            # importa usuarios faltantes
python manage.py sincronizar_auth0 --dry-run  # muestra qué importaría sin crear nada
```

---

### 5.3. `limpiar_cuentas`

**Archivo:** `app/management/commands/limpiar_cuentas.py`

**Propósito:** Elimina cuentas de prueba de la BD local y opcionalmente de Auth0. Permite reiniciar el entorno de pruebas sin borrar toda la base de datos.

**Por qué es necesario:** Durante las sesiones de prueba se generan muchos usuarios de prueba que contaminan el entorno. Borrar el `db.sqlite3` completo elimina también ubicaciones, catálogos, tickets y otros datos valiosos. Este comando elimina solo los usuarios prescindibles.

**Comportamiento:**
- Lista todos los usuarios que no son gestor ni superusuario antes de actuar.
- Solicita confirmación interactiva (se puede omitir con `--confirmar`).
- Elimina los usuarios seleccionados de la BD local con una transacción atómica.
- Si se usa `--auth0`, también elimina cada usuario de Auth0 via `DELETE /api/v2/users/{id}` usando la Management API.
- **Nunca elimina** usuarios con `rol='gestor'` ni `is_superuser=True`.

**Relación entre BD local y Auth0 al usar este comando:**

Si se ejecuta **sin** `--auth0`: los usuarios desaparecen de la BD local pero siguen existiendo en Auth0. Si intentan ingresar, el login fallará con "no existe en BD local". Para recuperarlos basta con ejecutar `sincronizar_auth0`.

Si se ejecuta **con** `--auth0`: los usuarios se eliminan de ambos sistemas. La operación en Auth0 es irreversible. Los usuarios tendrían que registrarse nuevamente.

**Uso:**
```bash
python manage.py limpiar_cuentas                     # solo BD local, con confirmacion
python manage.py limpiar_cuentas --auth0             # BD local + Auth0
python manage.py limpiar_cuentas --dry-run           # solo muestra, no borra
python manage.py limpiar_cuentas --auth0 --confirmar # sin prompt (para scripts)
```

---

## 6. Flujo de Trabajo para el Equipo

### Primer uso (clonar el repositorio)

```bash
git clone <url-repositorio>
cd campus_seguro
pip install -r requirements.txt
python manage.py migrate
python manage.py crear_gestor
python manage.py runserver
```

Este flujo levanta un entorno local completamente funcional con su propio `db.sqlite3`. Es el entorno de **desarrollo individual**: cada integrante trabaja en sus features de forma aislada.

### Sesiones de prueba compartidas (usar ngrok)

Solo Jordan (gestor principal) realiza estos pasos:

**Paso 1 — Configurar ngrok (una sola vez por instalación):**
```bash
ngrok config add-authtoken TU_TOKEN
```

**Paso 2 — Levantar el servidor y el túnel:**
```bash
# Terminal 1
python manage.py runserver

# Terminal 2
ngrok http 8000
```
ngrok entrega una URL del tipo `https://abc123.ngrok-free.app`.

**Paso 3 — Actualizar `.env`** con la URL recibida (descomentar las líneas de la sección NGROK y comentar `AUTH0_LOGOUT_RETURN_URL=http://localhost:8000/login/`):
```
CSRF_TRUSTED_ORIGINS=https://abc123.ngrok-free.app
USE_X_FORWARDED_HOST=True
SECURE_PROXY_SSL_HEADER=True
AUTH0_LOGOUT_RETURN_URL=https://abc123.ngrok-free.app/login/
```

**Paso 4 — Registrar la URL en Auth0 Dashboard:**  
Applications → [tu app] → Settings → `Allowed Logout URLs`: agregar `https://abc123.ngrok-free.app/login/` sin quitar las existentes.

**Paso 5 — Reiniciar Django** (Ctrl+C y `python manage.py runserver`).

**Paso 6 — Compartir la URL** con los compañeros. Ellos solo abren el navegador, no necesitan configurar nada.

> **Nota:** La URL de ngrok cambia cada vez que se reinicia ngrok en el plan gratuito. Los pasos 3, 4 y 6 deben repetirse cuando cambie.

### Si un compañero creó cuentas en su entorno local antes de usar ngrok

```bash
python manage.py sincronizar_auth0
```

Esto trae todos los usuarios registrados en Auth0 que no están en la BD local de Jordan.

### Reinicio del entorno de pruebas

```bash
# Opcion 1: limpiar solo cuentas (preserva tickets, ubicaciones, etc.)
python manage.py limpiar_cuentas --auth0

# Opcion 2: reinicio total (borra todo, incluidos tickets y datos)
del db.sqlite3
python manage.py migrate
python manage.py crear_gestor
```

---

## 7. Preguntas Frecuentes

**¿Los compañeros necesitan hacer git pull para usar ngrok?**  
No para acceder al sistema. Solo necesitan la URL. El `git pull` es necesario si van a desarrollar código localmente.

**¿Las cuentas creadas hoy por los compañeros estarán disponibles mañana?**  
Sí, si las crearon accediendo a la URL ngrok de Jordan. Esas solicitudes quedan en el `db.sqlite3` de Jordan y persisten entre sesiones. Si las crearon desde su propio `runserver` local, no estarán en la BD de Jordan; para recuperarlas se usa `sincronizar_auth0`.

**¿Qué pasa si borro un usuario de la BD local pero no de Auth0?**  
El usuario sigue existiendo en Auth0. Si intenta ingresar, Auth0 lo autenticará pero Django retornará el error "no existe en BD local". Basta con correr `sincronizar_auth0` para recrear el registro local.

**¿Qué pasa si borro un usuario de Auth0 pero no de la BD local?**  
El registro local queda huérfano. El usuario no podrá ingresar porque Auth0 rechazará sus credenciales. La entrada en la BD local queda inactiva y puede eliminarse manualmente o con `limpiar_cuentas`.

**¿El campo RUT de los usuarios importados por `sincronizar_auth0` es válido?**  
No. Auth0 no almacena el RUT; el comando asigna un valor temporal `SYNC-XXXXXXX`. El gestor puede editarlo desde el panel de administración al aprobar la cuenta.

**¿ngrok es gratuito?**  
El plan gratuito es suficiente para desarrollo y pruebas. La limitación principal es que la URL cambia cada vez que se reinicia ngrok. Con un plan de pago se puede fijar un subdominio permanente.

---

## 7b. Argumento técnico para defender el uso de ngrok

### Por qué ngrok no interfiere con el flujo de la aplicación

Desde el punto de vista de Django y Auth0, una solicitud que llega por la URL de ngrok es idéntica a una que llega por `localhost`. ngrok actúa como un **proxy inverso transparente**: recibe la solicitud HTTPS externamente, la descifra y la reenvía a Django como HTTP en el puerto 8000. Django procesa esa solicitud exactamente igual que si viniera del navegador local.

Las tres variables agregadas a `settings.py` (`CSRF_TRUSTED_ORIGINS`, `USE_X_FORWARDED_HOST`, `SECURE_PROXY_SSL_HEADER`) son el estándar de configuración para cualquier proxy inverso, incluyendo nginx en producción. No son un parche específico de ngrok; son buenas prácticas de despliegue.

### Por qué no altera los casos de uso

Ningún caso de uso del sistema depende del origen de la solicitud. El flujo registro → pendiente → aprobación gestor → acceso por rol funciona igual independientemente de si el usuario llega por `localhost:8000` o por `https://abc.ngrok-free.app`. La lógica de negocio, los modelos, las vistas y las reglas de autorización no cambian.

### Por qué es una práctica válida en la industria

ngrok es una herramienta usada profesionalmente en desarrollo de software. Empresas como Stripe, Twilio y GitHub la documentan en sus guías de integración para que desarrolladores prueben webhooks y flujos de autenticación en entornos locales. No es una solución improvisada; es un patrón de trabajo distribuido reconocido.

### Por qué es controlada y segura

El túnel ngrok solo existe mientras Jordan lo mantiene activo. Cuando cierra ngrok, la URL deja de funcionar inmediatamente. A diferencia de un servidor siempre encendido, el equipo controla exactamente cuándo está expuesto el sistema. La conexión es HTTPS con el mismo estándar de cifrado que cualquier sitio web de producción.

### Argumento para presentación académica

ngrok resuelve un problema arquitectural real del proyecto: la imposibilidad de compartir datos entre entornos SQLite distribuidos sin cambiar el motor de base de datos. La solución centraliza el punto de entrada de datos sin modificar la arquitectura de la aplicación ni introducir dependencias nuevas de producción. Para efectos de una demostración, permite mostrar el flujo completo de gestión de cuentas en tiempo real con múltiples usuarios participando desde distintas máquinas.

---

## 8. Integridad de Datos al Eliminar Usuarios

### Qué protege el modelo (comportamiento por defecto)

El modelo define explícitamente qué ocurre en cada relación cuando un usuario es eliminado:

| Relación | Comportamiento | Consecuencia práctica |
|---|---|---|
| `Ticket.creado_por` | **PROTECT** | No se puede eliminar al usuario si tiene tickets creados |
| `Ticket.asignado_a` | SET_NULL | El ticket sobrevive; el campo queda vacío |
| `ValidacionGuardia.guardia` | **PROTECT** | No se puede eliminar si hizo validaciones |
| `RegistroMantencion.tecnico` | **PROTECT** | No se puede eliminar si hizo mantenciones |
| `AsignacionTicket.usuario` | **PROTECT** | No se puede eliminar si tiene asignaciones activas |
| `HistorialAcciones.usuario` | SET_NULL | El historial sobrevive sin referencia al actor |
| `LogAuditoria.usuario` | SET_NULL | El log sobrevive sin referencia al actor |
| `Notificacion.destinatario` | CASCADE | Las notificaciones del usuario se eliminan con él |

**Conclusión práctica:** si un usuario participó operativamente en el sistema (creó tickets, hizo validaciones o mantenciones), Django **impide su eliminación** a nivel de base de datos. El intento falla con un error de integridad referencial (`ProtectedError`). El camino correcto es **suspender la cuenta**, no eliminarla.

### Qué pasa si se borra desde Auth0 pero no desde Django

Si se elimina un usuario directamente desde el dashboard de Auth0 (sin usar `limpiar_cuentas`):
- Auth0 lo elimina → el usuario no puede iniciar sesión
- Django conserva su registro → sus tickets, historial y logs quedan intactos
- El webhook registra en `LogAuditoria`: "Usuario eliminado de Auth0"
- El campo `auth0_sub` en Django queda como un identificador huérfano

Esto **no es un error crítico** para el sistema. La fuente de verdad de los datos operativos es Django; Auth0 es solo el proveedor de autenticación. Un usuario sin Auth0 simplemente no puede ingresar, pero sus datos están preservados.

El problema práctico: si después se ejecuta `sincronizar_auth0`, ese usuario ya no aparece en Auth0 y no se reimporta. El registro Django queda con `auth0_sub` apuntando a algo que ya no existe. Para evitarlo, siempre usar `limpiar_cuentas --auth0` en lugar de borrar manualmente desde el dashboard.

---

## 9. Sincronía entre Auth0 y SQLite

### Estado actual de la sincronización

El sistema ya tiene cuatro puentes entre Auth0 y Django:

| Acción | Dirección | Estado |
|---|---|---|
| Registro de cuenta | Django → Auth0 | Implementado: crea usuario en Auth0 |
| Aprobación de cuenta | Django → Auth0 | Implementado: actualiza rol en app_metadata |
| Logout | Django → Auth0 | Implementado: revoca sesiones activas |
| Login | Auth0 → Django | Implementado: vincula auth0_sub automáticamente |

### Qué no está sincronizado (Auth0 → Django)

| Acción en Auth0 | ¿Qué pasa en Django? | Registrado en auditoría |
|---|---|---|
| Cambio de contraseña | Nada (Django no guarda contraseñas) | Sí, via webhook (`scp`) |
| Eliminación de usuario | Django conserva el registro | Sí, via webhook (`sdu`) |
| Bloqueo manual | Django no lo refleja | Sí, via webhook (`limit_wc`) |
| Cambio de email | Django conserva el email original | Sí, via webhook (`sce`) |

### ¿Se puede lograr sincronía total?

Técnicamente sí, pero con diferente complejidad según la acción:

**Eliminación (sdu) → marcar como inactivo en Django:**
Baja complejidad. Cuando el webhook recibe `sdu`, se puede marcar `is_active=False` y `estado_cuenta='suspendida'` en Django. Esto sincroniza el estado sin perder los datos.

**Cambio de email (sce) → actualizar correo en Django:**
Complejidad media. El webhook no incluye el nuevo email en el payload; habría que hacer una llamada adicional a la Management API para obtenerlo. Es posible pero agrega una dependencia extra.

**Cambio de contraseña (scp) → ningún cambio en Django:**
No hay nada que sincronizar. Django no almacena contraseñas cuando Auth0 está activo. El cambio es completamente interno a Auth0.

**Bloqueo en Auth0 → suspender en Django:**
Baja complejidad. Similar a la eliminación: cuando llega el evento de bloqueo, marcar `estado_cuenta='suspendida'` en Django.

### Recomendación para el proyecto

Para el alcance del Sprint actual, el nivel de sincronía implementado es suficiente. El webhook cubre la auditoría. Si se requiere sincronía más estricta en el futuro, el cambio de mayor impacto con menor complejidad es: **cuando Auth0 elimina un usuario (`sdu`), Django lo suspende automáticamente**. Eso elimina el riesgo del "usuario fantasma" y es una adición de pocas líneas de código.

---

## 10. Archivos del Proyecto Relacionados

| Archivo | Descripción |
|---|---|
| `campus_seguro/settings.py` | Configuración Django con soporte para proxy/ngrok |
| `.env` | Variables de entorno locales (no va a git) |
| `.env.example` | Plantilla documentada con sección ngrok |
| `app/management/commands/crear_gestor.py` | Crea el gestor en BD nueva |
| `app/management/commands/sincronizar_auth0.py` | Importa usuarios de Auth0 a BD local |
| `app/management/commands/limpiar_cuentas.py` | Limpia cuentas de prueba |
| `app/views.py` (login_view) | Vincula `auth0_sub` en primer login (línea 179) |
| `app/auth0_service.py` | Capa de comunicación con Auth0 API |
