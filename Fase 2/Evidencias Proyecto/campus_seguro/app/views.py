# ═══════════════════════════════════════════════════════════════
# CAMPUS SEGURO – Vistas principales
# ─────────────────────────────────────────────────────────────
# Archivo: app/views.py
#
# PROPÓSITO:
#   Contiene todas las vistas (controllers) del sistema Campus Seguro.
#   Maneja la lógica de autenticación, gestión de tickets, panel del
#   gestor, guardia, mantención, y recuperación de contraseña.
#
# AUTENTICACIÓN (flujo Auth0):
#   - login_view(): Autentica vía Auth0 ROPC si AUTH0_ENABLED=True,
#     o via Django authenticate() como fallback de desarrollo.
#   - logout_view(): Limpia sesión local + redirige a Auth0 logout.
#   - registro_view(): Crea usuario en Auth0 (si habilitado) y en BD local.
#   - aprobar_cuenta(): Gestor aprueba + asigna rol + sincroniza con Auth0.
#
# MÓDULOS RELACIONADOS:
#   - app/auth0_service.py: Toda la lógica de comunicación con Auth0.
#   - app/forms.py: Formularios (LoginForm, RegistroUsuarioForm, AsignarRolForm).
#   - app/models.py: Modelos de datos (Usuario, Ticket, etc.).
#
# DECORADORES:
#   - @login_required: Requiere usuario autenticado (Django built-in).
#   - @rol_requerido(*roles): Verifica que el usuario tenga el rol correcto.
# ═══════════════════════════════════════════════════════════════
import logging
import json  # ✅ Necesario para serializar ubicaciones a JSON

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Count, Sum, Q, Avg, F
from django.urls import reverse
from datetime import timedelta, datetime
from functools import wraps
from django.conf import settings

from .models import (
    CategoriaMaterial, CategoriaTicket, Especialidad, SesionTrabajo, Usuario, TokenRecuperacion, Ticket, Ubicacion, Material,
    ValidacionGuardia, RegistroMantencion, MaterialUtilizado,
    NoReparable, LogAuditoria, Notificacion, Inasistencia,
    HistorialAcciones, MaterialesFaltantes, EstadoCatalogo, AsignacionTicket
)
from .forms import (
    LoginForm, RegistroUsuarioForm, OlvideContrasenaForm, RestablecerContrasenaForm,
    TicketForm, ValidacionForm, MantencionForm, MaterialUtilizadoFormSet,
    NoReparableForm, PausaForm, ReactivacionForm, DerivarMantencionForm,
    ReasignarForm, InasistenciaForm, MaterialForm,
    VincularActivoForm, MaterialFaltanteForm, AsignarRolForm, EstimarTicketForm
)

# Importación condicional del servicio Auth0.
from . import auth0_service
from .auth0_service import Auth0Error

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')


def registrar_log(ticket, usuario, accion, **kwargs):
    LogAuditoria.objects.create(
        ticket=ticket, usuario=usuario, accion=accion,
        estado_anterior=kwargs.get('estado_anterior'),
        estado_nuevo=kwargs.get('estado_nuevo'),
        ip_address=kwargs.get('ip'),
        es_interno=kwargs.get('es_interno', False),
        detalle=kwargs.get('detalle'),
        modulo=kwargs.get('modulo', 'ticket'),
    )


def notificar(destinatario, tipo, titulo, mensaje, ticket=None, prioridad='media', url_accion=None):
    Notificacion.objects.create(
        destinatario=destinatario, tipo=tipo, titulo=titulo,
        mensaje=mensaje, ticket=ticket, prioridad=prioridad,
        url_accion=url_accion,
    )


