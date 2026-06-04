"""
NUEVAS VISTAS - HU-11 a HU-16
Trazabilidad, Validaciones, y Dashboards Mejorados
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Sum, Q, F, Case, When
from datetime import timedelta
from .models import (
    Ticket, Usuario, ValidacionGuardia, RegistroMantencion, MaterialUtilizado,
    NoReparable, HistorialAcciones, MaterialesFaltantes, Inasistencia,
    LogAuditoria, Notificacion, Material, EstadoCatalogo
)
from .forms import (
    ValidacionForm, MantencionForm, NoReparableForm,  # BUG-02: nombres correctos en forms.py
    VincularActivoForm, MaterialUtilizadoForm
)
# BUG-03: helpers definidos en views.py
from .views import rol_requerido, get_client_ip, notificar, notificar_gestores


# ???????????????????????????????????????????????????????????????????????????????????
# HU-11: VALIDACI?N GUARDIA CON CHECKLIST Y EVIDENCIA OBLIGATORIA
# ???????????????????????????????????????????????????????????????????????????????????
@login_required
@rol_requerido('guardia')
def validar_ticket_guardia(request, pk):
    """Guardia valida ticket en terreno - evidencia obligatoria"""
    ticket = get_object_or_404(Ticket, pk=pk, estado__codigo='en_validacion')

    if request.method == 'POST':
        form = ValidacionForm(request.POST, request.FILES)
        if form.is_valid():
            validacion = form.save(commit=False)
            validacion.ticket = ticket
            validacion.guardia = request.user
            validacion.evidencia_obligatoria_presente = bool(form.cleaned_data.get('foto_evidencia'))
            validacion.save()

            # Registrar en historial
            HistorialAcciones.objects.create(
                ticket=ticket,
                usuario=request.user,
                tipo_accion='validacion',
                estado_anterior='en_validacion',
                estado_nuevo='en_mantencion' if validacion.resultado == 'valido' else 'en_proceso',
                descripcion=f"Validaci?n {validacion.get_resultado_display()}",
                ip_address=get_client_ip(request)
            )

            # Actualizar estado del ticket
            if validacion.resultado == 'valido':
                ticket.estado = EstadoCatalogo.para('ticket', 'en_mantencion')
                notificar_gestores('validacion', 'Ticket Validado',
                    f"Ticket #{ticket.pk} pas? validaci?n. Listo para mantenci?n.",
                    ticket, 'media')
            else:
                ticket.estado = EstadoCatalogo.para('ticket', 'en_proceso')
                notificar(request.user, 'validacion', 'Validaci?n Rechazada',
                    f"Ticket #{ticket.pk} fue marcado como inv?lido.", ticket, 'alta')

            ticket.validado_por = request.user
            ticket.save()

            messages.success(request, 'Validaci?n registrada exitosamente')
            return redirect('app:dashboard')
    else:
        form = ValidacionForm()

    return render(request, 'app/validar.html', {
        'ticket': ticket,
        'form': form,
        'requiere_evidencia': True
    })


# ???????????????????????????????????????????????????????????????????????????????????
# HU-12: COMPLETAR MANTENCI?N CON CONTROL DE MATERIALES
# ???????????????????????????????????????????????????????????????????????????????????
@login_required
@rol_requerido('mantencion')
def completar_mantencion_v2(request, pk):
    """T?cnico completa reparaci?n - registra materiales y tiempo"""
    ticket = get_object_or_404(Ticket, pk=pk, estado='en_mantencion', asignado_a=request.user)
    mantencion = ticket.mantencion if hasattr(ticket, 'mantencion') else None

    if not mantencion:
        mantencion = RegistroMantencion.objects.create(ticket=ticket, tecnico=request.user)

    if request.method == 'POST':
        form = MantencionForm(request.POST, request.FILES, instance=mantencion)
        if form.is_valid():
            mantencion = form.save(commit=False)
            mantencion.fecha_finalizacion = timezone.now()
            mantencion.reparacion_exitosa = True
            mantencion.save()

            # Procesar materiales utilizados
            materiales_data = request.POST.getlist('material')
            cantidades = request.POST.getlist('cantidad')

            for material_id, cantidad in zip(materiales_data, cantidades):
                if material_id and cantidad:
                    material = Material.objects.get(pk=material_id)
                    MaterialUtilizado.objects.create(
                        registro=mantencion,
                        material=material,
                        cantidad=float(cantidad)
                    )

            # Registrar en historial
            HistorialAcciones.objects.create(
                ticket=ticket,
                usuario=request.user,
                tipo_accion='completar_mantencion',
                estado_anterior='en_mantencion',
                estado_nuevo='cerrado',
                descripcion=f"Reparaci?n completada - {mantencion.horas_hombre} HH",
                ip_address=get_client_ip(request)
            )

            # Cerrar ticket
            ticket.estado = EstadoCatalogo.para('ticket', 'cerrado')
            ticket.cerrado_at = timezone.now()
            ticket.save()

            notificar_gestores('ticket_cerrado', 'Ticket Reparado',
                f"Ticket #{ticket.pk} ha sido reparado y cerrado.", ticket, 'baja')

            messages.success(request, 'Reparaci?n completada exitosamente')
            return redirect('app:dashboard')
    else:
        form = MantencionForm(instance=mantencion)

    materiales_utilizados = mantencion.materiales_utilizados.all() if mantencion.pk else []

    return render(request, 'app/mantencion/completar.html', {
        'ticket': ticket,
        'mantencion': mantencion,
        'form': form,
        'materiales_utilizados': materiales_utilizados,
        'materiales_disponibles': Material.objects.filter(activo=True)
    })


# ???????????????????????????????????????????????????????????????????????????????????
# HU-13: MARCAR NO REPARABLE CON ESCALAMIENTO
# ???????????????????????????????????????????????????????????????????????????????????
@login_required
@rol_requerido('mantencion')
def marcar_no_reparable_v2(request, pk):
    """T?cnico marca ticket como no reparable - escala a gestor"""
    ticket = get_object_or_404(Ticket, pk=pk, estado__codigo='en_mantencion', asignado_a=request.user)

    if request.method == 'POST':
        form = NoReparableForm(request.POST, request.FILES)
        if form.is_valid():
            no_rep = form.save(commit=False)
            no_rep.ticket = ticket
            no_rep.tecnico = request.user
            no_rep.save()

            # Registrar en historial
            HistorialAcciones.objects.create(
                ticket=ticket,
                usuario=request.user,
                tipo_accion='no_reparable',
                estado_anterior='en_mantencion',
                estado_nuevo='no_reparado',
                descripcion=f"Marcado No Reparable - {no_rep.get_criticidad_display()} - Cr?tica: {no_rep.criticidad}",
                ip_address=get_client_ip(request)
            )

            # Cambiar estado
            ticket.estado = EstadoCatalogo.para('ticket', 'no_reparado')
            ticket.save()

            # Notificar a gestor para escalamiento
            notificar_gestores('no_reparado', 'Ticket No Reparable - Escalamiento',
                f"Ticket #{ticket.pk} marcado como no reparable. Requiere escalamiento.",
                ticket, 'alta')

            messages.success(request, 'Ticket marcado como no reparable. Escalado a gestor.')
            return redirect('app:dashboard')
    else:
        form = NoReparableForm()

    return render(request, 'app/mantencion/no_reparable.html', {
        'ticket': ticket,
        'form': form
    })


# ???????????????????????????????????????????????????????????????????????????????????
# HU-15: VINCULAR TICKET A ACTIVO SAP
# ???????????????????????????????????????????????????????????????????????????????????
@login_required
@rol_requerido('gestor')
def vincular_activo_ticket(request, pk):
    """Gestor vincula ticket a activo SAP para BI"""
    ticket = get_object_or_404(Ticket, pk=pk)

    if request.method == 'POST':
        form = VincularActivoForm(request.POST)
        if form.is_valid():
            id_activo = form.cleaned_data['id_activo_sap']
            ticket.id_activo_sap = id_activo
            ticket.save()

            HistorialAcciones.objects.create(
                ticket=ticket,
                usuario=request.user,
                tipo_accion='vinculacion_activo',
                descripcion=f"Vinculado a activo SAP: {id_activo}",
                ip_address=get_client_ip(request)
            )

            messages.success(request, f"Ticket vinculado al activo {id_activo}")
            return redirect('app:detalle_ticket', pk=pk)
    else:
        form = VincularActivoForm(initial={'id_activo_sap': ticket.id_activo_sap or ''})

    return render(request, 'app/vincular_activo.html', {'ticket': ticket, 'form': form})


# ???????????????????????????????????????????????????????????????????????????????????
# TRAZABILIDAD: HISTORIAL COMPLETO DE ACCIONES
# ???????????????????????????????????????????????????????????????????????????????????
@login_required
def historial_acciones_ticket(request, pk):
    """Muestra el historial completo de acciones de todos los usuarios en el ticket"""
    ticket = get_object_or_404(Ticket, pk=pk)

    # Verificar permisos
    es_gestor = request.user.rol == 'gestor'
    es_creador = ticket.creado_por == request.user
    es_asignado = ticket.asignado_a == request.user

    if not (es_gestor or es_creador or es_asignado or request.user.is_superuser):
        messages.error(request, 'No tienes permisos para ver este historial')
        return redirect('app:dashboard')

    historial = ticket.historial_acciones.all().order_by('-created_at')
    logs = ticket.logs.all().order_by('-created_at')

    return render(request, 'app/historial_acciones.html', {
        'ticket': ticket,
        'historial': historial,
        'logs': logs
    })


# ???????????????????????????????????????????????????????????????????????????????????
# MANTENCI?N: VISTA DE TRAZABILIDAD
# ???????????????????????????????????????????????????????????????????????????????????
@login_required
@rol_requerido('mantencion')
def trazabilidad_ticket(request, pk):
    """T?cnico ve trazabilidad completa del ticket antes de trabajar"""
    ticket = get_object_or_404(Ticket, pk=pk)

    # Solo puede ver si es gestor o est? asignado
    if request.user.rol != 'gestor' and ticket.asignado_a != request.user:
        messages.error(request, 'No tienes permisos para ver este ticket')
        return redirect('app:dashboard')

    historial = ticket.historial_acciones.all().order_by('-created_at')
    validacion = ticket.validacion if hasattr(ticket, 'validacion') else None
    mantencion = ticket.mantencion if hasattr(ticket, 'mantencion') else None

    return render(request, 'app/mantencion/trazabilidad.html', {
        'ticket': ticket,
        'historial': historial,
        'validacion': validacion,
        'mantencion': mantencion
    })


# ???????????????????????????????????????????????????????????????????????????????????
# MANTENIMIENTO: REGISTRAR MATERIALES FALTANTES
# ???????????????????????????????????????????????????????????????????????????????????
@login_required
@rol_requerido('mantencion')
def registrar_material_faltante(request, pk):
    """T?cnico registra material faltante para reparaci?n"""
    ticket = get_object_or_404(Ticket, pk=pk, asignado_a=request.user)
    mantencion = get_object_or_404(RegistroMantencion, ticket=ticket)

    if request.method == 'POST':
        material_id = request.POST.get('material_id')
        cantidad = request.POST.get('cantidad')

        material = Material.objects.get(pk=material_id)
        MaterialesFaltantes.objects.create(
            registro_mantencion=mantencion,
            material=material,
            cantidad_requerida=float(cantidad),
            estado='solicitado'
        )

        notificar_gestores('general', 'Material Faltante',
            f"Ticket #{ticket.pk} requiere material: {cantidad} {material.unidad} de {material.nombre}",
            ticket, 'media')

        messages.success(request, f"Material {material.nombre} registrado como faltante")
        return JsonResponse({'success': True})

    materiales_faltantes = mantencion.materiales_faltantes.all()
    return render(request, 'app/mantencion/material_faltante.html', {
        'ticket': ticket,
        'materiales_faltantes': materiales_faltantes,
        'materiales_disponibles': Material.objects.filter(activo=True)
    })


# ???????????????????????????????????????????????????????????????????????????????????
# GESTOR: DASHBOARD BI MEJORADO CON TRAZABILIDAD Y MATERIALES
# ???????????????????????????????????????????????????????????????????????????????????
@login_required
@rol_requerido('gestor')
def dashboard_gestor_bi_v2(request):
    """Dashboard mejorado con BI: trazabilidad, materiales, impacto"""
    tickets_total = Ticket.objects.filter(deleted_at__isnull=True).count()
    tickets_abiertos = Ticket.objects.filter(estado__in=['enviado', 'en_proceso', 'en_validacion', 'en_mantencion']).count()
    tickets_pausados = Ticket.objects.filter(estado='pausado').count()
    tickets_no_reparados = Ticket.objects.filter(estado='no_reparado').count()

    # Materiales m?s utilizados
    top_materiales = MaterialUtilizado.objects.values('material__nombre').annotate(
        total_cantidad=Sum('cantidad'),
        total_consumos=Count('id')
    ).order_by('-total_cantidad')[:10]

    # Materiales m?s solicitados
    top_materiales_faltantes = MaterialesFaltantes.objects.filter(
        estado__in=['pendiente', 'solicitado']
    ).values('material__nombre').annotate(
        total_cantidad=Sum('cantidad_requerida'),
        total_requests=Count('id')
    ).order_by('-total_cantidad')[:10]

    # Empleados con inasistencias
    empleados_inasistentes = Usuario.objects.filter(
        inasistencias__fecha_desde__lte=timezone.now().date(),
        inasistencias__fecha_hasta__gte=timezone.now().date(),
        inasistencias__estado='aprobada',
        rol__in=['mantencion', 'guardia']
    ).distinct()

    # Tickets asignados a personas con inasistencias
    tickets_bloqueados_inasistencia = Ticket.objects.filter(
        asignado_a__in=empleados_inasistentes,
        estado__in=['en_validacion', 'en_mantencion']
    )

    # Tiempo promedio de reparaci?n
    tickets_cerrados = Ticket.objects.filter(estado='cerrado', cerrado_at__isnull=False)
    tiempo_promedio = None
    if tickets_cerrados.exists():
        duraciones = [t.tiempo_resolucion for t in tickets_cerrados if t.tiempo_resolucion]
        if duraciones:
            tiempo_total = sum(duraciones, timedelta())
            tiempo_promedio = tiempo_total / len(duraciones)

    context = {
        'tickets_total': tickets_total,
        'tickets_abiertos': tickets_abiertos,
        'tickets_pausados': tickets_pausados,
        'tickets_no_reparados': tickets_no_reparados,
        'top_materiales': top_materiales,
        'top_materiales_faltantes': top_materiales_faltantes,
        'empleados_inasistentes': empleados_inasistentes,
        'tickets_bloqueados_inasistencia': tickets_bloqueados_inasistencia,
        'tiempo_promedio_resolucion': tiempo_promedio,
    }

    return render(request, 'app/dashboard_bi_v2.html', context)


# ???????????????????????????????????????????????????????????????????????????????????
# GESTOR: REPORTE DE MATERIALES
# ???????????????????????????????????????????????????????????????????????????????????
@login_required
@rol_requerido('gestor')
def reporte_materiales(request):
    """Reporte detallado de materiales utilizados y solicitados"""
    periodo = request.GET.get('periodo', '30')  # d?as
    desde = timezone.now() - timedelta(days=int(periodo))

    consumos = MaterialUtilizado.objects.filter(
        registro__created_at__gte=desde
    ).values('material__nombre', 'material__categoria').annotate(
        total_cantidad=Sum('cantidad'),
        total_usos=Count('id'),
        stock_actual=F('material__stock_actual')
    ).order_by('-total_cantidad')

    faltantes = MaterialesFaltantes.objects.filter(
        fecha_solicitud__gte=desde
    ).values('material__nombre').annotate(
        total_requerido=Sum('cantidad_requerida'),
        total_recibido=Sum('cantidad_recibida'),
        total_solicitudes=Count('id')
    ).order_by('-total_requerido')

    return render(request, 'app/reporte_materiales.html', {
        'consumos': consumos,
        'faltantes': faltantes,
        'periodo': periodo
    })


# ???????????????????????????????????????????????????????????????????????????????????
# GESTOR: REASIGNACI?N POR INASISTENCIA
# ???????????????????????????????????????????????????????????????????????????????????
@login_required
@rol_requerido('gestor')
def reasignar_por_inasistencia(request, pk):
    """Gestor reasigna tickets de personas con inasistencias"""
    ticket = get_object_or_404(Ticket, pk=pk)
    usuario_actual = ticket.asignado_a

    # Verificar si tiene inasistencia
    if not usuario_actual or not usuario_actual.tiene_inasistencia_activa:
        messages.error(request, 'Este usuario no tiene inasistencia activa')
        return redirect('app:detalle_ticket', pk=pk)

    # Obtener usuarios disponibles del mismo rol sin inasistencias
    usuarios_disponibles = Usuario.objects.filter(
        rol=usuario_actual.rol,
        estado_cuenta__codigo='activa',
        activo=True
    ).exclude(
        inasistencias__fecha_desde__lte=timezone.now().date(),
        inasistencias__fecha_hasta__gte=timezone.now().date(),
        inasistencias__estado__codigo='aprobada'
    ).distinct()

    if request.method == 'POST':
        nuevo_usuario_id = request.POST.get('nuevo_usuario')
        nuevo_usuario = get_object_or_404(Usuario, pk=nuevo_usuario_id)

        # Cambiar asignaci?n
        ticket.asignado_a = nuevo_usuario
        ticket.save()

        # Registrar en historial
        HistorialAcciones.objects.create(
            ticket=ticket,
            usuario=request.user,
            tipo_accion='reasignacion_por_inasistencia',
            descripcion=f"Reasignado de {usuario_actual.get_full_name()} a {nuevo_usuario.get_full_name()} por inasistencia",
            usuario_reasignado_a=nuevo_usuario,
            ip_address=get_client_ip(request)
        )

        notificar(nuevo_usuario, 'asignacion', 'Ticket Reasignado',
            f"Ticket #{ticket.pk} ha sido reasignado a tu persona", ticket, 'media')

        messages.success(request, f"Ticket reasignado a {nuevo_usuario.get_full_name()}")
        return redirect('app:detalle_ticket', pk=pk)

    return render(request, 'app/reasignar_inasistencia.html', {
        'ticket': ticket,
        'usuario_actual': usuario_actual,
        'usuarios_disponibles': usuarios_disponibles
    })


# ???????????????????????????????????????????????????????????????????????????????????
# GESTOR: REPORTE DE INASISTENCIAS
# ???????????????????????????????????????????????????????????????????????????????????
@login_required
@rol_requerido('gestor')
def reporte_inasistencias_empleados(request):
    """Reporte de inasistencias y impacto en tickets"""
    inasistencias_activas = Inasistencia.objects.filter(
        fecha_desde__lte=timezone.now().date(),
        fecha_hasta__gte=timezone.now().date(),
        estado='aprobada'
    ).select_related('usuario').order_by('-fecha_desde')

    impacto = {}
    for inasistencia in inasistencias_activas:
        tickets_asignados = Ticket.objects.filter(
            asignado_a=inasistencia.usuario,
            estado__in=['en_validacion', 'en_mantencion']
        ).count()
        impacto[inasistencia.usuario.id] = tickets_asignados

    return render(request, 'app/reporte_inasistencias.html', {
        'inasistencias_activas': inasistencias_activas,
        'impacto': impacto
    })
