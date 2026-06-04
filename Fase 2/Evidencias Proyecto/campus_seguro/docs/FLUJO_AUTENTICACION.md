# Flujo de Autenticación – Campus Seguro

## Resumen

Campus Seguro usa Auth0 como proveedor de identidad externo.
Las contraseñas **nunca se almacenan en la base de datos local**.
Auth0 valida las credenciales y retorna tokens JWT que el sistema usa
para identificar al usuario y conocer su rol.

---

## Flujo 1: Login

### Con Auth0 habilitado (producción)

```
Usuario
  │
  ▼ Abre http://localhost:8000/login/
  │
  │ Ingresa email: jordan@duoc.cl
  │ Ingresa contraseña: ****
  │ Presiona "Iniciar Sesión"
  │
  ▼ views.py → login_view()
  │
  ├─ form = LoginForm(request.POST)
  ├─ form.is_valid() → True
  │
  ▼ settings.AUTH0_ENABLED = True
  │
  ▼ auth0_service.autenticar_usuario(email, password)
  │
  │  POST https://campus-seguro.us.auth0.com/oauth/token
  │  {
  │    "grant_type": "password",
  │    "username": "jordan@duoc.cl",
  │    "password": "****",          ← NUNCA llega a la BD de Campus Seguro
  │    "client_id": "...",
  │    "client_secret": "..."
  │  }
  │
  ├─ [Si credenciales inválidas]
  │     Auth0 retorna: {"error": "invalid_grant"}
  │     Campus Seguro: messages.error("Correo o contraseña incorrectos")
  │     → Renderizar login.html con error
  │
  └─ [Si credenciales válidas]
       Auth0 retorna: {
         "access_token": "...",
         "id_token": "eyJhbGci...",   ← JWT con datos del usuario
         "expires_in": 86400
       }
       │
       ▼ auth0_service.decodificar_token(id_token)
       │
       │  Claims extraídos del JWT:
       │  {
       │    "sub": "auth0|66a1b2c3d4e5",   ← ID único en Auth0
       │    "email": "jordan@duoc.cl",
       │    "https://campus-seguro.app/roles": ["gestor"]
       │  }
       │
       ▼ Usuario.objects.get(correo_institucional="jordan@duoc.cl")
       │
       ├─ [estado_cuenta = 'pendiente'] → warning "Cuenta pendiente"
       ├─ [estado_cuenta = 'suspendida'] → error "Cuenta suspendida"
       ├─ [estado_cuenta = 'rechazada'] → error "Solicitud rechazada"
       │
       └─ [estado_cuenta = 'activa' y activo=True]
             login(request, user)        ← Crea sesión Django
             request.session.set_expiry(0 si no "Recordar")
             LogAuditoria.objects.create(accion='Inicio de sesión (Auth0)')
             │
             ▼ redirect('app:dashboard')
             │
             ▼ dashboard() → router por user.rol
             │
             ├─ rol='usuario'     → dashboard_usuario()  → dashboard.html
             ├─ rol='gestor'      → dashboard_gestor()   → dashboarddd.html
             ├─ rol='guardia'     → dashboard_guardia()  → guardia.html
             └─ rol='mantencion'  → dashboard_mantencion() → mantencion/dashboard.html
```

### Sin Auth0 (fallback desarrollo local)

```
views.py → login_view()
  │
  ▼ settings.AUTH0_ENABLED = False
  │
  ▼ authenticate(request, username=username, password=password)
  │  (Django auth estándar, usa contraseña hasheada en BD local)
  │
  └─ [mismo flujo de verificación de estado y login]
```

---

## Flujo 2: Registro

```
Usuario nuevo
  │
  ▼ Abre http://localhost:8000/registro/
  │
  │ Completa formulario:
  │   - Nombre, Apellido, RUT
  │   - Correo institucional
  │   - Contraseña (mínimo 8 caracteres)
  │   - Vínculo, Jornada, Carrera, Sede
  │
  │ NOTA: NO hay selector de rol (fue eliminado).
  │       El rol lo asigna el gestor al aprobar la cuenta.
  │
  ▼ views.py → registro_view()
  │
  ▼ RegistroUsuarioForm(request.POST).is_valid()
  │
  ├─ [Con Auth0 habilitado]
  │     │
  │     ▼ auth0_service.crear_usuario_auth0(email, password, nombre, apellido)
  │     │
  │     │  POST https://.../api/v2/users
  │     │  {
  │     │    "email": "jordan@duoc.cl",
  │     │    "password": "****",        ← Se envía a Auth0, NO se guarda en BD
  │     │    "connection": "Username-Password-Authentication",
  │     │    "app_metadata": {
  │     │      "campus_rol": "usuario",
  │     │      "campus_estado": "pendiente"
  │     │    }
  │     │  }
  │     │
  │     └─ Auth0 retorna: {"user_id": "auth0|66a1b2c3..."}
  │
  ▼ form.save(auth0_sub="auth0|66a1b2c3...", usar_auth0=True)
  │
  │  Crea Usuario en BD local:
  │    username = correo_institucional
  │    rol = 'usuario'                ← SIEMPRE usuario al registrarse
  │    estado_cuenta = 'pendiente'    ← Requiere aprobación
  │    is_active = False              ← No puede loguearse aún
  │    set_unusable_password()        ← Contraseña NO guardada en BD
  │    auth0_sub = "auth0|66a1b2c3..."
  │
  ▼ notificar_gestores('cuenta_solicitud', ...)
  │
  ▼ messages.success("✓ Solicitud enviada correctamente.")
  │
  ▼ redirect('app:login')
```

