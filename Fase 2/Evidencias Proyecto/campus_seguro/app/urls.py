from django.urls import path
from . import views
from . import vistas_nuevas  # BUG-04: conectar vistas mejoradas

app_name = 'app'

urlpatterns = [
    # ── AUTH ──────────────────────────────────────────
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('registro/', views.registro_view, name='registro'),
    path('olvide-contrasena/', views.olvide_contrasena_view, name='olvide_contrasena'),
    path('restablecer/<str:token>/', views.restablecer_contrasena_view, name='restablecer_contrasena'),

    # ── DASHBOARD ─────────────────────────────────────
    path('dashboard/', views.dashboard, name='dashboard'),

    # ── PERFIL ────────────────────────────────────────
    path('perfil/', views.mi_perfil, name='mi_perfil'),
    path('perfil/cambiar-password/', views.cambiar_password, name='cambiar_password'),

    # ── USUARIO: TICKETS ──────────────────────────────
    path('tickets/', views.mis_tickets, name='mis_tickets'),
    path('tickets/crear/', views.crear_ticket, name='crear_ticket'),
    path('tickets/<int:pk>/', views.detalle_ticket, name='detalle_ticket'),
    path('tickets/<int:pk>/editar/', views.editar_ticket, name='editar_ticket'),
    path('tickets/<int:pk>/eliminar/', views.eliminar_ticket, name='eliminar_ticket'),

    # ── GESTOR: TICKETS ───────────────────────────────
    path('gestor/tickets/', views.gestor_tickets, name='gestor_tickets'),
    path('gestor/tickets/<int:pk>/derivar/', views.derivar_ticket, name='derivar_ticket'),
    path('gestor/tickets/<int:pk>/reasignar/', views.reasignar_ticket, name='reasignar_ticket'),
    path('gestor/tickets/<int:pk>/pausar/', views.pausar_ticket, name='pausar_ticket'),
    path('gestor/tickets/<int:pk>/reactivar/', views.reactivar_ticket, name='reactivar_ticket'),
    path('gestor/tickets/<int:pk>/cerrar/', views.cerrar_ticket, name='cerrar_ticket'),

    # ── GESTOR: CUENTAS / USUARIOS ────────────────────
    path('gestor/solicitudes/', views.gestor_solicitudes_cuenta, name='gestor_solicitudes_cuenta'),
    path('gestor/solicitudes/<int:pk>/revisar/', views.aprobar_cuenta, name='aprobar_cuenta'),
    path('gestor/usuarios/', views.gestor_usuarios, name='gestor_usuarios'),
    path('gestor/usuarios/<int:pk>/suspender/', views.suspender_usuario, name='suspender_usuario'),
    path('gestor/usuarios/<int:pk>/reset/', views.reset_usuario_gestor, name='reset_usuario_gestor'),

    # ── GESTOR: BI / OPERATIVO ────────────────────────
    path('gestor/operativo/', views.gestor_operativo, name='gestor_operativo'),
    path('gestor/bi/', views.gestor_bi, name='gestor_bi'),

    # ── GESTOR: MATERIALES ────────────────────────────
    path('gestor/materiales/', views.materiales_listado, name='materiales_listado'),
    path('gestor/materiales/nuevo/', views.material_form, name='material_nuevo'),
    path('gestor/materiales/<int:pk>/editar/', views.material_form, name='material_editar'),

    # ── GESTOR: INASISTENCIAS ─────────────────────────
    path('gestor/inasistencias/', views.gestor_inasistencias, name='gestor_inasistencias'),
    path('gestor/inasistencias/<int:pk>/revisar/', views.revisar_inasistencia, name='revisar_inasistencia'),

    # ── GUARDIA ───────────────────────────────────────
    path('guardia/validar/<int:pk>/', views.validar_ticket, name='validar_ticket'),

    # ── MANTENCIÓN ────────────────────────────────────
    path('mantencion/<int:pk>/tomar/', views.tomar_trabajo, name='tomar_trabajo'),
    path('mantencion/<int:pk>/completar/', views.completar_mantencion, name='completar_mantencion'),
    path('mantencion/<int:pk>/no-reparable/', views.marcar_no_reparable, name='no_reparable'),

    # ── INASISTENCIAS (operativos) ───────────────────
    path('inasistencia/registrar/', views.registrar_inasistencia, name='registrar_inasistencia'),

    # ── NOTIFICACIONES ────────────────────────────────
    path('notificaciones/', views.notificaciones, name='notificaciones'),
    path('notificaciones/<int:pk>/<str:accion>/', views.notif_accion, name='notif_accion'),
    path('notificaciones/marcar-todas/', views.marcar_todas_leidas, name='marcar_todas_leidas'),

    # ── GESTOR: VINCULAR ACTIVOS ──────────────────────
    path('gestor/tickets/<int:pk>/vincular-activo/', views.vincular_activo_ticket, name='vincular_activo'),
    # historial: vistas_nuevas amplía permisos (creador + asignado pueden ver, no solo gestor)
    path('gestor/tickets/<int:pk>/historial/', vistas_nuevas.historial_acciones_ticket, name='historial_acciones'),

    # ── MANTENCIÓN: TRAZABILIDAD ──────────────────────
    path('mantencion/<int:pk>/trazabilidad/', views.trazabilidad_ticket, name='trazabilidad_ticket'),
    path('mantencion/<int:pk>/registrar-material-faltante/', views.registrar_material_faltante, name='registrar_material_faltante'),

    # ── AUTH0 WEBHOOK ─────────────────────────────────────
    # Recibe eventos de Auth0 Log Streaming (cambios de contrasena, bloqueos, eliminaciones).
    # No requiere login. Valida la request con AUTH0_WEBHOOK_SECRET del .env.
    # Los eventos se guardan en LogAuditoria (modulo='cuenta', es_interno=True).
    # Configuracion en Auth0: Monitoring -> Log Streams -> Custom Webhook -> esta URL.
    # Implementacion: views.auth0_webhook() en views.py.
    path('auth0/webhook/', views.auth0_webhook, name='auth0_webhook'),

    # ── GESTOR: DASHBOARD BI v2 ───────────────────────
    path('gestor/dashboard-bi/', views.dashboard_gestor_bi_v2, name='dashboard_gestor_bi_v2'),
    path('gestor/reporte-materiales/', views.reporte_materiales, name='reporte_materiales'),
    path('gestor/reporte-inasistencias/', views.reporte_inasistencias_empleados, name='reporte_inasistencias'),
    path('gestor/reasignar-por-inasistencia/<int:pk>/', views.reasignar_por_inasistencia, name='reasignar_por_inasistencia'),
]