def rol_requerido(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('app:login')
            if request.user.rol not in roles and not request.user.is_superuser:
                messages.error(request, 'No tienes permiso para acceder a esta sección.')
                return redirect('app:dashboard')
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def notificar_gestores(tipo, titulo, mensaje, ticket=None, prioridad='media', url_accion=None):
    """Notifica a todos los gestores activos"""
    for gestor in Usuario.objects.filter(rol='gestor', estado_cuenta__codigo='activa', activo=True):
        notificar(gestor, tipo, titulo, mensaje, ticket, prioridad, url_accion)


def _preparar_contexto_ubicaciones():
    """
    Helper que prepara los datos de ubicaciones para el template.
    Retorna un diccionario con:
    - edificios: lista de nombres de edificios únicos
    - ubicaciones_json: JSON con todas las ubicaciones para filtrado en cascada
    """
    ubicaciones = Ubicacion.objects.all().order_by('sede', 'edificio', 'piso', 'sala')
    edificios = Ubicacion.objects.values_list('edificio', flat=True).distinct().order_by('edificio')
    
    ubicaciones_json = json.dumps([
        {
            'id': u.id,
            'edificio': u.edificio,
            'piso': u.piso,
            'sala': u.sala,
            'tipo': u.get_tipo_display()
        }
        for u in ubicaciones
    ])
    
    return {
        'edificios': edificios,
        'ubicaciones_json': ubicaciones_json,
    }


# ═══════════════════════════════════════════════════════════════
# AUTH: LOGIN / LOGOUT / REGISTRO / RECUPERACIÓN
# ═══════════════════════════════════════════════════════════════

def login_view(request):
    if request.user.is_authenticated:
        return redirect('app:dashboard')

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        username_input = form.cleaned_data['username']
        password = form.cleaned_data['password']
        user = None

        if settings.AUTH0_ENABLED:
            try:
                email_para_auth0 = username_input
                try:
                    u_local = Usuario.objects.get(correo_institucional__iexact=username_input)
                    email_para_auth0 = u_local.correo_institucional
                except Usuario.DoesNotExist:
                    pass

                token_data = auth0_service.autenticar_usuario(email_para_auth0, password)
                id_token = token_data.get('id_token')

                if id_token:
                    claims = auth0_service.decodificar_token(id_token)
                    email_auth0 = claims.get('email', '').lower()
                    auth0_sub = claims.get('sub', '')

                    try:
                        user = Usuario.objects.get(correo_institucional__iexact=email_auth0)
                        if not user.auth0_sub and auth0_sub:
                            user.auth0_sub = auth0_sub
                            user.save(update_fields=['auth0_sub'])
                    except Usuario.DoesNotExist:
                        logger.warning(f"Auth0 autenticó a {email_auth0} pero no existe en BD local.")
                        messages.error(request, 'Tu cuenta no está registrada en Campus Seguro. Solicita registro institucional.')
                        return render(request, 'app/login.html', {'form': form})

            except Auth0Error as e:
                if e.code in ('invalid_grant', 'invalid_user_password', 'access_denied'):
                    messages.error(request, 'Correo o contraseña incorrectos.')
                elif e.code == 'connection_error':
                    messages.error(request, 'No se pudo conectar con el servicio de autenticación. Intenta más tarde.')
                else:
                    messages.error(request, f'Error de autenticación: {e.message}')
                return render(request, 'app/login.html', {'form': form})
        else:
            user = authenticate(request, username=username_input, password=password)
            if not user:
                try:
                    u = Usuario.objects.get(correo_institucional__iexact=username_input)
                    user = authenticate(request, username=u.username, password=password)
                except Usuario.DoesNotExist:
                    pass

        if user:
            estado = user.estado_cuenta.codigo
            if estado == 'pendiente':
                messages.warning(request, 'Tu cuenta está pendiente de aprobación por un gestor.')
            elif estado == 'suspendida':
                messages.error(request, 'Tu cuenta está suspendida. Contacta al administrador.')
            elif estado == 'rechazada':
                messages.error(request, 'Tu solicitud de cuenta fue rechazada.')
            elif user.puede_ingresar:
                login(request, user)
                if not form.cleaned_data.get('recordar'):
                    request.session.set_expiry(0)
                LogAuditoria.objects.create(
                    usuario=user,
                    accion='Inicio de sesión' + (' (Auth0)' if settings.AUTH0_ENABLED else ' (local)'),
                    ip_address=get_client_ip(request),
                    modulo='cuenta',
                )
                return redirect('app:dashboard')
        else:
            messages.error(request, 'Correo o contraseña incorrectos.')

    return render(request, 'app/login.html', {'form': form})


def registro_view(request):
    if request.user.is_authenticated:
        return redirect('app:dashboard')

    form = RegistroUsuarioForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        auth0_sub = None
        usar_auth0 = settings.AUTH0_ENABLED

        if usar_auth0:
            try:
                resultado_auth0 = auth0_service.crear_usuario_auth0(
                    email=form.cleaned_data['correo_institucional'],
                    password=form.cleaned_data['password1'],
                    nombre=form.cleaned_data['first_name'],
                    apellido=form.cleaned_data['last_name'],
                )
                auth0_sub = resultado_auth0.get('user_id')
                logger.info(f"Usuario creado en Auth0: {auth0_sub}")
            except Auth0Error as e:
                msg_lower = e.message.lower()
                if 'already exists' in msg_lower or e.code == 'user_exists':
                    messages.error(request, 'Este correo ya tiene una cuenta en el sistema.')
                elif 'password' in msg_lower and ('weak' in msg_lower or 'strength' in msg_lower):
                    messages.error(
                        request,
                        'La contraseña es muy débil. Debe tener mínimo 8 caracteres e incluir '
                        'mayúsculas, minúsculas, números y un carácter especial. '
                        'Ejemplo: Campus2024!'
                    )
                else:
                    messages.error(request, f'Error al crear cuenta: {e.message}')
                return render(request, 'app/registro.html', {'form': form})

        user = form.save(commit=True, auth0_sub=auth0_sub, usar_auth0=usar_auth0)

        LogAuditoria.objects.create(
            usuario=user,
            accion='Solicitud de cuenta creada' + (' (Auth0)' if usar_auth0 else ' (local)'),
            ip_address=get_client_ip(request),
            modulo='cuenta',
        )

        notificar_gestores(
            'cuenta_solicitud',
            f'Nueva solicitud de cuenta: {user.get_full_name()}',
            f'{user.get_full_name()} ({user.correo_institucional}) solicita acceso al sistema.',
            prioridad='alta',
            url_accion=reverse('app:gestor_solicitudes_cuenta'),
        )
        messages.success(
            request,
            '✓ Solicitud enviada correctamente. Un gestor revisará tu cuenta y '
            'recibirás una notificación cuando esté aprobada.'
        )
        return redirect('app:login')

    return render(request, 'app/registro.html', {'form': form})


def olvide_contrasena_view(request):
    form = OlvideContrasenaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        correo = form.cleaned_data['correo']
        try:
            user = Usuario.objects.get(correo_institucional__iexact=correo)
            token = TokenRecuperacion.generar(user, ip=get_client_ip(request))
            link = request.build_absolute_uri(
                reverse('app:restablecer_contrasena', kwargs={'token': token.token})
            )
            messages.success(request, f'✓ Se ha generado un enlace de recuperación. Revisa tu correo institucional.')
            messages.info(request, f'🔗 [DEV] Enlace de recuperación: {link}')
            LogAuditoria.objects.create(
                usuario=user, accion='Solicitud de recuperación de contraseña',
                ip_address=get_client_ip(request), modulo='cuenta'
            )
        except Usuario.DoesNotExist:
            messages.success(request, '✓ Si el correo está registrado, recibirás un enlace de recuperación.')
        return redirect('app:login')

    return render(request, 'app/olvide_contrasena.html', {'form': form})


def restablecer_contrasena_view(request, token):
    try:
        tk = TokenRecuperacion.objects.get(token=token)
    except TokenRecuperacion.DoesNotExist:
        messages.error(request, 'Enlace de recuperación inválido.')
        return redirect('app:login')

    if not tk.es_valido:
        messages.error(request, 'Este enlace ha expirado o ya fue utilizado.')
        return redirect('app:login')

    form = RestablecerContrasenaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        tk.usuario.set_password(form.cleaned_data['password1'])
        tk.usuario.save()
        tk.usado = True
        tk.save()
        LogAuditoria.objects.create(
            usuario=tk.usuario, accion='Contraseña restablecida',
            ip_address=get_client_ip(request), modulo='cuenta'
        )
        messages.success(request, '✓ Contraseña actualizada. Ya puedes iniciar sesión.')
        return redirect('app:login')

    return render(request, 'app/restablecer_contrasena.html', {'form': form, 'usuario': tk.usuario})


def logout_view(request):
    auth0_sub = None
    if request.user.is_authenticated:
        auth0_sub = getattr(request.user, 'auth0_sub', None)
        LogAuditoria.objects.create(
            usuario=request.user,
            accion='Cierre de sesión' + (' (Auth0)' if settings.AUTH0_ENABLED else ' (local)'),
            ip_address=get_client_ip(request),
            modulo='cuenta',
        )

    logout(request)

    if settings.AUTH0_ENABLED:
        if auth0_sub:
            auth0_service.revocar_sesion_auth0(auth0_sub)

        return_to = settings.AUTH0_LOGOUT_RETURN_URL
        auth0_logout_url = auth0_service.construir_url_logout(return_to)
        return redirect(auth0_logout_url)

    return redirect('app:login')


# ═══════════════════════════════════════════════════════════════
# DASHBOARD (router por rol)
# ══════════════════════════════════════════════════════════════
@login_required
def dashboard(request):
    user = request.user
    if user.rol == 'usuario':
        return dashboard_usuario(request)
    elif user.rol == 'gestor' or user.is_superuser:
        return dashboard_gestor(request)
    elif user.rol == 'guardia':
        return dashboard_guardia(request)
    elif user.rol == 'mantencion':
        return dashboard_mantencion(request)
    return render(request, 'app/dashboard.html')


def dashboard_usuario(request):
    user = request.user
    tickets = Ticket.objects.filter(creado_por=user, deleted_at__isnull=True)
    context = {
        'tickets': tickets.order_by('-created_at')[:10],
        'total': tickets.count(),
        'enviados': tickets.filter(estado__codigo='enviado').count(),
        'en_proceso': tickets.filter(estado__codigo__in=['en_proceso', 'en_validacion', 'en_mantencion']).count(),
        'pausados': tickets.filter(estado__codigo='pausado').count(),
        'cerrados': tickets.filter(estado__codigo='cerrado').count(),
    }
    return render(request, 'app/dashboard.html', context)


def dashboard_gestor(request):
    tickets = Ticket.objects.filter(deleted_at__isnull=True)
    hoy = timezone.now().date()
    semana = hoy - timedelta(days=7)

    trabajadores_ausentes = Usuario.objects.filter(
        rol__in=['mantencion', 'guardia'],
        inasistencias__estado__codigo='aprobada',
        inasistencias__fecha_desde__lte=hoy,
        inasistencias__fecha_hasta__gte=hoy,
    ).distinct()

    tickets_con_ausentes = Ticket.objects.filter(
        asignado_a__in=trabajadores_ausentes,
        estado__codigo__in=['en_mantencion', 'en_validacion'],
        deleted_at__isnull=True
    ).select_related('asignado_a')

    reparados_pendientes = tickets.filter(estado__codigo='reparado').select_related('creado_por', 'asignado_a')
    no_reparados_escalados = tickets.filter(estado__codigo='no_reparado').select_related('creado_por', 'asignado_a', 'no_reparable')
    validados_pendientes = tickets.filter(estado__codigo='validado').select_related('creado_por', 'validado_por')

    context = {
        'total_tickets': tickets.count(),
        'activos': tickets.exclude(estado__codigo__in=['cerrado', 'eliminado']).count(),
        'pausados': tickets.filter(estado__codigo='pausado').count(),
        'cerrados': tickets.filter(estado__codigo='cerrado').count(),
        'criticos': tickets.filter(urgencia='critica').exclude(estado__codigo__in=['cerrado', 'eliminado']).count(),
        'no_reparados': tickets.filter(estado__codigo='no_reparado').count(),
        'reparados_pendientes_count': tickets.filter(estado__codigo='reparado').count(),
        'validados_count': tickets.filter(estado__codigo='validado').count(),
        'sin_asignar': tickets.filter(estado__codigo='enviado').count(),
        'tickets_hoy': tickets.filter(created_at__date=hoy).count(),
        'cerrados_semana': tickets.filter(estado__codigo='cerrado', cerrado_at__gte=semana).count(),
        'tickets_recientes': tickets.order_by('-created_at')[:10],
        'tickets_criticos': tickets.filter(urgencia='critica').exclude(estado__codigo__in=['cerrado', 'eliminado']).order_by('-created_at')[:5],
        'reparados_pendientes': reparados_pendientes.order_by('-created_at'),
        'no_reparados_escalados': no_reparados_escalados.order_by('-created_at'),
        'validados_pendientes': validados_pendientes.order_by('-created_at'),
        'por_edificio': list(tickets.values(edificio=F('ubicacion__edificio')).annotate(total=Count('id')).order_by('-total')[:6]),
        'por_categoria': list(tickets.values('categoria__nombre_display').annotate(total=Count('id')).order_by('-total')),
        'por_estado': [{'estado': i['estado__codigo'], 'total': i['total']} for i in tickets.values('estado__codigo').annotate(total=Count('id'))],
        'solicitudes_cuenta': Usuario.objects.filter(estado_cuenta__codigo='pendiente').count(),
        'inasistencias_pendientes': Inasistencia.objects.filter(estado__codigo='pendiente').count(),
        'notif_no_leidas': Notificacion.objects.filter(destinatario=request.user, leida=False, archivada=False).count(),
        'trabajadores_ausentes': trabajadores_ausentes,
        'tickets_con_ausentes': tickets_con_ausentes,
        'pausa_choices': Ticket.PAUSA_CHOICES,
    }
    return render(request, 'app/dashboard_gestor.html', context)


def dashboard_guardia(request):
    """
    Dashboard del Guardia - Muestra validaciones pendientes y asignadas.
    
    CAMBIOS TARJETA 08:
    - Agregar sección "Mis Revisiones Asignadas" (tickets asignados específicamente a este guardia)
    - Filtrar por asignaciones con rol_asignacion='guardia' y estado='pendiente'
    """
    user = request.user
    hoy = timezone.now().date()
    
    # Tickets pendientes de validación general (cualquier guardia puede tomar)
    pendientes = Ticket.objects.filter(estado__codigo='en_validacion', deleted_at__isnull=True)
    
    # Mis validaciones realizadas
    mis_validaciones = ValidacionGuardia.objects.filter(guardia=user)
    
    # ══════════════════════════════════════════════════════════════
    # NUEVO: Mis Revisiones Asignadas (TARJETA 08)
    # Tickets asignados específicamente a este guardia con fecha programada
    # Filtra solo las asignaciones con estado 'pendiente'
    # ═══════════════════════════════════════════════════════════════
    mis_revisiones = AsignacionTicket.objects.filter(
        usuario=user,
        rol_asignacion='guardia',
        estado__codigo='pendiente'
    ).select_related('ticket', 'ticket__ubicacion').order_by('fecha_programada')
    
    context = {
        'pendientes': pendientes.order_by('-urgencia', '-created_at'),
        'pendientes_count': pendientes.count(),
        'mis_validaciones': mis_validaciones.select_related('ticket').order_by('-created_at')[:8],
        'total_validados': mis_validaciones.count(),
        'validos': mis_validaciones.filter(resultado='valido').count(),
        'invalidos': mis_validaciones.filter(resultado='invalido').count(),
        'inasistencias': Inasistencia.objects.filter(usuario=user).order_by('-fecha_desde')[:3],
        # Campos nuevos para TARJETA 08
        'mis_revisiones': mis_revisiones,
        'mis_revisiones_count': mis_revisiones.count(),
    }
    return render(request, 'app/guardia.html', context)


def dashboard_mantencion(request):
    user = request.user
    pendientes = Ticket.objects.filter(
        estado__codigo='en_mantencion', asignado_a=user, deleted_at__isnull=True
    ).select_related('creado_por', 'gestor_responsable')
    completados = RegistroMantencion.objects.filter(tecnico=user)
    no_reparados = NoReparable.objects.filter(tecnico=user)
    hoy = timezone.now().date()
    inasistencia_activa = Inasistencia.objects.filter(
        usuario=user, estado__codigo='aprobada',
        fecha_desde__lte=hoy, fecha_hasta__gte=hoy
    ).first()
    context = {
        'pendientes': pendientes.order_by('-urgencia', '-created_at'),
        'pendientes_count': pendientes.count(),
        'completados_count': completados.count(),
        'no_reparados_count': no_reparados.count(),
        'hh_total': SesionTrabajo.objects.filter(tecnico=user).aggregate(t=Sum('horas_hombre'))['t'] or 0,
        'historial': completados.select_related('ticket').order_by('-fecha_registro')[:8],
        'inasistencias': Inasistencia.objects.filter(usuario=user).order_by('-fecha_desde')[:5],
        'inasistencia_activa': inasistencia_activa,
    }
    return render(request, 'app/mantencion/dashboard.html', context)


# ═══════════════════════════════════════════════════════════════
# USUARIO: TICKETS
# ═══════════════════════════════════════════════════════════════
@login_required
def crear_ticket(request):
    """
    Vista para crear un nuevo ticket de reporte de incidencia.
    
    ✅ CAMBIO CLAVE: Se pasa TicketForm() al contexto para que el template
    pueda acceder a form.fields.categoria.choices y form.fields.urgencia.choices
    """
    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        ubicacion_id = request.POST.get('ubicacion', '').strip()
        categoria = request.POST.get('categoria')
        urgencia = request.POST.get('urgencia', 'media')
        
        afecta_clase = request.POST.get('afecta_clase') == 'on'
        riesgo_electrico = request.POST.get('riesgo_electrico') == 'on'
        riesgo_estructural = request.POST.get('riesgo_estructural') == 'on'
        riesgo_accesibilidad = request.POST.get('riesgo_accesibilidad') == 'on'
        
        # Validaciones básicas
        if not titulo or not descripcion or not ubicacion_id or not categoria:
            messages.error(request, 'Por favor completa todos los campos obligatorios.')
            contexto = _preparar_contexto_ubicaciones()
            contexto['form'] = TicketForm()  # ✅ AGREGADO: Pasar el form
            return render(request, 'app/crear_ticket.html', contexto)
        
        # Validar ubicación
        try:
            ubicacion = Ubicacion.objects.get(id=ubicacion_id)
        except (Ubicacion.DoesNotExist, ValueError):
            messages.error(request, 'La ubicación seleccionada no es válida. Por favor selecciónala nuevamente.')
            contexto = _preparar_contexto_ubicaciones()
            contexto['form'] = TicketForm()  # ✅ AGREGADO: Pasar el form
            return render(request, 'app/crear_ticket.html', contexto)
        
        # Validar foto
        foto = None
        if 'foto_evidencia' in request.FILES:
            foto = request.FILES['foto_evidencia']
            if foto.size > 10 * 1024 * 1024:
                messages.error(request, 'La foto no puede superar los 10 MB.')
                contexto = _preparar_contexto_ubicaciones()
                contexto['form'] = TicketForm()  # ✅ AGREGADO: Pasar el form
                return render(request, 'app/crear_ticket.html', contexto)
        else:
            messages.error(request, 'La foto de evidencia es obligatoria.')
            contexto = _preparar_contexto_ubicaciones()
            contexto['form'] = TicketForm()  # ✅ AGREGADO: Pasar el form
            return render(request, 'app/crear_ticket.html', contexto)
        
        # Crear ticket
        ticket = Ticket(
            titulo=titulo,
            descripcion=descripcion,
            ubicacion=ubicacion,
            categoria_id=categoria,
            urgencia=urgencia,
            creado_por=request.user,
            afecta_clase=afecta_clase,
            riesgo_electrico=riesgo_electrico,
            riesgo_estructural=riesgo_estructural,
            riesgo_accesibilidad=riesgo_accesibilidad,
            estado=EstadoCatalogo.para('ticket', 'enviado'),
            foto_evidencia=foto,
        )
        ticket.save()
        
        # Registros de trazabilidad
        registrar_log(
            ticket, request.user, 'Ticket creado',
            estado_nuevo='enviado',
            ip=get_client_ip(request)
        )
        
        HistorialAcciones.objects.create(
            ticket=ticket,
            usuario=request.user,
            tipo_accion='creacion',
            estado_anterior=None,
            estado_nuevo='enviado',
            descripcion=f'Ticket creado por {request.user.get_full_name() or request.user.username}',
            es_global=True,
            ip_address=get_client_ip(request),
        )
        
        # Notificaciones
        notificar(
            request.user, 'ticket_enviado',
            f'Ticket #{ticket.pk} enviado',
            'Tu reporte ha sido registrado correctamente.',
            ticket=ticket
        )
        
        notificar_gestores(
            'ticket_enviado',
            f'Nuevo ticket #{ticket.pk}',
            f'{request.user.get_full_name() or request.user.username} reportó: {ticket.titulo}',
            ticket=ticket,
            prioridad='alta' if ticket.urgencia == 'critica' else 'media',
            url_accion=reverse('app:detalle_ticket', kwargs={'pk': ticket.pk})
        )
        
        messages.success(request, f'✓ Ticket #{ticket.pk} creado exitosamente.')
        return redirect('app:mis_tickets')
    
    # GET: Mostrar formulario vacío
    contexto = _preparar_contexto_ubicaciones()
    contexto['form'] = TicketForm()  # ✅ AGREGADO: Pasar el form (ESTO ES LO QUE FALTABA)
    return render(request, 'app/crear_ticket.html', contexto)


@login_required
def mis_tickets(request):
    tickets = Ticket.objects.filter(creado_por=request.user, deleted_at__isnull=True).order_by('-created_at')
    estado = request.GET.get('estado')
    if estado:
        tickets = tickets.filter(estado__codigo=estado)
    return render(request, 'app/mis_tickets.html', {
        'tickets': tickets,
        'estados': EstadoCatalogo.objects.filter(entidad='ticket').order_by('orden').values_list('codigo', 'nombre_display'),
        'estado_filtro': estado,
    })


@login_required
def detalle_ticket(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, deleted_at__isnull=True)
    if request.user.rol == 'usuario' and ticket.creado_por != request.user:
        messages.error(request, 'No tienes permiso para ver este ticket.')
        return redirect('app:mis_tickets')

    es_operativo = request.user.rol in ('gestor', 'guardia', 'mantencion')
    if es_operativo:
        logs = ticket.logs.select_related('usuario').order_by('created_at')
    else:
        ESTADOS_PUBLICOS = {'enviado', 'en_validacion', 'en_mantencion', 'reparado', 'pausado', 'no_reparado', 'cerrado'}
        logs = ticket.logs.filter(es_interno=False).select_related('usuario').order_by('created_at')

    return render(request, 'app/shared/ticket_detalle.html', {
        'ticket': ticket,
        'logs': logs,
        'es_operativo': es_operativo,
    })


@login_required
def editar_ticket(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, creado_por=request.user, deleted_at__isnull=True)
    if not ticket.es_editable():
        messages.error(request, 'Solo puedes editar tickets en estado "Enviado".')
        return redirect('app:detalle_ticket', pk=pk)

    form = TicketForm(request.POST or None, request.FILES or None, instance=ticket)
    if request.method == 'POST' and form.is_valid():
        form.save()
        registrar_log(ticket, request.user, 'Ticket editado', ip=get_client_ip(request))
        messages.success(request, '✓ Ticket actualizado.')
        return redirect('app:detalle_ticket', pk=pk)
    return render(request, 'app/editar_ticket.html', {'form': form, 'ticket': ticket})


@login_required
def eliminar_ticket(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, creado_por=request.user, deleted_at__isnull=True)
    if not ticket.es_editable():
        messages.error(request, 'No puedes eliminar este ticket.')
        return redirect('app:mis_tickets')
    if request.method == 'POST':
        ticket.soft_delete()
        registrar_log(ticket, request.user, 'Ticket eliminado (soft delete)', ip=get_client_ip(request))
        messages.success(request, '✓ Ticket eliminado.')
        return redirect('app:mis_tickets')
    return render(request, 'app/confirmar_eliminar.html', {'ticket': ticket})


@login_required
def cancelar_ticket(request, pk):
    """
    Vista para que el usuario cancele su propio ticket.
    GET: Muestra página de confirmación.
    POST: Ejecuta la cancelación.
    Solo se puede cancelar si el estado es "Enviado".
    """
    ticket = get_object_or_404(Ticket, pk=pk, deleted_at__isnull=True)
    
    # Validar que el usuario sea el creador del ticket
    if ticket.creado_por != request.user:
        messages.error(request, 'No tienes permiso para cancelar este ticket.')
        return redirect('app:detalle_ticket', pk=pk)
    
    # Validar que el ticket esté en estado "Enviado"
    if ticket.estado.codigo != 'enviado':
        messages.error(request, 'Este ticket ya fue tomado y no se puede cancelar.')
        return redirect('app:detalle_ticket', pk=pk)
    
    # Si es GET: mostrar página de confirmación
    if request.method == 'GET':
        return render(request, 'app/confirmar_cancelar.html', {'ticket': ticket})
    
    # Si es POST: ejecutar la cancelación
    # Guardar estado anterior
    estado_anterior = ticket.estado
    
    # Cambiar estado a "Cancelado"
    ticket.estado = EstadoCatalogo.para('ticket', 'cancelado')
    ticket.save()
    
    # Registrar en HistorialAcciones
    HistorialAcciones.objects.create(
        ticket=ticket,
        usuario=request.user,
        tipo_accion='cancelacion',
        estado_anterior=estado_anterior,
        estado_nuevo=ticket.estado,
        descripcion=f'Ticket cancelado por {request.user.get_full_name() or request.user.username}',
        es_global=True,
        ip_address=get_client_ip(request),
    )
    
    # Registrar en LogAuditoria
    registrar_log(
        ticket, request.user, 'Ticket cancelado por usuario',
        estado_anterior=estado_anterior.codigo,
        estado_nuevo='cancelado',
        ip=get_client_ip(request)
    )
    
    # Notificar al gestor
    notificar_gestores(
        'ticket_cancelado',
        f'Ticket #{ticket.pk} cancelado',
        f'{request.user.get_full_name() or request.user.username} canceló el ticket #{ticket.pk}: {ticket.titulo}',
        ticket=ticket,
        prioridad='baja',
        url_accion=reverse('app:detalle_ticket', kwargs={'pk': ticket.pk})
    )
    
    messages.success(request, '✓ Ticket cancelado exitosamente.')
    return redirect('app:detalle_ticket', pk=pk)


# ═══════════════════════════════════════════════════════════════
# GESTOR
# ═══════════════════════════════════════════════════════════════
@login_required
@rol_requerido('gestor')
def gestor_tickets(request):
    qs = Ticket.objects.filter(deleted_at__isnull=True).select_related('creado_por', 'asignado_a').order_by('-created_at')
    estado = request.GET.get('estado')
    urgencia = request.GET.get('urgencia')
    categoria = request.GET.get('categoria')
    busqueda = request.GET.get('q')

    if estado: qs = qs.filter(estado__codigo=estado)
    if urgencia: qs = qs.filter(urgencia=urgencia)
    if categoria: qs = qs.filter(categoria__codigo=categoria)
    if busqueda:
        qs = qs.filter(
            Q(titulo__icontains=busqueda) | Q(descripcion__icontains=busqueda) |
            Q(ubicacion__edificio__icontains=busqueda) | Q(ubicacion__sala__icontains=busqueda)
        )

    return render(request, 'app/ticket.html', {
        'tickets': qs,
        'estados': EstadoCatalogo.objects.filter(entidad='ticket').order_by('orden').values_list('codigo', 'nombre_display'),
        'urgencias': Ticket.URGENCIA_CHOICES,
        'categorias': CategoriaTicket.objects.filter(activo=True).values_list('codigo', 'nombre_display'),
        'filtros': {'estado': estado, 'urgencia': urgencia, 'categoria': categoria, 'q': busqueda},
    })


@login_required
@rol_requerido('gestor')
def vista_gestor_dashboard(request):
    # Dashboard BI alternativo creado por Moises (Sprint 2).
    # Renderiza gestor_dashboard.html con diseno Bootstrap Icons independiente.
    # El template usa datos estaticos de maqueta; los datos reales
    # se pueden conectar en futuras iteraciones.
    # URL: /gestor/dashboard-ui/  nombre: app:gestor_dashboard
    return render(request, 'app/gestor_dashboard.html')


@login_required
@rol_requerido('gestor')
def derivar_ticket(request, pk):
    """
    Vista para derivar ticket a validación (guardia) o mantención (técnico).
    
    CAMBIOS TARJETA 08:
    - Si elige "guardia": mostrar formulario con selector de fecha y guardias disponibles
    
    CAMBIOS TARJETA 09:
    - Si elige "mantencion": mostrar formulario con selector de fecha y técnicos disponibles
    - Validar disponibilidad del técnico (sin inasistencia aprobada en esa fecha)
    - Crear AsignacionTicket con rol_asignacion='mantencion'
    """
    ticket = get_object_or_404(Ticket, pk=pk, deleted_at__isnull=True)
    
    if request.method == 'POST':
        destino = request.POST.get('destino')
        estado_anterior = ticket.estado.codigo
        ticket.gestor_responsable = request.user

        if destino == 'guardia':
            # ═══════════════════════════════════════════════════════════════
            # TARJETA 08: Asignar guardia específico con fecha programada
            # ═══════════════════════════════════════════════════════════════
            guardia_id = request.POST.get('guardia_id')
            fecha_programada_str = request.POST.get('fecha_programada')
            
            if not guardia_id or not fecha_programada_str:
                messages.error(request, 'Debes seleccionar un guardia y una fecha de validación.')
                return redirect('app:derivar_ticket', pk=pk)
            
            try:
                fecha_programada = datetime.strptime(fecha_programada_str, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, 'Fecha de validación inválida.')
                return redirect('app:derivar_ticket', pk=pk)
            
            guardia = get_object_or_404(Usuario, pk=guardia_id, rol='guardia')
            
            # Verificar que el guardia no tenga inasistencia aprobada en esa fecha
            if guardia.inasistencias.filter(
                estado__codigo='aprobada',
                fecha_desde__lte=fecha_programada,
                fecha_hasta__gte=fecha_programada
            ).exists():
                messages.error(request, f'{guardia.get_full_name()} tiene una inasistencia aprobada en esa fecha.')
                return redirect('app:derivar_ticket', pk=pk)
            
            # Crear asignación N-N
            asignacion = AsignacionTicket.objects.create(
                ticket=ticket,
                usuario=guardia,
                rol_asignacion='guardia',
                asignado_por=request.user,
                estado=EstadoCatalogo.para('asignacion', 'pendiente'),
                fecha_programada=fecha_programada
            )
            
            # Cambiar estado principal del ticket a 'en_validacion'
            ticket.sub_estado = EstadoCatalogo.para('ticket_sub', 'asignado_guardia')
            ticket.estado = EstadoCatalogo.para('ticket', 'en_validacion')
            ticket.save()
            
            # Registrar en historial
            HistorialAcciones.objects.create(
                ticket=ticket,
                usuario=request.user,
                tipo_accion='asignacion',
                estado_anterior=estado_anterior,
                estado_nuevo='en_validacion',
                sub_estado_nuevo='asignado_guardia',
                descripcion=f'Ticket asignado a guardia {guardia.get_full_name()} para validación el {fecha_programada.strftime("%d/%m/%Y")}',
                es_global=True,
                ip_address=get_client_ip(request),
            )
            
            # Notificar al guardia asignado
            notificar(
                guardia, 'asignacion',
                f'Te asignaron el ticket #{ticket.pk} para validar',
                f'Debe realizar la validación en terreno el {fecha_programada.strftime("%d/%m/%Y")}.\n'
                f'Ubicación: {ticket.ubicacion}\n'
                f'Descripción: {ticket.titulo}',
                ticket=ticket,
                prioridad='alta' if ticket.urgencia in ['alta', 'critica'] else 'media',
                url_accion=reverse('app:dashboard')
            )
            
            messages.success(request, f'✓ Guardia {guardia.get_full_name()} asignado para validación el {fecha_programada.strftime("%d/%m/%Y")}.')
            return redirect('app:gestor_tickets')

        elif destino == 'mantencion':
            # ═══════════════════════════════════════════════════════════════
            # TARJETA 09: Asignar técnico específico con fecha programada
            # ═══════════════════════════════════════════════════════════════
            tecnico_id = request.POST.get('tecnico_id')
            fecha_programada_str = request.POST.get('fecha_programada_mantencion')
            
            if not tecnico_id or not fecha_programada_str:
                messages.error(request, 'Debes seleccionar un técnico y una fecha de trabajo.')
                return redirect('app:derivar_ticket', pk=pk)
            
            try:
                fecha_programada = datetime.strptime(fecha_programada_str, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, 'Fecha de trabajo inválida.')
                return redirect('app:derivar_ticket', pk=pk)
            
            tecnico = get_object_or_404(Usuario, pk=tecnico_id, rol='mantencion')
            
            # Verificar que el técnico no tenga inasistencia aprobada en esa fecha
            if tecnico.inasistencias.filter(
                estado__codigo='aprobada',
                fecha_desde__lte=fecha_programada,
                fecha_hasta__gte=fecha_programada
            ).exists():
                messages.error(request, f'{tecnico.get_full_name()} tiene una inasistencia aprobada en esa fecha.')
                return redirect('app:derivar_ticket', pk=pk)
            
            # Crear asignación N-N para mantención
            asignacion = AsignacionTicket.objects.create(
                ticket=ticket,
                usuario=tecnico,
                rol_asignacion='mantencion',
                asignado_por=request.user,
                estado=EstadoCatalogo.para('asignacion', 'pendiente'),
                fecha_programada=fecha_programada
            )
            
            # Asignar técnico al ticket y cambiar estado
            ticket.asignado_a = tecnico
            ticket.estado = EstadoCatalogo.para('ticket', 'en_mantencion')
            ticket.sub_estado = EstadoCatalogo.para('ticket_sub', 'asignado_tecnico')
            ticket.save()
            
            # Registrar en historial
            HistorialAcciones.objects.create(
                ticket=ticket,
                usuario=request.user,
                tipo_accion='asignacion',
                estado_anterior=estado_anterior,
                estado_nuevo='en_mantencion',
                sub_estado_nuevo='asignado_tecnico',
                descripcion=f'Ticket asignado a técnico {tecnico.get_full_name()} para trabajo el {fecha_programada.strftime("%d/%m/%Y")}',
                es_global=True,
                ip_address=get_client_ip(request),
            )
            
            # Notificar al técnico asignado
            notificar(
                tecnico, 'asignacion',
                f'Te asignaron el ticket #{ticket.pk} para reparación',
                f'Debe realizar el trabajo el {fecha_programada.strftime("%d/%m/%Y")}.\n'
                f'Ubicación: {ticket.ubicacion}\n'
                f'Descripción: {ticket.titulo}',
                ticket=ticket,
                prioridad='alta' if ticket.urgencia in ['alta', 'critica'] else 'media',
                url_accion=reverse('app:completar_mantencion', kwargs={'pk': ticket.pk})
            )
            
            # Notificación al usuario creador (Cambio a En Mantención)
            notificar(
                destinatario=ticket.creado_por,
                tipo='ticket_actualizado',
                titulo=f'Ticket #{ticket.pk} en proceso de reparación',
                mensaje=f'Tu reporte "{ticket.titulo}" ya se encuentra en proceso de solución.',
                ticket=ticket,
                prioridad='media',
                url_accion=reverse('app:detalle_ticket', kwargs={'pk': ticket.pk})
            )
            
            messages.success(request, f'✓ Técnico {tecnico.get_full_name()} asignado para trabajo el {fecha_programada.strftime("%d/%m/%Y")}.')
            return redirect('app:gestor_tickets')

    # GET: Mostrar formulario de derivación
    tecnicos = Usuario.objects.filter(rol='mantencion', estado_cuenta__codigo='activa', activo=True)
    guardias = Usuario.objects.filter(rol='guardia', estado_cuenta__codigo='activa', activo=True)
    return render(request, 'app/derivar.html', {
        'ticket': ticket, 
        'tecnicos': tecnicos,
        'guardias': guardias
    })


@login_required
@rol_requerido('gestor')
def guardias_disponibles_ajax(request):
    """
    Vista AJAX para obtener guardias disponibles en una fecha específica.
    Filtra guardias que NO tienen inasistencia aprobada en esa fecha.
    
    TARJETA 08:
    - Recibe fecha por GET
    - Retorna JSON con lista de guardias disponibles
    """
    fecha_str = request.GET.get('fecha')
    
    if not fecha_str:
        return JsonResponse({'error': 'Fecha requerida'}, status=400)
    
    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Fecha inválida'}, status=400)
    
    # Obtener todos los guardias activos
    guardias = Usuario.objects.filter(
        rol='guardia',
        estado_cuenta__codigo='activa',
        activo=True
    ).order_by('first_name', 'last_name')
    
    # Filtrar guardias que NO tienen inasistencia aprobada en esa fecha
    guardias_disponibles = []
    for g in guardias:
        tiene_inasistencia = g.inasistencias.filter(
            estado__codigo='aprobada',
            fecha_desde__lte=fecha,
            fecha_hasta__gte=fecha
        ).exists()
        
        if not tiene_inasistencia:
            guardias_disponibles.append({
                'id': g.id,
                'nombre': f'{g.get_full_name()} ({g.turno})' if g.turno else g.get_full_name(),
                'turno': g.turno or 'General'
            })
    
    return JsonResponse({
        'fecha': fecha_str,
        'guardias': guardias_disponibles,
        'total': len(guardias_disponibles)
    })


@login_required
@rol_requerido('gestor')
def tecnicos_disponibles_ajax(request):
    """
    Vista AJAX para obtener técnicos disponibles en una fecha específica.
    Filtra técnicos que NO tienen inasistencia aprobada en esa fecha.
    
    TARJETA 09:
    - Recibe fecha por GET
    - Retorna JSON con lista de técnicos disponibles
    """
    fecha_str = request.GET.get('fecha')
    
    if not fecha_str:
        return JsonResponse({'error': 'Fecha requerida'}, status=400)
    
    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Fecha inválida'}, status=400)
    
    # Obtener todos los técnicos activos
    tecnicos = Usuario.objects.filter(
        rol='mantencion',
        estado_cuenta__codigo='activa',
        activo=True
    ).order_by('first_name', 'last_name')
    
    # Filtrar técnicos que NO tienen inasistencia aprobada en esa fecha
    tecnicos_disponibles = []
    for t in tecnicos:
        tiene_inasistencia = t.inasistencias.filter(
            estado__codigo='aprobada',
            fecha_desde__lte=fecha,
            fecha_hasta__gte=fecha
        ).exists()
        
        if not tiene_inasistencia:
            # Obtener especialidades del técnico
            especialidades = list(t.especialidades.values_list('nombre', flat=True))
            especialidad_texto = ', '.join(especialidades) if especialidades else 'General'
            
            tecnicos_disponibles.append({
                'id': t.id,
                'nombre': t.get_full_name(),
                'especialidad': especialidad_texto
            })
    
    return JsonResponse({
        'fecha': fecha_str,
        'tecnicos': tecnicos_disponibles,
        'total': len(tecnicos_disponibles)
    })


@login_required
@rol_requerido('gestor')
def reasignar_ticket(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, deleted_at__isnull=True)
    roles_destino = ['mantencion'] if ticket.estado.codigo == 'en_mantencion' else ['guardia', 'mantencion']

    form = ReasignarForm(request.POST or None, roles=roles_destino)
    if request.method == 'POST' and form.is_valid():
        anterior = ticket.asignado_a
        nuevo = form.cleaned_data['nuevo_responsable']
        motivo = form.cleaned_data['motivo']
        ticket.asignado_a = nuevo
        ticket.save()
        registrar_log(ticket, request.user,
                      f'Reasignado: {anterior or "(sin asignar)"} → {nuevo.get_full_name()}',
                      ip=get_client_ip(request), es_interno=True, detalle=motivo)
        notificar(nuevo, 'asignacion', f'Ticket reasignado a ti #{ticket.pk}',
                  f'{ticket.titulo}\nMotivo: {motivo}', ticket=ticket,
                  url_accion=reverse('app:detalle_ticket', kwargs={'pk': ticket.pk}))
        messages.success(request, '✓ Ticket reasignado.')
        return redirect('app:gestor_tickets')

    return render(request, 'app/reasignar.html', {'form': form, 'ticket': ticket})


@login_required
@rol_requerido('gestor')
def pausar_ticket(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, deleted_at__isnull=True)
    form = PausaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        estado_anterior = ticket.estado.codigo
        razones = form.cleaned_data['razones_pausa']
        pausa_labels = dict(Ticket.PAUSA_CHOICES)
        razones_texto = ' | '.join(pausa_labels.get(r, r) for r in razones)

        ticket.estado = EstadoCatalogo.para('ticket', 'pausado')
        ticket.estado_pausa = ','.join(razones)
        ticket.motivo_pausa = form.cleaned_data['motivo_pausa']
        ticket.save()
        registrar_log(ticket, request.user,
                      f'Ticket pausado — {razones_texto}',
                      estado_anterior=estado_anterior, estado_nuevo='pausado',
                      ip=get_client_ip(request), es_interno=True,
                      detalle=f'Razones: {razones_texto}\nDetalle: {ticket.motivo_pausa}')
        if ticket.asignado_a:
            notificar(ticket.asignado_a, 'pausa', f'Ticket #{ticket.pk} pausado',
                      f'Motivo: {razones_texto}', ticket=ticket)
        messages.success(request, '✓ Ticket pausado.')
        return redirect('app:gestor_tickets')
    return render(request, 'app/pausar.html', {'form': form, 'ticket': ticket, 'pausa_choices': Ticket.PAUSA_CHOICES})


@login_required
@rol_requerido('gestor')
def reactivar_ticket(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, estado__codigo='pausado', deleted_at__isnull=True)
    form = ReactivacionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        codigo_destino = 'en_mantencion' if ticket.asignado_a and ticket.asignado_a.rol == 'mantencion' else 'validado' if ticket.validado_por else 'enviado'
        ticket.estado = EstadoCatalogo.para('ticket', codigo_destino)
        ticket.comentario_reactivacion = form.cleaned_data['comentario']
        ticket.estado_pausa = None
        ticket.motivo_pausa = None
        ticket.save()
        registrar_log(ticket, request.user,
                      f'Ticket reactivado — vuelve a {codigo_destino}',
                      estado_anterior='pausado', estado_nuevo=codigo_destino,
                      ip=get_client_ip(request), es_interno=True,
                      detalle=f'Razón de reactivación: {ticket.comentario_reactivacion}')
        if ticket.asignado_a:
            notificar(ticket.asignado_a, 'reactivacion', f'Ticket #{ticket.pk} reactivado',
                      ticket.comentario_reactivacion, ticket=ticket)
        messages.success(request, '✓ Ticket reactivado.')
        return redirect('app:gestor_tickets')
    return render(request, 'app/reactivar.html', {'form': form, 'ticket': ticket})


@login_required
@rol_requerido('gestor')
def cerrar_ticket(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, deleted_at__isnull=True)
    if ticket.estado.codigo not in ('reparado', 'en_mantencion', 'pausado', 'no_reparado', 'en_proceso', 'en_validacion'):
        messages.error(request, 'Este ticket no puede cerrarse desde su estado actual.')
        return redirect('app:gestor_tickets')
    if request.method == 'POST':
        estado_anterior = ticket.estado.codigo
        ticket.estado = EstadoCatalogo.para('ticket', 'cerrado')
        ticket.cerrado_at = timezone.now()
        ticket.save()
        registrar_log(ticket, request.user, 'Ticket cerrado por gestor',
                      estado_anterior=estado_anterior, estado_nuevo='cerrado',
                      ip=get_client_ip(request))
        notificar(ticket.creado_por, 'ticket_cerrado', f'Ticket #{ticket.pk} cerrado',
                  'Tu reporte fue resuelto satisfactoriamente.', ticket=ticket)
        messages.success(request, '✓ Ticket cerrado.')
        return redirect('app:gestor_tickets')
    return render(request, 'app/cerrar_ticket.html', {'ticket': ticket})


@login_required
@rol_requerido('gestor')
def validar_reparacion(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, estado__codigo='reparado', deleted_at__isnull=True)
    mantencion = getattr(ticket, 'mantencion', None)

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'aprobar':
            estado_anterior = ticket.estado.codigo
            ticket.estado = EstadoCatalogo.para('ticket', 'cerrado')
            ticket.cerrado_at = timezone.now()
            ticket.save()
            registrar_log(ticket, request.user, 'Reparación aprobada por gestor — ticket cerrado',
                          estado_anterior=estado_anterior, estado_nuevo='cerrado',
                          ip=get_client_ip(request))
            notificar(ticket.creado_por, 'ticket_cerrado',
                      f'Ticket #{ticket.pk} cerrado',
                      'La reparación fue aprobada por el gestor. Tu reporte quedó resuelto.',
                      ticket=ticket)
            if mantencion:
                notificar(mantencion.tecnico, 'general',
                          f'Reparación #{ticket.pk} aprobada',
                          f'El gestor aprobó tu reparación del ticket "{ticket.titulo}".',
                          ticket=ticket)
            messages.success(request, '✓ Reparación aprobada. Ticket cerrado.')
            return redirect('app:gestor_tickets')

        elif accion == 'rechazar':
            comentario = request.POST.get('comentario_rechazo', '').strip()
            if not comentario:
                messages.error(request, 'Debes ingresar el motivo del rechazo.')
                return render(request, 'app/validar_reparacion.html',
                              {'ticket': ticket, 'mantencion': mantencion})
            estado_anterior = ticket.estado.codigo
            ticket.estado = EstadoCatalogo.para('ticket', 'en_mantencion')
            ticket.save()
            registrar_log(ticket, request.user,
                          f'Reparación rechazada por gestor — devuelta a mantención',
                          estado_anterior=estado_anterior, estado_nuevo='en_mantencion',
                          ip=get_client_ip(request), es_interno=True,
                          detalle=comentario)
            if mantencion:
                notificar(mantencion.tecnico, 'rechazo_validacion',
                          f'Reparación #{ticket.pk} rechazada',
                          f'El gestor rechazó la reparación: {comentario}',
                          ticket=ticket)
            messages.warning(request, '⚠ Reparación rechazada. Ticket devuelto a mantención.')
            return redirect('app:gestor_tickets')

    return render(request, 'app/validar_reparacion.html',
                  {'ticket': ticket, 'mantencion': mantencion})


# ── Gestor: Gestión de cuentas ─────────────────────
@login_required
@rol_requerido('gestor')
def gestor_solicitudes_cuenta(request):
    pendientes = Usuario.objects.filter(estado_cuenta__codigo='pendiente').order_by('-fecha_registro')
    recientes = Usuario.objects.exclude(estado_cuenta__codigo='pendiente').order_by('-fecha_aprobacion')[:10]
    return render(request, 'app/solicitudes__cuenta.html', {
        'pendientes': pendientes, 'recientes': recientes,
    })


@login_required
@rol_requerido('gestor')
def aprobar_cuenta(request, pk):
    user = get_object_or_404(Usuario, pk=pk, estado_cuenta__codigo='pendiente')
    form_rol = AsignarRolForm(request.POST or None)

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'aprobar':
            if not form_rol.is_valid():
                messages.error(request, 'Selecciona un rol válido para aprobar la cuenta.')
                return render(request, 'app/revisar_cuenta.html', {
                    'cuenta': user,
                    'form_rol': form_rol,
                })

            rol_asignado = form_rol.cleaned_data['rol']

            rut_nuevo = request.POST.get('rut_nuevo', '').strip()
            if rut_nuevo and rut_nuevo != user.rut:
                if not Usuario.objects.filter(rut=rut_nuevo).exclude(pk=user.pk).exists():
                    user.rut = rut_nuevo
                else:
                    messages.warning(request, f'El RUT {rut_nuevo} ya pertenece a otro usuario. Se mantuvo el RUT temporal.')

            user.rol = rol_asignado
            user.estado_cuenta = EstadoCatalogo.para('cuenta', 'activa')
            user.is_active = True
            user.fecha_aprobacion = timezone.now()
            user.aprobado_por = request.user
            user.save()
            
            # ═══════════════════════════════════════════════════════════════
            # NUEVO: LÓGICA DE ESPECIALIDAD PARA MANTENCIÓN
            # ═══════════════════════════════════════════════════════════════
            if rol_asignado == 'mantencion':
                # Capturamos el ID de la especialidad desde el dropdown del HTML
                especialidad_id = request.POST.get('especialidad_seleccionada')
                if especialidad_id:
                    especialidad_obj = get_object_or_404(Especialidad, id=especialidad_id)
                    # Al usar la relación Muchos a Muchos (M:N), lo agregamos a la tabla intermedia
                    user.especialidades.add(especialidad_obj) 
                else:
                    messages.warning(request, 'Se aprobó al mantenedor pero no se le asignó ninguna especialidad.')
            # ═══════════════════════════════════════════════════════════════

            if settings.AUTH0_ENABLED and user.auth0_sub:
                try:
                    auth0_service.actualizar_rol_auth0(
                        auth0_sub=user.auth0_sub,
                        rol=rol_asignado,
                        estado='activa',
                    )
                    logger.info(f"Rol '{rol_asignado}' sincronizado en Auth0 para {user.auth0_sub}")
                except Auth0Error as e:
                    logger.warning(f"No se pudo sincronizar rol en Auth0 para {user.auth0_sub}: {e.message}")
                    messages.warning(
                        request,
                        f'Cuenta aprobada localmente, pero no se pudo sincronizar el rol '
                        f'en Auth0 ({e.message}). El usuario puede necesitar re-ingresar.'
                    )

            LogAuditoria.objects.create(
                usuario=request.user,
                accion=f'Cuenta aprobada: {user.username}',
                ip_address=get_client_ip(request),
                modulo='cuenta',
                detalle=f'Aprobada con rol: {user.get_rol_display()}',
            )
            notificar(
                user,
                'cuenta_aprobada',
                '✓ Tu cuenta fue aprobada',
                f'Bienvenido a Campus Seguro. Ya puedes iniciar sesión. '
                f'Tu rol asignado es: {user.get_rol_display()}.',
            )
            messages.success(
                request,
                f'✓ Cuenta de {user.get_full_name()} aprobada como {user.get_rol_display()}.'
            )

        elif accion == 'rechazar':
            user.estado_cuenta = EstadoCatalogo.para('cuenta', 'rechazada')
            user.save()
            LogAuditoria.objects.create(
                usuario=request.user,
                accion=f'Cuenta rechazada: {user.username}',
                ip_address=get_client_ip(request),
                modulo='cuenta',
            )
            notificar(
                user,
                'cuenta_rechazada',
                '✗ Tu solicitud de cuenta fue rechazada',
                'Contacta al administrador para más información.',
            )
            messages.info(request, f'Cuenta de {user.get_full_name()} rechazada.')

        return redirect('app:gestor_solicitudes_cuenta')

    # ═══════════════════════════════════════════════════════════════
    # GET: PASAR LAS ESPECIALIDADES AL TEMPLATE (CRÍTICO)
    # ═══════════════════════════════════════════════════════════════
    # Aquí necesitas enviar todas las especialidades de la base de datos
    # para que el formulario HTML pueda dibujar el dropdown de opciones.
    return render(request, 'app/revisar_cuenta.html', {
        'cuenta': user,
        'form_rol': form_rol,
        'especialidades': Especialidad.objects.all(), # 👈 NUEVA VARIABLE PARA EL CONTEXTO
    })


@login_required
@rol_requerido('gestor')
def gestor_usuarios(request):
    qs = Usuario.objects.all().order_by('-fecha_registro')
    rol_filtro = request.GET.get('rol')
    estado_filtro = request.GET.get('estado')
    if rol_filtro:
        qs = qs.filter(rol=rol_filtro)
    if estado_filtro:
        qs = qs.filter(estado_cuenta__codigo=estado_filtro)
    return render(request, 'app/usuarios.html', {
        'usuarios': qs,
        'roles': Usuario.ROL_CHOICES,
        'estados': EstadoCatalogo.objects.filter(entidad='cuenta').order_by('orden').values_list('codigo', 'nombre_display'),
        'filtros': {'rol': rol_filtro, 'estado': estado_filtro},
        'todas_especialidades': Especialidad.objects.all(), # 👈 PASAMOS TODAS LAS ESPECIALIDADES PARA FILTRADO EN LA TABLA
    })

# NUEVA VISTA: Procesar el cambio de especialidades (M:N)
@login_required
@rol_requerido('gestor')
def actualizar_especialidades_mantenedor(request, pk):
    if request.method == 'POST':
        usuario = get_object_or_404(Usuario, pk=pk, rol='mantencion')
        # Capturamos la lista de IDs seleccionadas desde los checkboxes
        especialidades_ids = request.POST.getlist('especialidades_usuario')
        
        # .set() limpia las anteriores automáticamente e inyecta las nuevas en la tabla intermedia
        usuario.especialidades.set(especialidades_ids)
        
        messages.success(request, f'✓ Especialidades de {usuario.get_full_name()} actualizadas correctamente.')
    return redirect('app:gestor_usuarios')

@login_required
@rol_requerido('gestor')
def suspender_usuario(request, pk):
    user = get_object_or_404(Usuario, pk=pk)
    if request.method == 'POST':
        if user.estado_cuenta.codigo == 'suspendida':
            user.estado_cuenta = EstadoCatalogo.para('cuenta', 'activa')
            user.is_active = True
            messages.success(request, f'✓ {user.get_full_name()} reactivado.')
            accion = 'Cuenta reactivada'
        else:
            user.estado_cuenta = EstadoCatalogo.para('cuenta', 'suspendida')
            user.is_active = False
            messages.warning(request, f'⚠ {user.get_full_name()} suspendido.')
            accion = 'Cuenta suspendida'
        user.save()
        LogAuditoria.objects.create(
            usuario=request.user, accion=f'{accion}: {user.username}',
            ip_address=get_client_ip(request), modulo='cuenta'
        )
    return redirect('app:gestor_usuarios')


@login_required
@rol_requerido('gestor')
def reset_usuario_gestor(request, pk):
    user = get_object_or_404(Usuario, pk=pk)
    if request.method == 'POST':
        token = TokenRecuperacion.generar(user, ip=get_client_ip(request))
        link = request.build_absolute_uri(
            reverse('app:restablecer_contrasena', kwargs={'token': token.token})
        )
        LogAuditoria.objects.create(
            usuario=request.user,
            accion=f'Reset de contraseña generado para {user.username}',
            ip_address=get_client_ip(request), modulo='cuenta'
        )
        notificar(user, 'reset_password', 'Restablecimiento de contraseña',
                  f'Un gestor generó un enlace para restablecer tu contraseña.',
                  url_accion=link)
        messages.success(request, f'✓ Enlace generado. URL: {link}')
    return redirect('app:gestor_usuarios')


# ═══════════════════════════════════════════════════════════════
# GESTOR: DASHBOARD OPERATIVO / BI / REPORTES
# ═══════════════════════════════════════════════════════════════
@login_required
@rol_requerido('gestor')
def gestor_operativo(request):
    rendimiento_mantencion = Usuario.objects.filter(rol='mantencion', estado_cuenta__codigo='activa').annotate(
        total_trabajos=Count('cierres_firmados', distinct=True),
        trabajos_completados=Count('tickets_asignados', filter=Q(tickets_asignados__estado__codigo__in=['cerrado', 'reparado']), distinct=True),
        en_curso=Count('tickets_asignados', filter=Q(tickets_asignados__estado__codigo='en_mantencion'), distinct=True),
        no_reparados=Count('noreparable', distinct=True),
        hh_totales=Sum('sesiones_trabajo__horas_hombre'),
    ).order_by('-trabajos_completados')

    rendimiento_guardia = Usuario.objects.filter(rol='guardia', estado_cuenta__codigo='activa').annotate(
        total_validaciones=Count('validacionguardia', distinct=True),
        validos=Count('validacionguardia', filter=Q(validacionguardia__resultado='valido'), distinct=True),
        invalidos=Count('validacionguardia', filter=Q(validacionguardia__resultado='invalido'), distinct=True),
    ).order_by('-total_validaciones')

    return render(request, 'app/operativo.html', {
        'rendimiento_mantencion': rendimiento_mantencion,
        'rendimiento_guardia': rendimiento_guardia,
    })


@login_required
@rol_requerido('gestor')
def gestor_bi(request):
    from datetime import date as date_cls
    hoy = timezone.now().date()
    rango = request.GET.get('rango', 'mes')
    seccion = request.GET.get('seccion', 'general')
    trabajador_id = request.GET.get('trabajador', '')
    cat_material = request.GET.get('cat_material', '')
    fecha_desde_str = request.GET.get('fecha_desde', '')
    fecha_hasta_str = request.GET.get('fecha_hasta', '')
    
    cat_material_nombre = None
    if cat_material:
        cat_obj = CategoriaMaterial.objects.filter(codigo=cat_material).first()
        if cat_obj:
            cat_material_nombre = cat_obj.nombre_display

    hasta = hoy
    if fecha_desde_str:
        try:
            desde = date_cls.fromisoformat(fecha_desde_str)
            if fecha_hasta_str:
                hasta = date_cls.fromisoformat(fecha_hasta_str)
            rango = 'custom'
        except ValueError:
            desde = hoy - timedelta(days=30)
    elif rango == 'dia':
        desde = hoy
    elif rango == 'semana':
        desde = hoy - timedelta(days=7)
    elif rango == 'año':
        desde = hoy - timedelta(days=365)
    else:
        desde = hoy - timedelta(days=30)

    tickets = Ticket.objects.filter(
        deleted_at__isnull=True,
        created_at__date__gte=desde,
        created_at__date__lte=hasta,
    )
    total_tickets = tickets.count()
    afectan_clase = tickets.filter(afecta_clase=True).count()
    riesgos_electricos = tickets.filter(riesgo_electrico=True).count()
    riesgos_estructurales = tickets.filter(riesgo_estructural=True).count()
    cerrados_periodo = tickets.filter(estado__codigo='cerrado').count()
    porc_impacto = round((afectan_clase / total_tickets * 100) if total_tickets else 0, 1)
    tasa_cierre = round((cerrados_periodo / total_tickets * 100) if total_tickets else 0, 1)
    por_categoria = list(tickets.values('categoria__nombre_display').annotate(total=Count('id')).order_by('-total'))
    por_urgencia = list(tickets.values('urgencia').annotate(total=Count('id')))
    por_estado = [{'estado': i['estado__codigo'], 'total': i['total']} for i in tickets.values('estado__codigo').annotate(total=Count('id')).order_by('-total')]
    por_edificio = list(tickets.values(edificio=F('ubicacion__edificio')).annotate(total=Count('id')).order_by('-total')[:8])
    reincidencia = list(
        tickets.values(
            edificio=F('ubicacion__edificio'),
            piso=F('ubicacion__piso'),
            sala=F('ubicacion__sala'),
        ).annotate(total=Count('id')).filter(total__gt=1).order_by('-total')[:8]
    )

    val_qs = ValidacionGuardia.objects.filter(
        created_at__date__gte=desde, created_at__date__lte=hasta
    )
    if trabajador_id and seccion == 'guardias':
        val_qs = val_qs.filter(guardia_id=trabajador_id)

    val_total = val_qs.count()
    val_validas = val_qs.filter(resultado='valido').count()
    val_invalidas = val_qs.filter(resultado='invalido').count()
    val_con_foto = val_qs.filter(foto_evidencia__isnull=False).exclude(foto_evidencia='').count()
    _val_tiempo = val_qs.aggregate(avg=Avg('tiempo_validacion_minutos'))['avg']
    val_tiempo_prom = round(float(_val_tiempo), 1) if _val_tiempo else 0
    val_tasa_validez = round((val_validas / val_total * 100) if val_total else 0, 1)
    val_tasa_foto = round((val_con_foto / val_total * 100) if val_total else 0, 1)
    val_check_elec = val_qs.filter(checklist_electrico=True).count()
    val_check_estr = val_qs.filter(checklist_estructural=True).count()
    val_check_acc = val_qs.filter(checklist_accesibilidad=True).count()

    por_guardia = list(
        val_qs.values('guardia__id', 'guardia__first_name', 'guardia__last_name')
        .annotate(
            total=Count('id'),
            validas=Count('id', filter=Q(resultado='valido')),
            invalidas=Count('id', filter=Q(resultado='invalido')),
            con_foto=Count('id', filter=Q(foto_evidencia__isnull=False) & ~Q(foto_evidencia='')),
            checklists=Count('id', filter=Q(checklist_electrico=True) | Q(checklist_estructural=True) | Q(checklist_accesibilidad=True)),
            tiempo_prom=Avg('tiempo_validacion_minutos'),
        ).order_by('-total')
    )
    max_val_total = max((g['total'] for g in por_guardia), default=1)
    for g in por_guardia:
        tasa_v = (g['validas'] / g['total'] * 100) if g['total'] else 0
        tasa_f = (g['con_foto'] / g['total'] * 100) if g['total'] else 0
        actividad = (g['total'] / max_val_total * 100) if max_val_total else 0
        riesgo_pts = min(g['checklists'] * 12, 100)
        g['score'] = int(tasa_v * 0.35 + tasa_f * 0.30 + actividad * 0.20 + riesgo_pts * 0.15)
        g['val_tasa'] = round(tasa_v, 1)
        g['foto_tasa'] = round(tasa_f, 1)

    val_por_categoria = list(
        Ticket.objects.filter(
            deleted_at__isnull=True, created_at__date__gte=desde,
            created_at__date__lte=hasta, validacion__isnull=False
        ).values('categoria__nombre_display').annotate(total=Count('id')).order_by('-total')
    )

    # ═══════════════════════════════════════════════════════════════
    # 🟢 CORRECCIÓN: Filtramos por 'fecha_registro' y cruzamos con 'ticket__sesiones'
    # ═══════════════════════════════════════════════════════════════
    mant_qs = RegistroMantencion.objects.filter(
        fecha_registro__date__gte=desde, fecha_registro__date__lte=hasta
    )
    if trabajador_id and seccion in ('mantencion', 'materiales'):
        mant_qs = mant_qs.filter(tecnico_id=trabajador_id)

    mant_total = mant_qs.count()
    
    # Agregamos las HH reales consultando las sesiones asociadas a los tickets cerrados
    _mant_hh = mant_qs.aggregate(t=Sum('ticket__sesiones__horas_hombre'))['t']
    _mant_hh_prom = mant_qs.aggregate(avg=Avg('ticket__sesiones__horas_hombre'))['avg']
    
    mant_hh_total = round(float(_mant_hh), 1) if _mant_hh else 0
    mant_hh_prom = round(float(_mant_hh_prom), 1) if _mant_hh_prom else 0
    
    # El tiempo promedio lo estimamos multiplicando las HH promedio por 60 minutos
    mant_tiempo_prom = int(mant_hh_prom * 60)
    
    # Contamos la presencia de alertas analíticas buscando en las sesiones del periodo
    mant_personal_adicional = mant_qs.filter(ticket__sesiones__personal_adicional_requerido=True).distinct().count()
    mant_nivel_mayor = mant_qs.filter(ticket__sesiones__requiere_nivel_mayor=True).distinct().count()
    
    mant_con_foto = mant_qs.filter(foto_final__isnull=False).exclude(foto_final='').count()
    mant_tasa_foto = round((mant_con_foto / mant_total * 100) if mant_total else 0, 1)

    # 🟢 CORRECCIÓN: Tabla de rendimiento por Técnico adaptada a la subestructura
    por_tecnico = list(
        mant_qs.values('tecnico__id', 'tecnico__first_name', 'tecnico__last_name')
        .annotate(
            total=Count('id'),
            hh_total=Sum('ticket__sesiones__horas_hombre'),
            hh_prom=Avg('ticket__sesiones__horas_hombre'),
            nivel_mayor=Count('ticket__sesiones', filter=Q(ticket__sesiones__requiere_nivel_mayor=True), distinct=True),
            adicional=Count('ticket__sesiones', filter=Q(ticket__sesiones__personal_adicional_requerido=True), distinct=True),
            con_foto=Count('id', filter=Q(foto_final__isnull=False) & ~Q(foto_final='')),
        ).order_by('-total')
    )

    nrep_qs = NoReparable.objects.filter(
        created_at__date__gte=desde, created_at__date__lte=hasta
    )
    if trabajador_id and seccion == 'mantencion':
        nrep_qs = nrep_qs.filter(tecnico_id=trabajador_id)
    nrep_total = nrep_qs.count()
    nrep_por_criticidad = list(nrep_qs.values('criticidad').annotate(total=Count('id')).order_by('-total'))
    nrep_externalizacion = nrep_qs.filter(requiere_externalizacion=True).count()
    denominador = mant_total + nrep_total
    tasa_nrep = round((nrep_total / denominador * 100) if denominador else 0, 1)

    max_mant_total = max((t['total'] for t in por_tecnico), default=1)
    for t in por_tecnico:
        nrep_tec = nrep_qs.filter(tecnico_id=t['tecnico__id']).count()
        denom_tec = t['total'] + nrep_tec
        t['resolucion'] = round((t['total'] / denom_tec * 100) if denom_tec else 100, 1)
        t['foto_tasa'] = round((t['con_foto'] / t['total'] * 100) if t['total'] else 0, 1)
        escalaciones = (t['nivel_mayor'] or 0) + (t['adicional'] or 0)
        t['autonomia'] = round(max(0, (t['total'] - escalaciones) / t['total'] * 100) if t['total'] else 100, 1)
        actividad_pts = (t['total'] / max_mant_total * 100) if max_mant_total else 0
        t['score'] = int(t['resolucion'] * 0.40 + t['foto_tasa'] * 0.20 + t['autonomia'] * 0.25 + actividad_pts * 0.15)
        t['nrep_count'] = nrep_tec

    mat_qs = MaterialUtilizado.objects.filter(
        sesion_trabajo__created_at__date__gte=desde,
        sesion_trabajo__created_at__date__lte=hasta,
    )
    if trabajador_id and seccion == 'materiales':
        mat_qs = mat_qs.filter(sesion_trabajo__tecnico_id=trabajador_id)
    if cat_material and seccion == 'materiales':
        mat_qs = mat_qs.filter(material__categoria__codigo=cat_material)

    materiales_top = list(
        mat_qs.values('material__codigo', 'material__nombre', 'material__unidad')
        .annotate(
            categoria_nombre=F('material__categoria__nombre_display'),
            total_consumido=Sum('cantidad_utilizada'),
            veces_usado=Count('id'),
            en_tickets=Count('sesion_trabajo__ticket', distinct=True),
        ).order_by('-total_consumido')[:20]
    )
    por_categoria_mat = list(
        mat_qs.values('material__categoria__nombre_display')
        .annotate(total=Sum('cantidad_utilizada'), frecuencia=Count('id'), tipos=Count('material', distinct=True))
        .order_by('-total')
    )
    mat_por_tipo_ticket = list(
        mat_qs.values('sesion_trabajo__ticket__categoria__nombre_display')
        .annotate(
            total_cantidad=Sum('cantidad_utilizada'),
            tipos_material=Count('material', distinct=True),
            usos=Count('id'),
        ).order_by('-total_cantidad')
    )
    mat_por_tecnico = list(
        mat_qs.values(
            nombre=F('sesion_trabajo__tecnico__first_name'),
            apellido=F('sesion_trabajo__tecnico__last_name')
        )
        .annotate(
            items_distintos=Count('material', distinct=True), 
            cantidad_total=Sum('cantidad_utilizada')
        )
        .order_by('-cantidad_total')
    )
    # CORREGIDO: Traer el código y el nombre descriptivo real de la tabla maestra
    categorias_materiales = list(
        CategoriaMaterial.objects.filter(activo=True).values_list('codigo', 'nombre_display')
    )

    guardias = Usuario.objects.filter(rol='guardia', estado_cuenta__codigo='activa').order_by('first_name')
    tecnicos = Usuario.objects.filter(rol='mantencion', estado_cuenta__codigo='activa').order_by('first_name')

    return render(request, 'app/bi.html', {
        'rango': rango, 'desde': desde, 'hasta': hasta, 'seccion': seccion,
        'trabajador_id': trabajador_id, 'cat_material': cat_material,
        'fecha_desde_str': fecha_desde_str, 'fecha_hasta_str': fecha_hasta_str,
        'guardias': guardias, 'tecnicos': tecnicos,
        'total_tickets': total_tickets, 'afectan_clase': afectan_clase,
        'riesgos_electricos': riesgos_electricos, 'riesgos_estructurales': riesgos_estructurales,
        'cerrados_periodo': cerrados_periodo, 'tasa_cierre': tasa_cierre, 'porc_impacto': porc_impacto,
        'por_categoria': por_categoria, 'por_urgencia': por_urgencia,
        'por_estado': por_estado, 'por_edificio': por_edificio, 'reincidencia': reincidencia,
        'val_total': val_total, 'val_validas': val_validas, 'val_invalidas': val_invalidas,
        'val_con_foto': val_con_foto, 'val_tiempo_prom': val_tiempo_prom,
        'val_tasa_validez': val_tasa_validez, 'val_tasa_foto': val_tasa_foto,
        'val_check_elec': val_check_elec, 'val_check_estr': val_check_estr,
        'val_check_acc': val_check_acc, 'por_guardia': por_guardia, 'val_por_categoria': val_por_categoria,
        'mant_total': mant_total, 'mant_hh_total': mant_hh_total, 'mant_hh_prom': mant_hh_prom,
        'mant_tiempo_prom': mant_tiempo_prom, 'mant_personal_adicional': mant_personal_adicional,
        'mant_nivel_mayor': mant_nivel_mayor, 'mant_con_foto': mant_con_foto,
        'mant_tasa_foto': mant_tasa_foto, 'por_tecnico': por_tecnico,
        'nrep_total': nrep_total, 'nrep_por_criticidad': nrep_por_criticidad,
        'nrep_externalizacion': nrep_externalizacion, 'tasa_nrep': tasa_nrep,
        'materiales_top': materiales_top, 'por_categoria_mat': por_categoria_mat,
        'mat_por_tipo_ticket': mat_por_tipo_ticket, 'mat_por_tecnico': mat_por_tecnico,
        'categorias_materiales': categorias_materiales, 'cat_material': cat_material, 'cat_material_nombre': cat_material_nombre,
    })


# ═══════════════════════════════════════════════════════════════
# GUARDIA
# ═══════════════════════════════════════════════════════════════
@login_required
@rol_requerido('guardia')
def validar_ticket(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, estado__codigo='en_validacion', deleted_at__isnull=True)
    if hasattr(ticket, 'validacion'):
        messages.info(request, 'Este ticket ya fue validado.')
        return redirect('app:dashboard')

    form = ValidacionForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        validacion = form.save(commit=False)
        validacion.ticket = ticket
        validacion.guardia = request.user
        validacion.save()

        estado_anterior = ticket.estado.codigo
        
        # ═══════════════════════════════════════════════════════════════
        # TARJETA 08: Actualizar estado de la asignación a 'completada'
        # Esto hace que el ticket desaparezca de "Mis Revisiones Asignadas"
        # ═══════════════════════════════════════════════════════════════
        try:
            asignacion = AsignacionTicket.objects.get(
                ticket=ticket,
                usuario=request.user,
                rol_asignacion='guardia',
                estado__codigo='pendiente'
            )
            asignacion.estado = EstadoCatalogo.para('asignacion', 'completada')
            asignacion.fecha_completado = timezone.now()
            asignacion.save()
        except AsignacionTicket.DoesNotExist:
            pass # Si no existe, simplemente continúa

        if validacion.resultado == 'valido':
            ticket.estado = EstadoCatalogo.para('ticket', 'validado')
            mensaje_gestor = (f'Ticket #{ticket.pk} validado por guardia {request.user.get_full_name()}. '
                              f'Listo para asignar a mantención.')
        else:
            ticket.estado = EstadoCatalogo.para('ticket', 'cerrado')
            ticket.cerrado_at = timezone.now()
            mensaje_gestor = (f'Ticket #{ticket.pk} marcado como inválido por guardia '
                              f'{request.user.get_full_name()}.')

        ticket.validado_por = request.user
        ticket.save()

        registrar_log(ticket, request.user,
                      f'Validación en terreno: {validacion.get_resultado_display()} — {request.user.get_full_name()}',
                      estado_anterior=estado_anterior, estado_nuevo=ticket.estado.codigo,
                      ip=get_client_ip(request), es_interno=False,
                      detalle=f'{validacion.comentario}' + (' | Con foto de evidencia.' if validacion.foto_evidencia else ''))

        notificar_gestores('validacion', f'Validación completada #{ticket.pk}',
                           mensaje_gestor, ticket=ticket,
                           url_accion=reverse('app:detalle_ticket', kwargs={'pk': ticket.pk}))

        if validacion.resultado == 'invalido':
            notificar(ticket.creado_por, 'validacion', f'Ticket #{ticket.pk} cerrado tras validación',
                      f'Tu reporte fue revisado en terreno: {validacion.comentario[:100]}',
                      ticket=ticket)

        messages.success(request, '✓ Validación registrada.')
        return redirect('app:dashboard')

    return render(request, 'app/validar.html', {'form': form, 'ticket': ticket})


# ═══════════════════════════════════════════════════════════════
# MANTENCIÓN
# ═══════════════════════════════════════════════════════════════

@login_required
@rol_requerido('mantencion')
def estimar_ticket(request, pk):
    """Vista para procesar el diagnóstico y tiempo estimado del mantenedor."""
    ticket = get_object_or_404(Ticket, pk=pk, estado__codigo='en_mantencion', asignado_a=request.user, deleted_at__isnull=True)
    
    # Buscamos la asignación de mantención pendiente para este ticket y este técnico
    asignacion = get_object_or_404(AsignacionTicket, ticket=ticket, usuario=request.user, rol_asignacion='mantencion')

    if request.method == 'POST':
        form = EstimarTicketForm(request.POST, instance=asignacion)
        if form.is_valid():
            form.save()
            
            # Guardamos el hito en los logs de auditoría para el BI
            registrar_log(
                ticket, request.user, 'Estimación técnica ingresada', 
                ip=get_client_ip(request), es_interno=True, 
                detalle=f"Tiempo estimado: {asignacion.tiempo_estimado} hrs. Diagnóstico: {asignacion.diagnostico_preliminar[:150]}..."
            )
            
            messages.success(request, '✓ Estimación registrada con éxito. Ya puedes iniciar el trabajo.')
            return redirect('app:dashboard')
    else:
        form = EstimarTicketForm(instance=asignacion)

    return render(request, 'app/mantencion/estimar.html', {
        'form': form,
        'ticket': ticket,
    })

@login_required
@rol_requerido('mantencion')
def tomar_trabajo(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, estado__codigo='en_mantencion', asignado_a=request.user, deleted_at__isnull=True)
    if request.method == 'POST':
        if not ticket.inicio_trabajo_at:
            ticket.inicio_trabajo_at = timezone.now()
            ticket.save()
            registrar_log(ticket, request.user, 'Trabajo iniciado',
                          ip=get_client_ip(request), es_interno=True,
                          detalle=f'Técnico {request.user.get_full_name()} inició la reparación')
            notificar_gestores('general', f'Ticket #{ticket.pk} en reparación',
                               f'{request.user.get_full_name()} comenzó la reparación: {ticket.titulo}',
                               ticket=ticket, prioridad='media',
                               url_accion=reverse('app:detalle_ticket', kwargs={'pk': ticket.pk}))
            messages.success(request, f'✓ Trabajo iniciado. Registra la reparación cuando termines.')
        else:
            messages.info(request, 'Este trabajo ya fue iniciado.')
    return redirect('app:dashboard')

@login_required
@rol_requerido('mantencion')
def completar_mantencion(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, estado__codigo='en_mantencion', asignado_a=request.user, deleted_at__isnull=True)
    if hasattr(ticket, 'mantencion'):
        messages.info(request, 'Este ticket ya tiene registro de mantención.')
        return redirect('app:dashboard')

    # Catálogos para el desvío dinámico por JavaScript
    todos_materiales = Material.objects.filter(activo=True).order_by('categoria__nombre_display', 'nombre')
    tecnico = request.user
    especialidades_tecnico = tecnico.especialidades.all()

    if especialidades_tecnico.exists():
        materiales_filtrados = Material.objects.filter(
            activo=True,
            especialidades__in=especialidades_tecnico
        ).distinct().order_by('categoria__nombre_display', 'nombre')
    else:
        materiales_filtrados = todos_materiales

    def serialize_mat(qs):
        return [
            {
                'id': m.id,
                'text': f"{m.nombre} ({m.codigo}) - {m.categoria.nombre_display if m.categoria else 'General'}"
            } for m in qs
        ]

    materiales_filtrados_json = json.dumps(serialize_mat(materiales_filtrados))
    todos_materiales_json = json.dumps(serialize_mat(todos_materiales))

    # Inicializamos formularios por defecto para evitar UnboundLocalError en fallos de validación
    form = MantencionForm(request.POST or None, request.FILES or None if request.method == 'POST' else None)
    formset = MaterialUtilizadoFormSet(request.POST or None if request.method == 'POST' else None)

    if request.method == 'POST':
        tipo_rendicion = request.POST.get('tipo_rendicion')
        ahora = timezone.now()
        
        # 🟢 1. CAPTURA OBLIGATORIA DE TEXTOS
        descripcion_limpia = request.POST.get('descripcion_trabajo', '').strip()
        herramientas_limpias = request.POST.get('herramientas_utilizadas', '').strip()
        
        # 🟢 2. Checkboxes y Observaciones del turno
        personal_adicional = request.POST.get('personal_adicional_requerido') == 'on'
        nivel_mayor = request.POST.get('requiere_nivel_mayor') == 'on'
        observaciones_limpias = request.POST.get('observaciones', '').strip()

        # Helper local para re-renderizar la pantalla con errores sin perder el estado
        def responder_con_error(mensaje):
            messages.error(request, mensaje)
            logs = ticket.logs.select_related('usuario').order_by('created_at')
            return render(request, 'app/mantencion/completar.html', {
                'form': form,
                'formset': formset,
                'ticket': ticket,
                'logs': logs,
                'materiales_filtrados_json': materiales_filtrados_json,
                'todos_materiales_json': todos_materiales_json,
            })

        # 🟢 2. GUARDIAS DE VALIDACIÓN CRÍTICA
        if not descripcion_limpia:
            return responder_con_error('⚠️ Operación rechazada: Es obligatorio ingresar una descripción del trabajo realizado.')
            
        if not herramientas_limpias: # ◄--- NUEVO: Frena el envío si las herramientas van vacías
            return responder_con_error('⚠️ Operación rechazada: Debes especificar qué herramientas utilizaste en este turno (ej: Ninguna, destornillador, etc).')
        
        if not observaciones_limpias:
            return responder_con_error('⚠️ Operación rechazada: Es obligatorio dejar una observación o nota de turno para el gestor.')
        
        if len(observaciones_limpias) > 500:
            return responder_con_error('⚠️ El campo de observaciones no puede superar los 500 caracteres.')
        
        # 🟢 AUTOMATIZACIÓN: Cálculo matemático de Horas Hombre reales
        if ticket.inicio_trabajo_at:
            delta = ahora - ticket.inicio_trabajo_at
            horas_hombre_limpio = max(0.1, round(delta.total_seconds() / 3600, 1))
        else:
            horas_hombre_limpio = 0.1 # Fallback de resguardo por si el cronómetro no partió bien
        
        # ═══════════════════════════════════════════════════════════════
        # CASO A: EL TÉCNICO SOLO REGISTRA UN AVANCE DIARIO
        # ═══════════════════════════════════════════════════════════════
        if tipo_rendicion == 'avance':
            # Construimos el objeto en memoria (sin impactar la BD todavía)
            sesion = SesionTrabajo(
                ticket=ticket,
                tecnico=request.user,
                inicio=ticket.inicio_trabajo_at or ahora,
                fin=ahora,
                horas_hombre=horas_hombre_limpio,
                descripcion_avance=descripcion_limpia,
                herramientas_utilizadas=herramientas_limpias,
                personal_adicional_requerido=personal_adicional,
                requiere_nivel_mayor=nivel_mayor,
                observaciones=observaciones_limpias if observaciones_limpias else 'Sin observaciones',
                tipo_cierre='fin_turno'
            )
            formset = MaterialUtilizadoFormSet(request.POST, instance=sesion)
            
            # ✔️ CORREGIDO: Aplicamos el desvío de validación para el catálogo de avance también
            for sub_form in formset:
                sub_form.fields['material'].queryset = todos_materiales
            
            # 1. Ejecutamos la validación base de Django
            formset_valido = formset.is_valid()

            # 🟢 INTERCEPTOR DE ERRORES DE CANTIDAD O ENTRADA
            # Si Django detecta que falta la cantidad, que es inválida o cualquier problema,
            # extraemos el error y lo mandamos al cartel rojo.
            if not formset_valido:
                for errors in formset.errors:
                    for field, error_list in errors.items():
                        # Traducimos el nombre del campo para el técnico en terreno
                        campo_nombre = "Cantidad" if field == "cantidad_utilizada" else field
                        return responder_con_error(f"⚠️ Error en materiales: El campo '{campo_nombre}' tiene un problema: {error_list[0]}")

            if formset.is_valid():
                sesion.save() # Guardamos la sesión SOLO si los materiales están correctos
                formset.save()
                
                ticket.inicio_trabajo_at = None 
                ticket.save()
                
                registrar_log(ticket, request.user, 'Avance de jornada registrado', ip=get_client_ip(request))
                messages.success(request, '✓ Avance diario guardado. El ticket sigue activo para tu próximo turno.')
                return redirect('app:dashboard')

        # ═══════════════════════════════════════════════════════════════
        # CASO B: EL TÉCNICO TERMINÓ Y CIERRA EL TICKET DEFINITIVAMENTE
        # ═══════════════════════════════════════════════════════════════
        elif tipo_rendicion == 'finalizar':
            # 🟢 NUEVA VALIDACIÓN: Verificar foto obligatoria solo para el cierre definitivo
            foto = request.FILES.get('foto_final')
            if not foto:
                return responder_con_error('⚠️ Operación rechazada: Es obligatorio subir una foto de evidencia para poder finalizar y cerrar el ticket.')
            
            sesion_final = SesionTrabajo(
                ticket=ticket,
                tecnico=request.user,
                inicio=ticket.inicio_trabajo_at or ahora,
                fin=ahora,
                horas_hombre=horas_hombre_limpio,
                descripcion_avance=descripcion_limpia,
                herramientas_utilizadas=herramientas_limpias,
                personal_adicional_requerido=personal_adicional,
                requiere_nivel_mayor=nivel_mayor,
                observaciones=observaciones_limpias if observaciones_limpias else 'Sin observaciones',
                tipo_cierre='completado'
            )
            formset = MaterialUtilizadoFormSet(request.POST, instance=sesion_final)
            
            for sub_form in formset:
                sub_form.fields['material'].queryset = todos_materiales
            
            formset_valido = formset.is_valid()

            # 🟢 INTERCEPTOR DE ERRORES PARA EL CIERRE
            if not formset_valido:
                for errors in formset.errors:
                    for field, error_list in errors.items():
                        campo_nombre = "Cantidad" if field == "cantidad_utilizada" else field
                        return responder_con_error(f"⚠️ Error en materiales: El campo '{campo_nombre}' tiene un problema: {error_list[0]}")

            if formset.is_valid():
                sesion_final.save() # Guardamos de forma segura tras pasar las validaciones
                formset.save()
                
                registro = form.save(commit=False)
                registro.ticket = ticket
                registro.tecnico = request.user
                registro.foto_final = foto
                registro.save()
                
                ticket.estado = EstadoCatalogo.para('ticket', 'reparado')
                ticket.sub_estado = None
                ticket.inicio_trabajo_at = None
                ticket.save()
                
                registrar_log(ticket, request.user, 'Reparación finalizada con éxito', ip=get_client_ip(request))
                messages.success(request, '✓ ¡Excelente! El ticket ha sido cerrado y enviado al gestor para su revisión final.')
                return redirect('app:dashboard')
    else:
        form = MantencionForm()
        # ✔️ CORREGIDO: El formset inicial se amarra a una SesionTrabajo en blanco
        formset = MaterialUtilizadoFormSet(instance=SesionTrabajo())
        for sub_form in formset:
            sub_form.fields['material'].queryset = materiales_filtrados

    logs = ticket.logs.select_related('usuario').order_by('created_at')
    
    return render(request, 'app/mantencion/completar.html', {
        'form': form,
        'formset': formset,
        'ticket': ticket,
        'logs': logs,
        'materiales_filtrados_json': materiales_filtrados_json,
        'todos_materiales_json': todos_materiales_json,
    })

@login_required
@rol_requerido('mantencion')
def marcar_no_reparable(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, estado__codigo='en_mantencion', asignado_a=request.user, deleted_at__isnull=True)
    form = NoReparableForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        no_rep = form.save(commit=False)
        no_rep.ticket = ticket
        no_rep.tecnico = request.user
        no_rep.save()
        ticket.estado = EstadoCatalogo.para('ticket', 'no_reparado')
        ticket.save()
        registrar_log(ticket, request.user, 'Marcado como No Reparable',
                      estado_anterior='en_mantencion', estado_nuevo='no_reparado',
                      ip=get_client_ip(request), es_interno=True,
                      detalle=no_rep.motivo_tecnico)
        notificar_gestores('no_reparado', f'⚠ Ticket #{ticket.pk} no reparable',
                           f'{request.user.get_full_name()} marcó el ticket como no reparable.\n{no_rep.motivo_tecnico[:150]}',
                           ticket=ticket, prioridad='alta',
                           url_accion=reverse('app:detalle_ticket', kwargs={'pk': ticket.pk}))
        messages.warning(request, '⚠ Ticket marcado como no reparable. Se notificó al gestor.')
        return redirect('app:dashboard')
    return render(request, 'app/mantencion/no_reparable.html', {'form': form, 'ticket': ticket})


# ═══════════════════════════════════════════════════════════════
# MATERIALES (catálogo)
# ═══════════════════════════════════════════════════════════════
@login_required
@rol_requerido('gestor')
def materiales_listado(request):
    qs = Material.objects.all().order_by('categoria', 'nombre')
    categoria = request.GET.get('categoria')
    if categoria:
        qs = qs.filter(categoria__codigo=categoria)
    return render(request, 'app/materiales.html', {
        'materiales': qs,
        'categorias': CategoriaMaterial.objects.filter(activo=True).values_list('codigo', 'nombre_display'),
        'categoria_filtro': categoria,
    })


@login_required
@rol_requerido('gestor')
def material_form(request, pk=None):
    material = get_object_or_404(Material, pk=pk) if pk else None
    form = MaterialForm(request.POST or None, instance=material)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, '✓ Material guardado.')
        return redirect('app:materiales_listado')
    return render(request, 'app/material_form.html', {'form': form, 'material': material})


