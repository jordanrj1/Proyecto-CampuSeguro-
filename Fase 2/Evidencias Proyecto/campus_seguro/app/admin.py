from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.urls import path, reverse
from django.http import HttpResponseRedirect
from .models import (
    Carrera, CategoriaMaterial, CategoriaTicket, Usuario, TokenRecuperacion, Ubicacion, Material, Ticket,
    SesionTrabajo, ValidacionGuardia, AsignacionTicket, RegistroMantencion, MaterialUtilizado,
    NoReparable, LogAuditoria, Notificacion, Inasistencia,
    HistorialAcciones, MaterialesFaltantes, EstadoCatalogo, TransicionEstado,
    Especialidad, EspecialidadUsuario, EspecialidadMaterial, Sede,
    Rol, Escuela, Departamento, Edificio, Piso, TipoUbicacion # 🌟 CORRECCIÓN 1: Nuevos modelos relacionales importados
)

# ═══════════════════════════════════════════════════════════════
# INLINES
# ═══════════════════════════════════════════════════════════════

class EspecialidadUsuarioInline(admin.TabularInline):
    model = EspecialidadUsuario
    extra = 1


class EspecialidadMaterialInline(admin.TabularInline):
    model = EspecialidadMaterial
    extra = 1


class MaterialUtilizadoInline(admin.TabularInline):
    model = MaterialUtilizado
    extra = 1


# ═══════════════════════════════════════════════════════════════
# 🌟 NUEVO: CONFIGURACIÓN MAESTRA DE INFRAESTRUCTURA GEOGRÁFICA
# ═══════════════════════════════════════════════════════════════

@admin.register(Edificio)
class EdificioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'sede')
    list_filter = ('sede',)
    search_fields = ('nombre', 'sede__nombre')


@admin.register(Piso)
class PisoAdmin(admin.ModelAdmin):
    list_display = ('numero', 'edificio')
    list_filter = ('edificio__sede', 'edificio')
    search_fields = ('numero', 'edificio__nombre')


@admin.register(TipoUbicacion)
class TipoUbicacionAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre_display')
    search_fields = ('codigo', 'nombre_display')


@admin.register(Ubicacion)
class UbicacionAdmin(admin.ModelAdmin):
    """
    Gestión de espacios físicos del campus.
    El administrador es el único responsable de crear, editar y dar de baja ubicaciones.
    Desde aquí se controla qué salas, pisos y edificios son seleccionables al crear tickets.
    """
    list_display   = ('get_sede', 'get_edificio', 'get_piso', 'sala', 'get_tipo', 'capacidad', 'id_sap')
    list_filter    = ('piso__edificio__sede', 'piso__edificio', 'tipo')
    search_fields  = ('sala', 'piso__edificio__nombre', 'piso__edificio__sede__nombre', 'id_sap')
    ordering       = ('piso__edificio__sede__nombre', 'piso__edificio__nombre', 'piso__numero', 'sala')
    list_per_page  = 50
    
    fieldsets = (
        ('Identificación del espacio', {
            'fields': ('piso', 'sala'),
        }),
        ('Características', {
            'fields': ('tipo', 'capacidad', 'id_sap'),
            'description': 'id_sap es opcional. Se usa para integración con SAP.',
        }),
    )

    @admin.display(ordering='piso__edificio__sede__nombre', description='Sede')
    def get_sede(self, obj):
        return obj.piso.edificio.sede.nombre if obj.piso and obj.piso.edificio and obj.piso.edificio.sede else '—'

    @admin.display(ordering='piso__edificio__nombre', description='Edificio')
    def get_edificio(self, obj):
        return obj.piso.edificio.nombre if obj.piso and obj.piso.edificio else '—'

    @admin.display(ordering='piso__numero', description='Piso')
    def get_piso(self, obj):
        return f"Piso {obj.piso.numero}" if obj.piso else '—'

    @admin.display(ordering='tipo__nombre_display', description='Tipo')
    def get_tipo(self, obj):
        return obj.tipo.nombre_display if obj.tipo else '—'

    change_list_template = 'admin/app/ubicacion/change_list.html'

    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path(
                'poblar-campus-default/',
                self.admin_site.admin_view(self._poblar_campus_view),
                name='app_ubicacion_poblar',
            ),
        ]
        return extra + urls

    def _poblar_campus_view(self, request):
        total = Ubicacion.crear_default_campus()
        if total > 0:
            self.message_user(request, f'Campus poblado: {total} ubicaciones creadas (Edificio E y H).')
        else:
            self.message_user(request, 'Todas las ubicaciones ya estaban creadas — no se duplicaron.', level='WARNING')
        return HttpResponseRedirect(reverse('admin:app_ubicacion_changelist'))


