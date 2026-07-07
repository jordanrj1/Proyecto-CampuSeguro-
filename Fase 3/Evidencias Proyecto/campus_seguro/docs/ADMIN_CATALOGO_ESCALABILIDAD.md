# Administración, Catálogos y Escalabilidad — Campus Seguro

> **Sesión:** Junio 2026  
> **Responsable:** Jordan García  
> **Rama:** Jordan  
> **Propósito del documento:** Registrar las decisiones de arquitectura tomadas para hacer el sistema
> configurable y escalable sin tocar código, documentar la capa de administración implementada,
> explicar la coexistencia de Auth0 y Django Admin, y dejar trazabilidad de todo lo que
> estaba hardcodeado y cómo se resolvió.

---

## Índice

1. [El problema: datos hardcodeados](#1-el-problema-datos-hardcodeados)
2. [La solución: EstadoCatalogo como motor de catálogos](#2-la-solución-estadocatalogo-como-motor-de-catálogos)
3. [Qué se migró a la base de datos](#3-qué-se-migró-a-la-base-de-datos)
4. [La capa de administración Django Admin](#4-la-capa-de-administración-django-admin)
5. [Auth0 y Django Admin: por qué coexisten y no interfieren](#5-auth0-y-django-admin-por-qué-coexisten-y-no-interfieren)
6. [Setup automático en nuevos entornos](#6-setup-automático-en-nuevos-entornos)
7. [Simplificación de roles: eliminación de enc_seguridad](#7-simplificación-de-roles-eliminación-de-enc_seguridad)
8. [Cómo escalar el sistema desde ahora](#8-cómo-escalar-el-sistema-desde-ahora)
9. [Archivos modificados en esta sesión](#9-archivos-modificados-en-esta-sesión)

---

## 1. El problema: datos hardcodeados

### Qué es un dato hardcodeado

Un dato hardcodeado es un valor que vive directamente en el código Python, no en la base de datos.
En Django, el patrón más común es `CharField(choices=[...])`:

```python
# Ejemplo de hardcodeo — los valores solo existen en el código
URGENCIA_CHOICES = [
    ('baja',    'Baja'),
    ('media',   'Media'),
    ('alta',    'Alta'),
    ('critica', 'Crítica'),
]
urgencia = models.CharField(max_length=20, choices=URGENCIA_CHOICES)
```

### Por qué es un problema

| Consecuencia | Impacto |
|---|---|
| Para agregar una nueva opción hay que editar código | El gestor o admin no puede hacerlo solo — necesita un desarrollador |
| En un entorno nuevo los dropdowns quedan vacíos | Mala experiencia y errores en formularios |
| Si el equipo necesita ajustar una etiqueta ("Alta" → "Urgente") requiere deploy | No escalable en producción |
| Las ubicaciones (edificios, pisos, salas) estaban en `_preparar_contexto_ubicaciones` sin BD | En un entorno nuevo la tabla `Ubicacion` estaba vacía — los dropdowns de crear ticket no mostraban nada |

### Inventario de lo que estaba hardcodeado

Antes de esta sesión, los siguientes datos solo existían en código Python:

| Dato | Lugar en el código | Impacto visible |
|------|--------------------|-----------------|
| Niveles de urgencia (baja/media/alta/crítica) | `Ticket.URGENCIA_CHOICES` en `models.py` | Dropdown en crear ticket sin datos al migrar |
| Razones de pausa de ticket | `Ticket.PAUSA_CHOICES` en `models.py` | Formulario pausar ticket no escalable |
| Criticidad de no reparable | `NoReparable.CRITICIDAD_CHOICES` en `models.py` | Formulario no reparable no escalable |
| Motivos de inasistencia | `Inasistencia.MOTIVO_CHOICES` en `models.py` | Formulario inasistencia no escalable |
| Ubicaciones (Edificio E y H) | Lógica en `_preparar_contexto_ubicaciones()` | Tabla `Ubicacion` vacía en nuevo entorno |

---

## 2. La solución: EstadoCatalogo como motor de catálogos

### Arquitectura de la solución

`EstadoCatalogo` ya existía como el motor de estados del sistema (estados de ticket, cuenta, etc.).
Se extendió su uso para ser también el motor de catálogos de opciones de formulario.

La estrategia es: **cada tipo de choice se convierte en una `entidad` dentro de `EstadoCatalogo`**.
Los formularios leen de la BD en lugar del código. Si la BD está vacía (entorno nuevo), el sistema
cae automáticamente al `CHOICES` del modelo Python como fallback — sin romper nada.

```
                    ┌─────────────────────────────┐
                    │      EstadoCatalogo          │
                    │                              │
                    │  entidad = 'urgencia_ticket' │
                    │  codigo  = 'baja'            │
                    │  nombre_display = 'Baja'     │
                    │  orden = 1                   │
                    │  color_hex = '#28a745'       │
                    └─────────────┬───────────────┘
                                  │ lee
                    ┌─────────────▼───────────────┐
                    │        Form.__init__()       │
                    │                              │
                    │  db = EstadoCatalogo         │
                    │       .filter(entidad=...)   │
                    │  self.fields['x'].choices    │
                    │    = db or MODEL_CHOICES     │  ← fallback si BD vacía
                    └─────────────────────────────┘
```

### Patrón implementado en formularios

Cada formulario afectado recibió un método `__init__` que hace el override de choices:

```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    db = list(
        EstadoCatalogo.objects
        .filter(entidad='urgencia_ticket', activo=True)
        .order_by('orden')
        .values_list('codigo', 'nombre_display')
    )
    self.fields['urgencia'].choices = db or Ticket.URGENCIA_CHOICES
```

**Ventaja clave:** No requiere migración de base de datos. El campo del modelo sigue siendo
`CharField(max_length=20)` — solo cambia quién llena el dropdown.

---

## 3. Qué se migró a la base de datos

### Catálogos nuevos en EstadoCatalogo

Se agregaron 18 registros nuevos en `poblar_sistema.py`:

#### `urgencia_ticket` — 4 registros

| codigo | nombre_display | color |
|--------|---------------|-------|
| baja | Baja | #28a745 (verde) |
| media | Media | #ffc107 (amarillo) |
| alta | Alta | #fd7e14 (naranja) |
| critica | Crítica | #dc3545 (rojo) |

#### `pausa_ticket` — 4 registros

| codigo | nombre_display |
|--------|---------------|
| material | Aprobación de materiales |
| personal | Personal técnico |
| nivel_mayor | Peritaje (análisis técnico) |
| externalizacion | Requiere externalización |

#### `criticidad` — 4 registros

| codigo | nombre_display |
|--------|---------------|
| baja | Baja |
| media | Media |
| alta | Alta |
| critica | Crítica |

#### `motivo_inasistencia` — 5 registros

| codigo | nombre_display |
|--------|---------------|
| enfermedad | Enfermedad |
| permiso | Permiso Administrativo |
| capacitacion | Capacitación |
| vacaciones | Vacaciones |
| otro | Otro |

### Ubicaciones del campus

Se implementó `Ubicacion.crear_default_campus()` y se ejecutó, resultando en **217 registros**:

| Edificio | Pisos | Salas por piso | Total |
|----------|-------|----------------|-------|
| Edificio E | 1–5 | 16 aulas + baño | 81 ubicaciones |
| Edificio H | 1–8 | 16 aulas + baño | 136 ubicaciones |

Estas ubicaciones ya aparecen en los dropdowns de crear ticket sin configuración adicional.

### Formularios actualizados

| Formulario | Campo afectado | Entidad en BD |
|-----------|---------------|---------------|
| `CrearTicketForm` (vía contexto) | `urgencia` | `urgencia_ticket` |
| `PausaForm` | `razones_pausa` | `pausa_ticket` |
| `NoReparableForm` | `criticidad` | `criticidad` |
| `InasistenciaForm` | `motivo` | `motivo_inasistencia` |

---

## 4. La capa de administración Django Admin

### Por qué se creó esta capa

Antes de esta sesión, el sistema no tenía un perfil ni interfaz para que alguien
gestionara la configuración del sistema de forma autónoma. Todas las opciones de
catálogo, ubicaciones, categorías y especialidades solo podían modificarse tocando código.

La decisión fue implementar **Django Admin como capa de configuración**, donde el administrador
del sistema puede gestionar todo lo que los 4 roles de la app van a encontrar cuando la usen.

### Responsabilidades del Admin

| Área | Qué puede gestionar |
|------|---------------------|
| **Campus** | Edificios, pisos, salas — agregar nuevas ubicaciones sin código |
| **Catálogos** | Estados de ticket/cuenta/asignación, urgencias, motivos, criticidad |
| **Categorías** | Categorías de ticket y de material |
| **Especialidades** | Crear especialidades técnicas, asignarlas a usuarios y materiales |
| **Inventario** | Materiales del pañol: código, nombre, unidad, categoría |
| **Usuarios** | Ver y editar roles, RUT, datos institucionales, especialidades |
| **Tickets** | Vista de auditoría — ver estado de tickets en curso |
| **Auditoría** | LogAuditoria e HistorialAcciones — solo lectura, registro de acciones |
| **Notificaciones** | Marcar como leídas o archivar en bloque |

### Modelos registrados y su propósito

```
Django Admin
│
├── CONFIGURACIÓN DEL CAMPUS
│   └── Ubicacion .............. Edificios/pisos/salas. Botón "Poblar campus"
│
├── CATÁLOGOS
│   ├── CategoriaTicket ........ Tipos de problema reportable
│   ├── CategoriaMaterial ...... Tipos de material del pañol
│   ├── Especialidad ........... Áreas técnicas (electricidad, plomería, etc.)
│   ├── EstadoCatalogo ......... Motor de estados + catálogos de opciones
│   └── TransicionEstado ....... Qué rol puede mover qué estado
│
├── INVENTARIO
│   └── Material ............... Stock del pañol con especialidades
│
├── USUARIOS
│   ├── Usuario ................ Roles, datos institucionales, especialidades
│   └── TokenRecuperacion ...... Solo lectura — generados por el sistema
│
├── TICKETS Y OPERACIONES
│   ├── Ticket ................. Vista de auditoría
│   ├── AsignacionTicket ....... Quién tiene asignado qué
│   ├── ValidacionGuardia ...... Resultados de inspección en terreno
│   ├── SesionTrabajo .......... Sesiones con materiales inlineados
│   ├── RegistroMantencion ..... Cierres técnicos
│   ├── NoReparable ............ Declaraciones de no reparabilidad
│   ├── MaterialUtilizado ...... Auditoría de consumo — solo lectura
│   └── MaterialesFaltantes .... Solicitudes de materiales
│
├── RECURSOS HUMANOS
│   └── Inasistencia ........... Registro de ausencias del personal técnico
│
├── NOTIFICACIONES
│   └── Notificacion ........... Con acciones masivas: leer / archivar
│
└── AUDITORÍA (solo lectura)
    ├── LogAuditoria ........... No se puede agregar ni editar
    └── HistorialAcciones ...... No se puede agregar ni editar
```

### Funcionalidad especial: botón "Poblar campus"

`UbicacionAdmin` tiene una URL adicional (`/admin/app/ubicacion/poblar-campus-default/`)
accesible mediante un botón en el listado. Llama a `Ubicacion.crear_default_campus()`
que siembra Edificio E y H idempotentemente (no duplica si ya existen).

Esto permite que en un entorno nuevo el administrador pueble el campus
con un solo clic desde la interfaz, sin línea de comandos.

---

## 5. Auth0 y Django Admin: por qué coexisten y no interfieren

### La pregunta

> "Si tengo Django Admin y Auth0, en ambas se muestran usuarios y acciones.
> ¿Para qué tengo las dos? ¿No es redundante?"

### La respuesta: operan en capas distintas

No son dos sistemas haciendo lo mismo. Cada uno resuelve un problema diferente
en una capa diferente del sistema:

```
┌─────────────────────────────────────────────────────────────┐
│  CAPA DE IDENTIDAD — Auth0 (nube)                           │
│                                                             │
│  Responde: ¿quién eres tú?                                  │
│  Responsabilidad: verificar credenciales, emitir tokens     │
│  Usuarios: todos (usuario, gestor, guardia, mantencion)     │
│  Contraseña: guardada en la nube de Auth0                   │
└─────────────────────────┬───────────────────────────────────┘
                          │ token JWT
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  CAPA DE APLICACIÓN — Django + SQLite                       │
│                                                             │
│  Responde: ¿qué puede hacer este usuario en el sistema?     │
│  Responsabilidad: roles, tickets, ubicaciones, catálogos    │
│  Usuarios: sus datos institucionales (RUT, rol, sede)       │
└─────────────────────────┬───────────────────────────────────┘
                          │ datos de configuración
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  CAPA DE CONFIGURACIÓN — Django Admin                       │
│                                                             │
│  Responde: ¿cómo está configurado el sistema?               │
│  Responsabilidad: catálogos, ubicaciones, materiales        │
│  Usuarios: solo el administrador técnico                    │
│  Contraseña: contraseña local Django (independiente)        │
└─────────────────────────────────────────────────────────────┘
```

### Tabla comparativa

| | Auth0 | Django Admin |
|--|-------|-------------|
| **¿Qué gestiona?** | Identidad y autenticación | Datos de configuración del sistema |
| **¿Quién lo usa?** | Todos los usuarios de la app | Solo el administrador técnico |
| **URL** | `/login/` (redirige a Auth0) | `/admin/` |
| **Contraseña** | Almacenada en la nube de Auth0 | Contraseña local Django (`CampusAdmin2024!`) |
| **Sesión generada** | Cookie de la app Django | Cookie de admin (separada) |
| **Si se elimina** | Hay que construir auth desde cero (hash, reset email, MFA, tokens) | Hay que construir vistas CRUD para cada catálogo |

### Por qué no interfieren

Tienen sesiones completamente separadas. Un usuario puede:
- Estar logueado en la app (via Auth0) y **no** en Django Admin
- Estar logueado en Django Admin y **no** en la app

El campo `auth0_sub` en el modelo `Usuario` es el único puente:
cuando alguien se autentica en Auth0, Django busca localmente ese `sub`
y carga el perfil de aplicación. Cada sistema hace lo suyo sin pisar al otro.

### Por qué no se puede eliminar ninguno de los dos

**Si eliminas Auth0:**
- Habría que construir desde cero: hash de contraseñas, reset por email, bloqueo
  por intentos fallidos, compatibilidad OAuth, protección contra fuerza bruta.
- Son meses de trabajo de seguridad que Auth0 entrega resuelto y auditado.

**Si eliminas Django Admin:**
- No habría forma de gestionar categorías, ubicaciones, catálogos, especialidades
  o materiales sin modificar código y hacer deploy.
- El sistema perdería toda su escalabilidad operativa.

### La defensa en una frase

> Auth0 resuelve el *quién* con estándares de seguridad de industria.
> Django Admin resuelve el *qué configura el sistema* con control total local.
> Son capas distintas; eliminar cualquiera obliga a construir desde cero lo que el otro ya provee.

---

## 6. Setup automático en nuevos entornos

### El problema anterior

Clonar el repositorio y levantar el servidor requería ejecutar varios comandos adicionales:
`poblar_sistema`, `crear_gestor`, y un script manual en el shell para activar permisos de admin.
Cualquier integrante que olvidara un paso tenía el sistema incompleto.

### La solución: señal `post_migrate`

Se implementó una señal `post_migrate` en `app/apps.py` que se dispara
**automáticamente** después de que `python manage.py migrate` completa.

```python
# app/apps.py
class AppConfig(AppConfig):
    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(_setup_inicial, sender=self)

def _setup_inicial(sender, **kwargs):
    # Si BD vacía → poblar_sistema (estados, catálogos, ubicaciones)
    # Si no hay superusuario → crear gestor@duocuc.cl con permisos admin
```

### Comportamiento

| Estado de la BD | Qué hace `_setup_inicial` |
|-----------------|--------------------------|
| BD vacía (entorno nuevo) | Ejecuta `poblar_sistema` + crea el gestor admin |
| BD con datos (segundo `migrate`, nuevas migraciones) | No hace nada — es idempotente |
| Error durante migraciones tempranas (tablas no existen aún) | Captura la excepción silenciosamente — no interrumpe |

### Flujo completo en entorno nuevo

```bash
git clone <repo>
pip install -r requirements.txt
python manage.py migrate      # ← esto hace TODO: tablas + catálogos + gestor admin
python manage.py runserver
```

Después de `migrate`, sin comandos adicionales:
- 50+ estados de catálogo sembrados
- 217 ubicaciones del campus creadas (Edificio E y H)
- Gestor admin creado con acceso a `/admin/`

### Credenciales de Django Admin (auto-creadas)

| Campo | Valor |
|-------|-------|
| URL | `http://localhost:8000/admin/` |
| Usuario | `gestor@duocuc.cl` |
| Contraseña | `CampusAdmin2024!` |

> Esta contraseña es **solo para `/admin/`**. El login de la app (`/login/`) sigue usando Auth0.

---

## 7. Simplificación de roles: eliminación de enc_seguridad

### Decisión

El rol `enc_seguridad` (Encargado de Seguridad) fue eliminado del sistema porque no estaba
siendo utilizado en ningún flujo activo de la aplicación. Mantenerlo generaba ruido en los
selectores de rol y en el código de autenticación.

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `app/models.py` | Eliminado de `ROL_CHOICES` en `Usuario` y `TransicionEstado` |
| `app/auth0_service.py` | Eliminado de `roles_validos`, del docstring de mapeo y de la detección por email |
| `app/management/commands/sincronizar_auth0.py` | Eliminado de `_ROLES_VALIDOS` |

### Roles activos tras el cambio

| Código | Display | Dashboard |
|--------|---------|-----------|
| `usuario` | Usuario Base | `/dashboard/` |
| `gestor` | Gestor | `/gestor/` |
| `guardia` | Guardia | `/guardia/` |
| `mantencion` | Mantención | `/mantencion/dashboard/` |

> **Nota sobre migraciones:** La eliminación de un choice en Django **no requiere migración**.
> El campo `rol` es un `VARCHAR(20)` sin restricción en la BD — Django solo valida choices
> a nivel de formulario, no a nivel de base de datos. El archivo `0001_initial.py` no se tocó;
> es registro histórico y su contenido no afecta el funcionamiento actual.

---

## 8. Cómo escalar el sistema desde ahora

Con la arquitectura implementada, el administrador puede escalar el sistema sin modificar código:

### Agregar una nueva urgencia

1. Ir a `http://localhost:8000/admin/`
2. Estado Catálogo → Agregar
3. Completar: `entidad = urgencia_ticket`, `codigo = urgente`, `nombre_display = Urgente`, `orden = 5`
4. Guardar → aparece automáticamente en el dropdown de crear ticket

### Agregar una nueva sala o edificio

1. Ir a Ubicaciones → Agregar
2. Completar edificio, piso, sala, tipo
3. Guardar → aparece en el cascade de crear ticket

### Agregar una nueva categoría de ticket

1. Ir a Categorías de Ticket → Agregar
2. Completar código y nombre
3. Guardar → aparece en el dropdown de categoría

### Agregar un nuevo motivo de inasistencia

1. Ir a Estado Catálogo → Agregar
2. `entidad = motivo_inasistencia`, completar codigo y nombre_display
3. Guardar → aparece en el formulario de inasistencia

### Agregar una nueva especialidad técnica

1. Ir a Especialidades → Agregar
2. Crear especialidad
3. Ir al usuario técnico → asignarle la especialidad vía inline

### Agregar un nuevo material al pañol

1. Ir a Materiales → Agregar
2. Completar código, nombre, categoría, unidad
3. Guardar → disponible en sesiones de trabajo

---

## 9. Archivos modificados en esta sesión

| Archivo | Tipo de cambio |
|---------|---------------|
| `app/admin.py` | Nuevo — registro completo de todos los modelos con `ModelAdmin` apropiado |
| `app/apps.py` | Nuevo — señal `post_migrate` para setup automático |
| `app/forms.py` | Modificado — `__init__` override en `NoReparableForm`, `PausaForm`, `InasistenciaForm` |
| `app/views.py` | Modificado — `_preparar_contexto_ubicaciones` pasa urgencias desde BD; `gestor_tickets` y `pausar_ticket` usan BD |
| `app/models.py` | Modificado — `enc_seguridad` eliminado de ambos `ROL_CHOICES` |
| `app/auth0_service.py` | Modificado — `enc_seguridad` eliminado de roles válidos y detección por email |
| `app/management/commands/sincronizar_auth0.py` | Modificado — `enc_seguridad` eliminado de `_ROLES_VALIDOS` |
| `app/management/commands/poblar_sistema.py` | Modificado — 18 nuevas entradas en `ESTADOS_INICIALES` + seeding de `Ubicacion` |
| `app/templates/app/crear_ticket.html` | Modificado — urgencia select usa variable de contexto `urgencias` en lugar de `form.fields` |
| `app/templates/admin/app/ubicacion/change_list.html` | Nuevo — botón "Poblar campus" en changelist de ubicaciones |

---

*Documento generado en la sesión de Junio 2026. Responsable: Jordan García.*