# ═══════════════════════════════════════════════════════════════
# INASISTENCIAS
# ═══════════════════════════════════════════════════════════════
@login_required
@rol_requerido('guardia', 'mantencion')
def registrar_inasistencia(request):
    form = InasistenciaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        ina = form.save(commit=False)
        ina.usuario = request.user
        ina.estado = EstadoCatalogo.para('inasistencia', 'pendiente')
        ina.save()
        notificar_gestores('inasistencia', f'Inasistencia: {request.user.get_full_name()}',
                           f'Solicitud de ausencia: {ina.fecha_desde} → {ina.fecha_hasta} ({ina.get_motivo_display()})',
                           url_accion=reverse('app:gestor_inasistencias'))
        messages.success(request, '✓ Inasistencia registrada. Pendiente de aprobación.')
        return redirect('app:dashboard')
    return render(request, 'app/shared/inasistencia_form.html', {'form': form})


@login_required
@rol_requerido('gestor')
def gestor_inasistencias(request):
    pendientes = Inasistencia.objects.filter(estado__codigo='pendiente').select_related('usuario').order_by('-created_at')
    recientes = Inasistencia.objects.exclude(estado__codigo='pendiente').select_related('usuario').order_by('-created_at')[:15]
    return render(request, 'app/inasistencia.html', {
        'pendientes': pendientes, 'recientes': recientes,
    })