# ═══════════════════════════════════════════════════════════════
# 🌟 NUEVO: REGISTRO DE ENTIDADES MAESTRAS DE USUARIO (DDL NORMALIZADO)
# ═══════════════════════════════════════════════════════════════

@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre')
    search_fields = ('codigo', 'nombre')


@admin.register(Escuela)
class EscuelaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre')
    search_fields = ('codigo', 'nombre')


@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre')
    search_fields = ('codigo', 'nombre')


# ═══════════════════════════════════════════════════════════════
# CATÁLOGOS — CategoriaTicket, CategoriaMaterial, Especialidad
# ═══════════════════════════════════════════════════════════════

@admin.register(CategoriaTicket)
class CategoriaTicketAdmin(admin.ModelAdmin):
    list_display  = ('codigo', 'nombre_display', 'activo')
    search_fields = ('codigo', 'nombre_display')
    list_filter   = ('activo',)


@admin.register(CategoriaMaterial)
class CategoriaMaterialAdmin(admin.ModelAdmin):
    list_display  = ('codigo', 'nombre_display', 'activo')
    search_fields = ('codigo', 'nombre_display')
    list_filter   = ('activo',)


@admin.register(Especialidad)
class EspecialidadAdmin(admin.ModelAdmin):
    list_display  = ('nombre', 'descripcion')
    search_fields = ('nombre',)


# ═══════════════════════════════════════════════════════════════
# MÁQUINA DE ESTADOS — EstadoCatalogo, TransicionEstado
# ═══════════════════════════════════════════════════════════════

@admin.register(EstadoCatalogo)
class EstadoCatalogoAdmin(admin.ModelAdmin):
    list_display  = ('entidad', 'codigo', 'nombre_display', 'es_inicial', 'es_final', 'orden', 'activo')
    list_filter   = ('entidad', 'es_inicial', 'es_final', 'activo')
    search_fields = ('codigo', 'nombre_display')
    ordering      = ('entidad', 'orden')


@admin.register(TransicionEstado)
class TransicionEstadoAdmin(admin.ModelAdmin):
    list_display = ('get_origen_display', 'get_destino_display', 'rol_requerido', 'activo')
    list_filter  = ('rol_requerido', 'activo')

    def get_origen_display(self, obj):
        return f"[{obj.estado_origen.entidad.upper()}] {obj.estado_origen.nombre_display}" if obj.estado_origen else '—'
    get_origen_display.short_description = 'Estado Origen'

    def get_destino_display(self, obj):
        return f"[{obj.estado_destino.nombre_display}]" if obj.estado_destino else '—'
    get_destino_display.short_description = 'Estado Destino'


# ═══════════════════════════════════════════════════════════════
# INVENTARIO — Material
# ═══════════════════════════════════════════════════════════════

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display  = ('codigo', 'nombre', 'categoria', 'unidad', 'activo')
    list_filter   = ('categoria', 'activo', 'unidad')
    search_fields = ('codigo', 'nombre')
    inlines       = [EspecialidadMaterialInline]


# ═══════════════════════════════════════════════════════════════
# SEDES Y CARRERAS — escalables vía admin
# ═══════════════════════════════════════════════════════════════

@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display  = ('nombre', 'direccion')
    search_fields = ('nombre',)


@admin.register(Carrera)
class CarreraAdmin(admin.ModelAdmin):
    list_display  = ('nombre', 'escuela', 'sede', 'activa')
    list_filter   = ('escuela', 'sede', 'activa')
    # 🌟 CORRECCIÓN 2: Modificado para buscar y ordenar cruzando el campo relacional de la escuela sin romper el admin
    search_fields = ('nombre', 'escuela__nombre')
    list_editable = ('activa',)
    ordering      = ('escuela__nombre', 'nombre')


