from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Usuario, TokenRecuperacion, Ubicacion, Material, Ticket,
    ValidacionGuardia, AsignacionTicket, RegistroMantencion, MaterialUtilizado,
    NoReparable, LogAuditoria, Notificacion, Inasistencia,
    HistorialAcciones, MaterialesFaltantes, EstadoCatalogo, TransicionEstado,
)


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'get_full_name', 'rol', 'estado_cuenta', 'correo_institucional', 'fecha_registro')
    list_filter = ('rol', 'estado_cuenta', 'vinculo')
    search_fields = ('username', 'first_name', 'last_name', 'correo_institucional', 'rut')
    fieldsets = UserAdmin.fieldsets + (
        ('Datos Institucionales', {
            'fields': ('rol', 'rut', 'telefono', 'correo_institucional',
                       'vinculo', 'carrera', 'jornada', 'sede', 'departamento',
                       'especialidad', 'turno', 'estado_cuenta', 'aprobado_por'),
        }),
    )


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'titulo', 'estado', 'urgencia', 'categoria', 'creado_por', 'asignado_a', 'created_at')
    list_filter = ('estado', 'urgencia', 'categoria')
    search_fields = ('titulo', 'descripcion', 'ubicacion__edificio', 'ubicacion__sala')
    readonly_fields = ('created_at', 'updated_at', 'cerrado_at')


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'categoria', 'stock_actual', 'stock_minimo', 'activo')
    list_filter = ('categoria', 'activo')
    search_fields = ('codigo', 'nombre')


@admin.register(LogAuditoria)
class LogAuditoriaAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'accion', 'usuario', 'ticket', 'ip_address')
    list_filter = ('modulo', 'es_interno')
    readonly_fields = [f.name for f in LogAuditoria._meta.fields]
    search_fields = ('accion', 'usuario__username')


@admin.register(AsignacionTicket)
class AsignacionTicketAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'usuario', 'rol_asignacion', 'estado', 'asignado_por', 'fecha_asignacion')
    list_filter = ('rol_asignacion', 'estado')
    search_fields = ('ticket__titulo', 'usuario__username')


@admin.register(HistorialAcciones)
class HistorialAccionesAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'usuario', 'tipo_accion', 'estado_anterior', 'estado_nuevo', 'es_global', 'created_at')
    list_filter = ('tipo_accion', 'es_global')
    search_fields = ('descripcion', 'usuario__username')
    readonly_fields = ('created_at',)


@admin.register(EstadoCatalogo)
class EstadoCatalogoAdmin(admin.ModelAdmin):
    list_display = ('entidad', 'codigo', 'nombre_display', 'es_inicial', 'es_final', 'orden', 'activo')
    list_filter = ('entidad', 'es_inicial', 'es_final', 'activo')
    search_fields = ('codigo', 'nombre_display')
    ordering = ('entidad', 'orden')


@admin.register(TransicionEstado)
class TransicionEstadoAdmin(admin.ModelAdmin):
    list_display = ('estado_origen', 'estado_destino', 'rol_requerido', 'activo')
    list_filter = ('rol_requerido', 'activo')


admin.site.register([
    TokenRecuperacion, Ubicacion, ValidacionGuardia,
    RegistroMantencion, MaterialUtilizado, NoReparable,
    Notificacion, Inasistencia, MaterialesFaltantes,
])

admin.site.site_header = 'Campus Seguro – Administración'
admin.site.site_title = 'Campus Seguro'
admin.site.index_title = 'Panel de Administración'