@login_required
@rol_requerido('gestor')
def revisar_inasistencia(request, pk):
    ina = get_object_or_404(Inasistencia, pk=pk)
    if request.method == 'POST':
        accion = request.POST.get('accion')
        ina.revisado_por = request.user
        if accion == 'aprobar':
            ina.estado = EstadoCatalogo.para('inasistencia', 'aprobada')
            notificar(ina.usuario, 'inasistencia', '✓ Inasistencia aprobada',
                      f'Tu solicitud para {ina.fecha_desde} → {ina.fecha_hasta} fue aprobada.')
        else:
            ina.estado = EstadoCatalogo.para('inasistencia', 'rechazada')
            notificar(ina.usuario, 'inasistencia', '✗ Inasistencia rechazada',
                      f'Tu solicitud para {ina.fecha_desde} → {ina.fecha_hasta} fue rechazada.')
        ina.save()
        messages.success(request, f'✓ Inasistencia {ina.estado.codigo}.')
    return redirect('app:gestor_inasistencias')


# ═══════════════════════════════════════════════════════════════
# NOTIFICACIONES
# ═══════════════════════════════════════════════════════════════
@login_required
def notificaciones(request):
    notifs = Notificacion.objects.filter(
        destinatario=request.user, deleted_at__isnull=True
    ).order_by('-created_at')
    filtro = request.GET.get('filtro', 'todas')
    if filtro == 'no_leidas':
        notifs = notifs.filter(leida=False, archivada=False)
    elif filtro == 'archivadas':
        notifs = notifs.filter(archivada=True)
    elif filtro == 'todas':
        notifs = notifs.filter(archivada=False)
    return render(request, 'app/shared/notificaciones.html', {
        'notificaciones': notifs,
        'filtro': filtro,
    })