---

## Flujo 3: Aprobación por Gestor

```
Gestor
  │
  ▼ Accede a http://localhost:8000/gestor/solicitudes/
  │
  │ Ve la lista de cuentas pendientes
  │
  ▼ Hace clic en "Revisar" de una solicitud
  │
  ▼ http://localhost:8000/gestor/solicitudes/<pk>/revisar/
  │
  │ Ve los datos del solicitante (nombre, correo, vínculo, etc.)
  │ Selecciona el ROL a asignar (radio buttons):
  │   ◉ Usuario Base  ○ Gestor  ○ Guardia  ○ Mantención
  │
  ▼ Hace clic en "✓ Aprobar y asignar rol"
  │
  ▼ views.py → aprobar_cuenta(request, pk)
  │
  ▼ Actualiza Usuario en BD local:
  │    user.rol = 'guardia'          ← El rol que seleccionó el gestor
  │    user.estado_cuenta = 'activa'
  │    user.is_active = True
  │    user.fecha_aprobacion = now()
  │    user.aprobado_por = gestor
  │
  ▼ [Con Auth0 habilitado y auth0_sub disponible]
  │    auth0_service.actualizar_rol_auth0(
  │      auth0_sub = user.auth0_sub,
  │      rol = 'guardia',
  │      estado = 'activa'
  │    )
  │    → PATCH /api/v2/users/auth0|66a1b2c3...
  │      {"app_metadata": {"campus_rol": "guardia", "campus_estado": "activa"}}
  │
  ▼ LogAuditoria: 'Cuenta aprobada con rol: Guardia'
  │
  ▼ Notificación al usuario: "Tu cuenta fue aprobada. Rol: Guardia."
  │
  ▼ Usuario puede iniciar sesión → redirigido a guardia.html
```

---

## Flujo 4: Logout

```
Usuario (autenticado)
  │
  ▼ Hace clic en "Cerrar Sesión"
  │
  ▼ views.py → logout_view()
  │
  ├─ LogAuditoria: 'Cierre de sesión (Auth0)'
  ├─ auth0_sub = user.auth0_sub
  │
  ▼ logout(request)  ← Limpia sesión Django local
  │
  ├─ [Con Auth0 habilitado]
  │     │
  │     ├─ auth0_service.revocar_sesion_auth0(auth0_sub)
  │     │    → DELETE /api/v2/users/{sub}/sessions
  │     │    (invalida sesiones activas en Auth0)
  │     │
  │     └─ auth0_service.construir_url_logout(return_to='http://localhost:8000/login/')
  │          → https://campus-seguro.us.auth0.com/v2/logout?
  │              client_id=xxx&returnTo=http://localhost:8000/login/
  │
  ▼ redirect(auth0_logout_url)
  │
  ▼ Auth0 invalida su cookie de sesión
  │
  ▼ Auth0 redirige a http://localhost:8000/login/
  │
  ▼ Usuario ve la pantalla de login
```

---

## Archivos relacionados

| Archivo | Función |
|---------|---------|
| [app/auth0_service.py](../app/auth0_service.py) | Todas las llamadas a la API de Auth0 |
| [app/views.py](../app/views.py) | Vistas: login_view, logout_view, registro_view, aprobar_cuenta |
| [app/forms.py](../app/forms.py) | LoginForm, RegistroUsuarioForm, AsignarRolForm |
| [app/models.py](../app/models.py) | Modelo Usuario con campo auth0_sub |
| [campus_seguro/settings.py](../campus_seguro/settings.py) | Variables AUTH0_* leídas desde .env |
| [.env.example](./../.env.example) | Plantilla de variables de entorno |
| [docs/AUTH0_CONFIGURACION.md](./AUTH0_CONFIGURACION.md) | Guía de configuración en el dashboard |

---

## Criterios de aceptación (verificación)

| Criterio | Implementado en |
|----------|----------------|
| Usuario ingresa email/contraseña en página de login | `login.html` + `LoginForm` |
| Auth0 valida las credenciales correctamente | `auth0_service.autenticar_usuario()` |
| Usuario se redirige a su panel según su rol | `views.dashboard()` → router por `user.rol` |
| Botón cerrar sesión limpia toda sesión (Auth0 + local) | `logout_view()` + `construir_url_logout()` + `revocar_sesion_auth0()` |
| No se guarda contraseña en BD de Campus Seguro | `form.save(usar_auth0=True)` → `set_unusable_password()` |