# ═══════════════════════════════════════════════════════════════
# USUARIOS
# ═══════════════════════════════════════════════════════════════

@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display  = ('username', 'get_full_name', 'rol', 'estado_cuenta', 'fecha_registro')
    list_filter   = ('rol', 'estado_cuenta', 'vinculo')
    search_fields = ('username', 'first_name', 'last_name')
    fieldsets = UserAdmin.fieldsets + (
        ('Datos Institucionales', {
            'fields': ('rol', 'rut', 'telefono', 'correo_institucional',
                       'vinculo', 'carrera', 'jornada', 'sede', 'departamento',
                       'turno', 'estado_cuenta', 'aprobado_por'),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Datos Institucionales Iniciales', {
            'fields': ('rol', 'rut', 'correo_institucional', 'sede', 'estado_cuenta'),
        }),
    )
    inlines = [EspecialidadUsuarioInline]


@admin.register(TokenRecuperacion)
class TokenRecuperacionAdmin(admin.ModelAdmin):
    list_display   = ('usuario', 'creado_en', 'expira_en', 'usado', 'ip_solicitud')
    list_filter    = ('usado', 'creado_en')
    search_fields  = ('usuario__username', 'usuario__correo_institucional')
    readonly_fields = ('usuario', 'token', 'creado_en', 'expira_en', 'ip_solicitud')

    def has_add_permission(self, request):
        return False


# ═══════════════════════════════════════════════════════════════
# TICKETS Y OPERACIONES
# ═══════════════════════════════════════════════════════════════

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display   = ('id', 'titulo', 'estado', 'urgencia', 'categoria', 'creado_por', 'asignado_a', 'created_at')
    list_filter    = ('estado', 'urgencia', 'categoria')
    search_fields  = ('titulo', 'descripcion', 'ubicacion__piso__edificio__nombre', 'ubicacion__sala')
    readonly_fields = ('created_at', 'updated_at', 'cerrado_at')


@admin.register(AsignacionTicket)
class AsignacionTicketAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'usuario', 'rol_asignacion', 'estado', 'asignado_por', 'fecha_asignacion')
    list_filter  = ('rol_asignacion', 'estado')
    search_fields = ('ticket__titulo', 'usuario__username')


@admin.register(ValidacionGuardia)
class ValidacionGuardiaAdmin(admin.ModelAdmin):
    list_display   = ('ticket', 'guardia', 'resultado', 'checklist_electrico', 'checklist_estructural', 'checklist_accesibilidad', 'created_at')
    list_filter    = ('resultado', 'created_at')
    search_fields  = ('ticket__titulo', 'guardia__username', 'comentario')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(NoReparable)
class NoReparableAdmin(admin.ModelAdmin):
    list_display   = ('ticket', 'tecnico', 'criticidad', 'requiere_externalizacion', 'costo_estimado_externo', 'created_at')
    list_filter    = ('criticidad', 'requiere_externalizacion', 'created_at')
    search_fields  = ('ticket__titulo', 'tecnico__username', 'motivo_tecnico')
    readonly_fields = ('created_at', 'updated_at')


# ═══════════════════════════════════════════════════════════════
# MANTENCIÓN Y MATERIALES
# ═══════════════════════════════════════════════════════════════

@admin.register(RegistroMantencion)
class RegistroMantencionAdmin(admin.ModelAdmin):
    list_display  = ('id', 'ticket', 'tecnico', 'causa_raiz', 'fecha_registro')
    list_filter   = ('fecha_registro', 'tecnico')
    search_fields = ('ticket__titulo', 'tecnico__username', 'causa_raiz')


@admin.register(SesionTrabajo)
class SesionTrabajoAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket', 'tecnico', 'inicio', 'fin', 'horas_hombre', 'tipo_cierre', 'progreso')
    list_filter  = ('personal_adicional_requerido', 'requiere_nivel_mayor', 'tipo_cierre', 'created_at')
    search_fields = ('ticket__titulo', 'tecnico__username', 'descripcion_avance')
    inlines      = [MaterialUtilizadoInline]


