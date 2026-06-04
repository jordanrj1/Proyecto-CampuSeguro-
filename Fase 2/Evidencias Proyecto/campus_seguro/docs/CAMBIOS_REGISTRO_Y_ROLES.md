# Cambios en el Sistema de Registro y Roles – Campus Seguro

## Resumen del cambio

Se modificó el sistema de registro para que los usuarios **no puedan elegir su propio rol**.
El gestor ahora tiene control total: habilita cuentas, las deshabilita, y asigna roles.

---

## ¿Por qué se hizo este cambio?

**Antes:**
- El usuario elegía su rol al registrarse (usuario, gestor, guardia, mantención).
- Esto era un riesgo de seguridad: cualquiera podía solicitar una cuenta como gestor.
- No había control sobre quién tenía acceso a cada panel.

**Después:**
- El registro crea siempre una cuenta como "Usuario Base" (rol='usuario').
- La cuenta queda en estado "pendiente" hasta que el gestor la revise.
- El gestor asigna el rol real al aprobar la cuenta.
- El gestor puede habilitar/deshabilitar cuentas en cualquier momento.

---

## Archivos modificados

### 1. `app/templates/app/registro.html`

**Qué cambió:**
- Se eliminaron los 4 role-cards (usuario, gestor, guardia, mantención).
- El campo oculto `rol` siempre tiene valor `usuario`.
- Se eliminaron las secciones de campos específicos por rol
  (campos de gestor, guardia, mantención).
- Se simplificó a: datos personales + datos académicos + seguridad.
- Se agregó un banner informativo que explica el proceso de aprobación.

**Cómo se ve ahora:**
```
┌─────────────────────────────────────┐
│  🛡️  Campus Seguro  │  ← Volver    │
├─────────────────────────────────────┤
│  Solicitar Acceso                   │
│                                     │
│  ℹ️ Tu cuenta quedará pendiente...  │
│                                     │
│  ── Datos Personales ──────────────│
│  [Nombre]     [Apellido]            │
│  [RUT]        [Teléfono]            │
│  [Correo Institucional]             │
│                                     │
│  ── Datos Académicos ──────────────│
│  [Vínculo]    [Jornada]             │
│  [Carrera]    [Sede]                │
│                                     │
│  ── Seguridad ─────────────────────│
│  [Contraseña] [Confirmar]           │
│                                     │
│  ☐ Acepto las políticas de uso     │
│                                     │
│  [ Enviar Solicitud → ]             │
└─────────────────────────────────────┘
```

---

### 2. `app/templates/app/revisar_cuenta.html`

**Qué cambió:**
- Se agregó el selector de rol en el panel de decisión del gestor.
- El gestor ve los datos del solicitante y elige su rol antes de aprobar.
- Se agregó un aviso sobre la sincronización con Auth0.

**Cómo se ve ahora:**
```
┌───────────────────────────┬──────────────────┐
│  👤 Datos del solicitante │  ⚙️ Decisión     │
│                           │                  │
│  Nombre: Juan Pérez       │  Rol a asignar:  │
│  RUT: 12345678-9          │  ◉ Usuario Base  │
│  Correo: j@duoc.cl        │  ○ Gestor        │
│  Vínculo: Alumno          │  ○ Guardia       │
│  Jornada: Diurna          │  ○ Mantención    │
│  Carrera: Ing. Info       │                  │
│  Sede: Concepción         │  [ ✓ Aprobar ]   │
│  Fecha: 03/06/2026        │  [ ✗ Rechazar ]  │
│                           │                  │
│                           │  🔐 Auth0: rol   │
│                           │  sincronizado    │
└───────────────────────────┴──────────────────┘
```

---

### 3. `app/forms.py`

**Qué cambió en `RegistroUsuarioForm`:**
- Eliminado el campo `rol` de `Meta.fields`.
- En `save()`: siempre establece `rol='usuario'` y `is_active=False`.
- En `save()`: acepta parámetros `auth0_sub` y `usar_auth0`.
  - Si `usar_auth0=True`: llama `set_unusable_password()`.
  - Si no: llama `set_password()` (fallback desarrollo).
- `estado_cuenta` ahora es `'pendiente'` (antes era `'activa'`).

**Nuevo `AsignarRolForm`:**
```python
class AsignarRolForm(forms.Form):
    ROL_CHOICES = [
        ('usuario', 'Usuario Base'),
        ('gestor', 'Gestor'),
        ('guardia', 'Guardia'),
        ('mantencion', 'Mantención'),
    ]
    rol = forms.ChoiceField(choices=ROL_CHOICES, ...)
```

---

### 4. `app/views.py` → `aprobar_cuenta()`

**Qué cambió:**
- Ahora recibe `form_rol = AsignarRolForm(request.POST)`.
- Valida que se haya seleccionado un rol antes de aprobar.
- Asigna `user.rol = form_rol.cleaned_data['rol']`.
- Llama a `auth0_service.actualizar_rol_auth0()` para sincronizar.
- Notifica al usuario con el rol asignado en el mensaje.

---

### 5. `app/models.py` → `Usuario`

**Qué se agregó:**
```python
auth0_sub = models.CharField(
    max_length=120,
    unique=True,
    null=True,
    blank=True,
    verbose_name='Auth0 Subject ID',
)
```

Este campo almacena el ID único del usuario en Auth0 (formato: `auth0|66a1b2c3...`).
Se usa para:
- Sincronizar el rol cuando el gestor aprueba la cuenta.
- Revocar sesiones en Auth0 al hacer logout o suspender cuenta.

---

## Flujo completo del nuevo sistema de roles

```
1. REGISTRO (usuario)
   └─ Llena formulario → rol='usuario', estado='pendiente', is_active=False
   └─ Auth0: usuario creado con app_metadata.campus_rol='usuario'

2. NOTIFICACIÓN (automática)
   └─ Todos los gestores activos reciben notificación

3. REVISIÓN (gestor)
   └─ Panel: /gestor/solicitudes/
   └─ Ve solicitudes pendientes

4. APROBACIÓN (gestor)
   └─ Selecciona rol: ◉ Guardia
   └─ Hace clic en "Aprobar"
   └─ Sistema: user.rol = 'guardia', is_active = True, estado = 'activa'
   └─ Auth0: app_metadata.campus_rol = 'guardia'

5. ACCESO (usuario aprobado)
   └─ Inicia sesión → Auth0 valida credenciales
   └─ Dashboard router → user.rol == 'guardia' → guardia.html

6. GESTIÓN POSTERIOR (gestor)
   └─ Puede suspender: /gestor/usuarios/<pk>/suspender/
   └─ Puede cambiar rol: desde /gestor/usuarios/ (futuro)
```

---

## Lo que NO cambió

- El panel del gestor (`/gestor/solicitudes/`) ya existía y funciona igual.
- Los usuarios existentes en la BD no se ven afectados.
- El sistema de notificaciones al gestor cuando hay solicitudes nuevas funciona igual.
- La lógica de tickets, validaciones y mantención no cambió.

---

## Usuarios existentes en la BD

Los usuarios que ya existen en la BD antes de este cambio:
- Mantienen su rol y estado actuales (no son afectados por la migración).
- Si tienen `is_active=True` y `estado_cuenta='activa'`, pueden seguir logueándose.
- Su campo `auth0_sub` quedará en `NULL` hasta que se vincule con Auth0.
- Pueden autenticarse con la contraseña local