@login_required
def notif_accion(request, pk, accion):
    notif = get_object_or_404(Notificacion, pk=pk, destinatario=request.user)
    if accion == 'leer':
        notif.leida = True
    elif accion == 'archivar':
        notif.archivada = True
        notif.leida = True
    elif accion == 'eliminar':
        notif.deleted_at = timezone.now()
    notif.save()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    return redirect('app:notificaciones')


@login_required
def marcar_todas_leidas(request):
    Notificacion.objects.filter(destinatario=request.user, leida=False).update(leida=True)
    messages.success(request, '✓ Todas las notificaciones marcadas como leídas.')
    return redirect('app:notificaciones')


# ═══════════════════════════════════════════════════════════════
# PERFIL
# ═══════════════════════════════════════════════════════════════
@login_required
def mi_perfil(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        if first_name:
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.save()
            messages.success(request, '✓ Nombre actualizado.')
        else:
            messages.error(request, 'El nombre no puede estar vacío.')
    return render(request, 'app/shared/perfil.html', {'usuario': request.user})


@login_required
def cambiar_password(request):
    if request.method == 'POST':
        actual = request.POST.get('actual')
        nueva1 = request.POST.get('nueva1')
        nueva2 = request.POST.get('nueva2')
        if not request.user.check_password(actual):
            messages.error(request, 'La contraseña actual es incorrecta.')
        elif nueva1 != nueva2:
            messages.error(request, 'Las contraseñas nuevas no coinciden.')
        elif len(nueva1) < 8:
            messages.error(request, 'La nueva contraseña debe tener al menos 8 caracteres.')
        else:
            request.user.set_password(nueva1)
            request.user.save()
            LogAuditoria.objects.create(
                usuario=request.user, accion='Cambio de contraseña',
                ip_address=get_client_ip(request), modulo='cuenta'
            )
            messages.success(request, '✓ Contraseña actualizada.')
            return redirect('app:login')
    return render(request, 'app/shared/cambiar_password.html')


# ═══════════════════════════════════════════════════════════════
# GESTOR: VINCULAR ACTIVO SAP (HU-15)
# ═══════════════════════════════════════════════════════════════
@login_required
@rol_requerido('gestor')
def vincular_activo_ticket(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, deleted_at__isnull=True)
    form = VincularActivoForm(request.POST or None, initial={'id_activo_sap': ticket.id_activo_sap})
    if request.method == 'POST' and form.is_valid():
        ticket.id_activo_sap = form.cleaned_data['id_activo_sap']
        ticket.save()
        registrar_log(ticket, request.user,
                      f'Activo SAP vinculado: {ticket.id_activo_sap}',
                      ip=get_client_ip(request), es_interno=True,
                      detalle=form.cleaned_data.get('descripcion_activo'))
        messages.success(request, f'✓ Activo {ticket.id_activo_sap} vinculado al ticket.')
        return redirect('app:gestor_tickets')
    return render(request, 'app/vincular_activo.html', {'form': form, 'ticket': ticket})


# ═══════════════════════════════════════════════════════════════
# GESTOR: HISTORIAL DE ACCIONES DE UN TICKET
# ═══════════════════════════════════════════════════════════════
@login_required
@rol_requerido('gestor')
def historial_acciones_ticket(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, deleted_at__isnull=True)
    historial = ticket.historial_acciones.select_related('usuario', 'usuario_reasignado_a').order_by('-created_at')
    logs = ticket.logs.select_related('usuario').order_by('-created_at')
    return render(request, 'app/historial_acciones.html', {
        'ticket': ticket,
        'historial': historial,
        'logs': logs,
    })


# ═══════════════════════════════════════════════════════════════
# MANTENCIÓN: TRAZABILIDAD COMPLETA DE TICKET
# ═══════════════════════════════════════════════════════════════
@login_required
@rol_requerido('mantencion', 'gestor')
def trazabilidad_ticket(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, deleted_at__isnull=True)
    logs = ticket.logs.select_related('usuario').order_by('created_at')
    validacion = getattr(ticket, 'validacion', None)
    mantencion = getattr(ticket, 'mantencion', None)
    no_reparable = getattr(ticket, 'no_reparable', None)
    materiales = MaterialUtilizado.objects.filter(sesion_trabajo__ticket=ticket).select_related('material')
    return render(request, 'app/mantencion/trazabilidad.html', {
        'ticket': ticket,
        'logs': logs,
        'validacion': validacion,
        'mantencion': mantencion,
        'no_reparable': no_reparable,
        'materiales': materiales,
    })


# ═══════════════════════════════════════════════════════════════
# MANTENCIÓN: REGISTRAR MATERIAL FALTANTE
# ═══════════════════════════════════════════════════════════════
@login_required
@rol_requerido('mantencion')
def registrar_material_faltante(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, deleted_at__isnull=True)
    sesion = SesionTrabajo.objects.filter(ticket=ticket, tecnico=request.user).first()
    form = MaterialFaltanteForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        faltante = form.save(commit=False)
        faltante.sesion_trabajo = sesion
        faltante.save()
        notificar_gestores('general', f'Material faltante – Ticket #{ticket.pk}',
                           f'{request.user.get_full_name()} reportó material faltante: {faltante.material.nombre}',
                           ticket=ticket, prioridad='media')
        messages.success(request, '✓ Material faltante registrado. Se notificó al gestor.')
        return redirect('app:dashboard')
    return render(request, 'app/mantencion/material_faltante.html', {
        'form': form, 'ticket': ticket, 'sesion': sesion,
    })


# ═══════════════════════════════════════════════════════════════
# GESTOR: DASHBOARD BI v2
# ═══════════════════════════════════════════════════════════════
@login_required
@rol_requerido('gestor')
def dashboard_gestor_bi_v2(request):
    hoy = timezone.now().date()
    rango = request.GET.get('rango', 'mes')
    trabajador_id = request.GET.get('trabajador', '')

    if rango == 'dia':
        desde = hoy
    elif rango == 'semana':
        desde = hoy - timedelta(days=7)
    elif rango == 'año':
        desde = hoy - timedelta(days=365)
    else:
        desde = hoy - timedelta(days=30)

    tickets = Ticket.objects.filter(deleted_at__isnull=True, created_at__date__gte=desde)
    todos = Ticket.objects.filter(deleted_at__isnull=True)

    if trabajador_id:
        tickets = tickets.filter(asignado_a_id=trabajador_id)

    por_categoria = list(tickets.values('categoria__nombre_display').annotate(total=Count('id')).order_by('-total'))
    por_urgencia = list(tickets.values('urgencia').annotate(total=Count('id')))
    por_estado = [{'estado': i['estado__codigo'], 'total': i['total']} for i in tickets.values('estado__codigo').annotate(total=Count('id'))]
    por_edificio = list(tickets.values(edificio=F('ubicacion__edificio')).annotate(total=Count('id')).order_by('-total')[:8])
    trabajadores = Usuario.objects.filter(rol__in=['mantencion', 'guardia'], estado_cuenta__codigo='activa').order_by('first_name')

    sesiones_periodo = SesionTrabajo.objects.filter(created_at__date__gte=desde)
    if trabajador_id:
        sesiones_periodo = sesiones_periodo.filter(tecnico_id=trabajador_id)

    return render(request, 'app/dashboard_bi_v2.html', {
        'total_tickets': tickets.count(),
        'cerrados_periodo': tickets.filter(estado__codigo='cerrado').count(),
        'criticos_activos': todos.filter(urgencia='critica').exclude(estado__codigo__in=['cerrado', 'eliminado']).count(),
        'no_reparados': todos.filter(estado__codigo='no_reparado').count(),
        'por_categoria': por_categoria,
        'por_urgencia': por_urgencia,
        'por_estado': por_estado,
        'por_edificio': por_edificio,
        'hh_total': sesiones_periodo.aggregate(t=Sum('horas_hombre'))['t'] or 0,
        'rango': rango,
        'desde': desde,
        'trabajadores': trabajadores,
        'trabajador_id': trabajador_id,
    })


# ═══════════════════════════════════════════════════════════════
# GESTOR: REPORTE DE MATERIALES
# ═══════════════════════════════════════════════════════════════
@login_required
@rol_requerido('gestor')
def reporte_materiales(request):
    materiales = Material.objects.all().order_by('categoria', 'nombre')
    consumo = MaterialUtilizado.objects.values(
        'material__codigo', 'material__nombre', 'material__categoria__nombre_display', 'material__unidad'
    ).annotate(
        total_consumido=Sum('cantidad_utilizada'),
        veces_usado=Count('id'),
    ).order_by('-total_consumido')
    return render(request, 'app/reporte_materiales.html', {
        'materiales': materiales,
        'consumo': consumo,
        'total_materiales': materiales.count(),
    })


# ═══════════════════════════════════════════════════════════════
# GESTOR: REPORTE DE INASISTENCIAS DE EMPLEADOS
# ═══════════════════════════════════════════════════════════════
@login_required
@rol_requerido('gestor')
def reporte_inasistencias_empleados(request):
    inasistencias = Inasistencia.objects.select_related('usuario', 'revisado_por').order_by('-created_at')
    por_empleado = Inasistencia.objects.values(
        'usuario__first_name', 'usuario__last_name', 'usuario__rol'
    ).annotate(
        total=Count('id'),
        aprobadas=Count('id', filter=Q(estado__codigo='aprobada')),
        rechazadas=Count('id', filter=Q(estado__codigo='rechazada')),
        pendientes=Count('id', filter=Q(estado__codigo='pendiente')),
    ).order_by('-total')
    return render(request, 'app/reporte_inasistencias.html', {
        'inasistencias': inasistencias[:50],
        'por_empleado': por_empleado,
        'total': inasistencias.count(),
        'pendientes': inasistencias.filter(estado__codigo='pendiente').count(),
        'aprobadas': inasistencias.filter(estado__codigo='aprobada').count(),
    })


# ═══════════════════════════════════════════════════════════════
# GESTOR: REASIGNAR TICKETS POR INASISTENCIA
# ═══════════════════════════════════════════════════════════════
@login_required
@rol_requerido('gestor')
def reasignar_por_inasistencia(request, pk):
    inasistencia = get_object_or_404(Inasistencia, pk=pk)
    tickets_afectados = Ticket.objects.filter(
        asignado_a=inasistencia.usuario,
        estado__codigo__in=['en_mantencion', 'en_validacion'],
        deleted_at__isnull=True
    )
    if request.method == 'POST':
        nuevo_id = request.POST.get('nuevo_responsable')
        nuevo = get_object_or_404(Usuario, pk=nuevo_id)
        count = 0
        for ticket in tickets_afectados:
            anterior = ticket.asignado_a
            ticket.asignado_a = nuevo
            ticket.save()
            registrar_log(ticket, request.user,
                          f'Reasignado por inasistencia: {anterior.get_full_name()} → {nuevo.get_full_name()}',
                          ip=get_client_ip(request), es_interno=True,
                          detalle=f'Inasistencia #{inasistencia.pk}: {inasistencia.get_motivo_display()}')
            notificar(nuevo, 'asignacion', f'Ticket reasignado #{ticket.pk}',
                      f'{ticket.titulo} – reasignado por inasistencia de {anterior.get_full_name()}',
                      ticket=ticket,
                      url_accion=reverse('app:detalle_ticket', kwargs={'pk': ticket.pk}))
            count += 1
        messages.success(request, f'✓ {count} ticket(s) reasignados a {nuevo.get_full_name()}.')
        return redirect('app:gestor_inasistencias')
    tecnicos = Usuario.objects.filter(
        rol__in=['mantencion', 'guardia'], estado_cuenta__codigo='activa', activo=True
    ).exclude(pk=inasistencia.usuario.pk)
    return render(request, 'app/reasignar_inasistencia.html', {
        'inasistencia': inasistencia,
        'tickets': tickets_afectados,
        'tecnicos': tecnicos,
    })


# ═══════════════════════════════════════════════════════════════
# AUTH0 WEBHOOK
# ═══════════════════════════════════════════════════════════════
import json as _json
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


@csrf_exempt
@require_POST
def auth0_webhook(request):
    webhook_secret = settings.AUTH0_WEBHOOK_SECRET
    if webhook_secret:
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.replace('Bearer ', '').strip()
        if token != webhook_secret:
            logger.warning('Auth0 webhook: token inválido rechazado.')
            return JsonResponse({'error': 'Unauthorized'}, status=401)

    raw_body = request.body.decode('utf-8', errors='replace').strip()
    eventos = []
    try:
        parsed = _json.loads(raw_body)
        eventos = parsed if isinstance(parsed, list) else [parsed]
    except ValueError:
        for linea in raw_body.splitlines():
            linea = linea.strip()
            if not linea:
                continue
            try:
                eventos.append(_json.loads(linea))
            except ValueError:
                logger.warning(f'Auth0 webhook: linea no parseable: {linea[:80]}')

    if not eventos:
        logger.warning(f'Auth0 webhook: body no parseable. Raw: {raw_body[:200]}')
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    tipo_map = {
        's': 'Login exitoso',
        'f': 'Login fallido (credenciales incorrectas)',
        'fp': 'Login fallido (contrasena incorrecta)',
        'fu': 'Login fallido (usuario no existe)',
        'fc': 'Login fallido (cuenta bloqueada)',
        'fco': 'Login fallido (origin no autorizado)',
        'ss': 'Registro exitoso',
        'fs': 'Registro fallido',
        'slo': 'Logout exitoso',
        'flo': 'Logout fallido',
        'scp': 'Cambio de contrasena exitoso',
        'fcp': 'Cambio de contrasena fallido',
        'spwd': 'Solicitud de cambio de contrasena enviada',
        'fpwd': 'Solicitud de cambio de contrasena fallida',
        'sce': 'Cambio de email exitoso',
        'fce': 'Cambio de email fallido',
        'su': 'Usuario actualizado (dashboard Auth0)',
        'sdu': 'Usuario eliminado de Auth0',
        'fdu': 'Eliminacion de usuario fallida',
        'scupm': 'Metadatos de usuario actualizados',
        'limit_wc': 'Cuenta bloqueada (demasiados intentos)',
        'limit_ui': 'Demasiadas solicitudes del usuario',
        'limit_mu': 'Multiples usuarios detectados',
        'adi': 'Usuario invitado por administrador',
        'admin_update_launch': 'Actualizacion de Auth0 iniciada',
        'sapi': '[INTERNO] Llamada a Management API',
        'fapi': '[INTERNO] Llamada a Management API fallida',
        'gd_auth_succeed': 'Autenticacion MFA exitosa',
        'gd_auth_failed': 'Autenticacion MFA fallida',
        'scoa': 'Autenticacion cross-origin exitosa',
        'fcoa': 'Autenticacion cross-origin fallida',
    }

    TIPOS_IGNORADOS = {'sapi', 'fapi'}

    for evento in eventos:
        datos = evento.get('data', evento)
        tipo_raw = datos.get('type', evento.get('type', ''))
        user_name = datos.get('user_name', '') or datos.get('user_id', '') or evento.get('user_name', '')
        descripcion = tipo_map.get(tipo_raw, f'Evento Auth0 ({tipo_raw})')

        if tipo_raw in TIPOS_IGNORADOS:
            logger.debug(f'Auth0 webhook: evento interno ignorado ({tipo_raw}) para {user_name}')
            continue

        usuario_local = None
        if user_name and '@' in user_name:
            try:
                usuario_local = Usuario.objects.get(correo_institucional__iexact=user_name)
            except Usuario.DoesNotExist:
                pass

        if tipo_raw == 'sdu' and usuario_local:
            try:
                estado_suspendida = EstadoCatalogo.objects.get(entidad='cuenta', codigo='suspendida')
                usuario_local.is_active = False
                usuario_local.estado_cuenta = estado_suspendida
                usuario_local.save(update_fields=['is_active', 'estado_cuenta'])
                logger.info(f'Auth0 webhook: usuario {user_name} suspendido en Django tras eliminacion en Auth0')
            except EstadoCatalogo.DoesNotExist:
                logger.warning('Auth0 webhook: no se encontro estado "suspendida" en catalogo')

        ip_evento = datos.get('ip', '')
        log_id = evento.get('log_id', datos.get('log_id', ''))
        detalle_partes = [f'Tipo: {tipo_raw}']
        if user_name:
            detalle_partes.append(f'Usuario Auth0: {user_name}')
        if ip_evento:
            detalle_partes.append(f'IP: {ip_evento}')
        if log_id:
            detalle_partes.append(f'Event ID: {log_id[:20]}...')

        LogAuditoria.objects.create(
            usuario=usuario_local,
            accion=descripcion,
            detalle=' | '.join(detalle_partes),
            modulo='cuenta',
            es_interno=True,
        )
        logger.info(f'Auth0 webhook: {descripcion} para {user_name}')

    return JsonResponse({'received': len(eventos)}, status=200)