@admin.register(MaterialUtilizado)
class MaterialUtilizadoAdmin(admin.ModelAdmin):
    list_display   = ('material', 'cantidad_utilizada', 'sesion_trabajo', 'get_ticket', 'get_tecnico')
    list_filter    = ('material__categoria', 'sesion_trabajo__created_at')
    search_fields  = ('material__nombre', 'material__codigo', 'sesion_trabajo__ticket__titulo')
    readonly_fields = ('sesion_trabajo', 'material', 'cantidad_utilizada', 'observacion')

    @admin.display(description='Ticket')
    def get_ticket(self, obj):
        return obj.sesion_trabajo.ticket

    @admin.display(description='Técnico')
    def get_tecnico(self, obj):
        return obj.sesion_trabajo.tecnico

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MaterialesFaltantes)
class MaterialesFaltantesAdmin(admin.ModelAdmin):
    list_display  = ('sesion_trabajo', 'material', 'cantidad_requerida', 'cantidad_recibida', 'estado', 'fecha_solicitud')
    list_filter   = ('estado', 'fecha_solicitud')
    search_fields = ('material__nombre', 'observaciones')


# ═══════════════════════════════════════════════════════════════
# RECURSOS HUMANOS — Inasistencia
# ═══════════════════════════════════════════════════════════════

@admin.register(Inasistencia)
class InasistenciaAdmin(admin.ModelAdmin):
    list_display   = ('usuario', 'fecha_desde', 'fecha_hasta', 'motivo', 'estado', 'revisado_por', 'created_at')
    list_filter    = ('motivo', 'estado', 'fecha_desde')
    search_fields  = ('usuario__first_name', 'usuario__last_name', 'usuario__correo_institucional', 'detalle')
    readonly_fields = ('created_at',)


# ═══════════════════════════════════════════════════════════════
# NOTIFICACIONES
# ═══════════════════════════════════════════════════════════════

@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display   = ('destinatario', 'tipo', 'prioridad', 'titulo', 'leida', 'archivada', 'created_at')
    list_filter    = ('tipo', 'prioridad', 'leida', 'archivada')
    search_fields  = ('titulo', 'mensaje', 'destinatario__username')
    readonly_fields = ('created_at',)
    actions        = ['marcar_como_leidas', 'archivar_seleccionadas']

    @admin.action(description='Marcar seleccionadas como leídas')
    def marcar_como_leidas(self, request, queryset):
        n = queryset.filter(leida=False).update(leida=True)
        self.message_user(request, f'{n} notificaciones marcadas como leídas.')

    @admin.action(description='Archivar seleccionadas')
    def archivar_seleccionadas(self, request, queryset):
        n = queryset.filter(archivada=False).update(archivada=True)
        self.message_user(request, f'{n} notificaciones archivadas.')


# ═══════════════════════════════════════════════════════════════
# AUDITORÍA — solo lectura
# ═══════════════════════════════════════════════════════════════

@admin.register(LogAuditoria)
class LogAuditoriaAdmin(admin.ModelAdmin):
    list_display   = ('created_at', 'accion', 'usuario', 'ticket', 'ip_address')
    list_filter    = ('modulo', 'es_interno')
    readonly_fields = [f.name for f in LogAuditoria._meta.fields]
    search_fields  = ('accion', 'usuario__username')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(HistorialAcciones)
class HistorialAccionesAdmin(admin.ModelAdmin):
    list_display   = ('ticket', 'usuario', 'tipo_accion', 'estado_anterior', 'estado_nuevo', 'es_global', 'created_at')
    list_filter    = ('tipo_accion', 'es_global')
    search_fields  = ('descripcion', 'usuario__username')
    readonly_fields = ('created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ═══════════════════════════════════════════════════════════════
# PERSONALIZACIÓN DEL BACK-OFFICE
# ═══════════════════════════════════════════════════════════════

admin.site.site_header = 'Campus Seguro – Administración'
admin.site.site_title  = 'Campus Seguro'
admin.site.index_title = 'Panel de Administración'