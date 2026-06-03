# Arquitectura General – Campus Seguro

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Framework web | Django 5.2 (Python 3.13) |
| Base de datos | SQLite (desarrollo) |
| Autenticación externa | Auth0 (OAuth2 / OIDC) |
| Tokens JWT | PyJWT 2.12 |
| Variables de entorno | python-dotenv |
| HTTP a APIs externas | requests 2.34 |
| Imágenes subidas | Pillow (MEDIA_ROOT) |

---

## Estructura de archivos

```
campus_seguro/
├── app/                           # Aplicación principal Django
│   ├── migrations/               # Migraciones de base de datos (0001–0008)
│   ├── templates/app/            # Templates HTML
│   │   ├── login.html            # Página de login
│   │   ├── registro.html         # Formulario de registro (simplificado)
│   │   ├── revisar_cuenta.html   # Panel del gestor para aprobar cuentas
│   │   ├── base.html             # Layout base con sidebar
│   │   ├── dashboard.html        # Dashboard de usuario base
│   │   ├── dashboarddd.html      # Dashboard del gestor
│   │   ├── guardia.html          # Dashboard del guardia
│   │   └── mantencion/           # Templates de mantención
│   ├── static/css/               # Estilos CSS del proyecto
│   ├── models.py                 # Modelos de datos (Usuario, Ticket, etc.)
│   ├── views.py                  # Vistas (controllers)
│   ├── vistas_nuevas.py          # Vistas adicionales (HU-11 a HU-16)
│   ├── forms.py                  # Formularios Django
│   ├── urls.py                   # Rutas URL de la aplicación
│   ├── admin.py                  # Configuración del admin Django
│   ├── auth0_service.py          # [NUEVO] Servicio de integración Auth0
│   └── context_processors.py    # Procesadores de contexto (notificaciones)
│
├── campus_seguro/                # Configuración del proyecto Django
│   ├── settings.py              # Configuración central (lee .env)
│   ├── urls.py                  # URL raíz
│   └── wsgi.py                  # Punto de entrada WSGI
│
├── docs/                         # [NUEVO] Documentación del proyecto
│   ├── ARQUITECTURA_GENERAL.md       # Este archivo
│   ├── AUTH0_CONFIGURACION.md        # Guía técnica para configurar Auth0 (9 pasos)
│   ├── FLUJO_AUTENTICACION.md        # Diagramas de flujo: login, registro, logout, aprobación
│   ├── CAMBIOS_REGISTRO_Y_ROLES.md   # Por qué se eliminó el selector de roles del registro
│   ├── GUIA_AUTH0_PARA_EQUIPO.md     # Qué es Auth0, qué puedes hacer en el dashboard
│   └── SETUP_NUEVO_ENTORNO.md        # Instructivo de instalación para compañeros de equipo
│
├── media/                        # Archivos subidos (imágenes de tickets, etc.)
├── manage.py                    # CLI de Django
├── requirements.txt             # [NUEVO] Dependencias Python
├── .env                         # [NUEVO] Variables de entorno (no en git)
└── .env.example                 # [NUEVO] Plantilla de variables de entorno
```

---

## Modelos de datos

### Usuario (AbstractUser extendido)
```
Usuario
├── id (PK)
├── username (= correo_institucional)
├── first_name, last_name
├── email
├── rol: 'usuario' | 'gestor' | 'guardia' | 'mantencion' | 'enc_seguridad'
├── rut (único)
├── correo_institucional (único)
├── telefono, vinculo, carrera, jornada, sede, departamento
├── especialidad, turno (para guardia/mantención)
├── estado_cuenta → FK EstadoCatalogo (pendiente/activa/suspendida/rechazada)
├── activo (bool)
├── auth0_sub (único, nullable) ← [NUEVO] Vincula con Auth0
├── fecha_registro, fecha_aprobacion
└── aprobado_por → FK self (gestor que aprobó)
```

### Ticket
```
Ticket
├── id (PK)
├── titulo, descripcion
├── categoria: electrico | plomeria | infraestructura | ...
├── urgencia: baja | media | alta | critica
├── estado → FK EstadoCatalogo
├── creado_por → FK Usuario
├── asignado_a → FK Usuario (guardia/mantención)
├── gestor_responsable → FK Usuario
├── ubicacion → FK Ubicacion
├── foto_evidencia (ImageField)
├── id_activo_sap
├── deleted_at (soft delete)
└── created_at, updated_at, cerrado_at
```

### EstadoCatalogo
Tabla central de estados del sistema. Evita hardcodear strings de estado.
```
EstadoCatalogo
├── entidad: ticket | cuenta | asignacion | inasistencia | material_faltante
├── codigo: 'pendiente' | 'activa' | 'enviado' | 'cerrado' | ...
├── nombre_display: 'Pendiente de Aprobación' | ...
├── es_inicial, es_final (bool)
└── color_hex
```

---

## Flujo de un ticket completo

```
Usuario → Crea ticket (estado: 'enviado')
    │
    ▼
Gestor → Revisa → Deriva a Guardia (estado: 'en_validacion')
    │
    ▼
Guardia → Valida en terreno → Marca válido (estado: 'validado')
    │
    ▼
Gestor → Asigna a técnico Mantención (estado: 'en_mantencion')
    │
    ├─ [Técnico completa] → (estado: 'reparado')
    │       │
    │       ▼
    │   Gestor → Cierra ticket (estado: 'cerrado')
    │
    └─ [No reparable] → (estado: 'no_reparado')
            │
            ▼
        Gestor → Escala externamente o cierra
```

---

## Sistema de notificaciones

Cada acción importante genera una `Notificacion`:
- Ticket creado → Notifica a gestores
- Ticket derivado → Notifica a guardia/técnico
- Ticket cerrado → Notifica al creador
- Cuenta aprobada → Notifica al nuevo usuario
- Cuenta rechazada → Notifica al solicitante

El badge de notificaciones en el sidebar se actualiza via `context_processors.py`
(`notificaciones_no_leidas`) que agrega el conteo a todos los templates.

---

## Integración Auth0

```
Campus Seguro Backend
       │
       ├── Login: POST /oauth/token (ROPC flow)
       │          ─────────────────────────────►  Auth0
       │          ◄─────────────────────────────
       │          JWT (access_token + id_token)
       │
       ├── Registro: POST /api/v2/users (Management API)
       │             ──────────────────────────────────►  Auth0
       │             ◄──────────────────────────────────
       │             {user_id: "auth0|66a1b2c3..."}
       │
       ├── Aprobar cuenta: PATCH /api/v2/users/{sub}
       │                   ────────────────────────►  Auth0
       │                   {app_metadata.campus_rol = "guardia"}
       │
       └── Logout: DELETE /api/v2/users/{sub}/sessions
                   + redirect a /v2/logout
```

**Código:** `app/auth0_service.py`  
**Configuración:** `campus_seguro/settings.py` + `.env`  
**Guía:** `docs/AUTH0_CONFIGURACION.md`

---

## Decoradores de control de acceso

```python
@login_required          # Redirige a /login/ si no está autenticado
@rol_requerido('gestor') # Redirige a /dashboard/ si rol incorrecto
def mi_vista(request):
    ...
```

`rol_requerido` está definido en `views.py` y verifica `request.user.rol`.
Los superusuarios (`is_superuser=True`) pasan cualquier verificación de rol.

---

## Registro de auditoría

Cada acción importante se registra en `LogAuditoria`:
```python
LogAuditoria.objects.create(
    usuario=user,
    accion='Inicio de sesión (Auth0)',
    ip_address=get_client_ip(request),
    modulo='cuenta',  # 'cuenta' | 'ticket' | 'sistema'
    detalle='...',    # Información adicional
)
```

El historial de acciones más detallado está en `HistorialAcciones`
(por ticket, con 19 tipos de acción y visibilidad pública/interna).
