from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CategoriaMaterial, CategoriaTicket, Usuario, TokenRecuperacion, Ubicacion, Material, Ticket,
    SesionTrabajo, ValidacionGuardia, AsignacionTicket, RegistroMantencion, MaterialUtilizado,
    NoReparable, LogAuditoria, Notificacion, Inasistencia,
    HistorialAcciones, MaterialesFaltantes, EstadoCatalogo, TransicionEstado,
    Especialidad, EspecialidadUsuario, EspecialidadMaterial,
)

# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE INLINES (Relaciones M:N y Transaccionales)
# ═══════════════════════════════════════════════════════════════

class EspecialidadUsuarioInline(admin.TabularInline):
    """Permite asignar especialidades a un técnico desde el perfil de Usuario"""
    model = EspecialidadUsuario
    extra = 1


class EspecialidadMaterialInline(admin.TabularInline):
    """Permite amarrar especialidades a un insumo desde el perfil de Material"""
    model = EspecialidadMaterial
    extra = 1


class MaterialUtilizadoInline(admin.TabularInline):
    """Muestra los materiales gastados directamente dentro de la ficha de mantención"""
    model = MaterialUtilizado
    extra = 1

@admin.register(SesionTrabajo)
class SesionTrabajoAdmin(admin.ModelAdmin):
    """Historial analítico de las sesiones cronometradas de los técnicos."""
    list_display = ('id', 'ticket', 'tecnico', 'inicio', 'fin', 'horas_hombre', 'tipo_cierre', 'progreso')
    list_filter = ('personal_adicional_requerido', 'requiere_nivel_mayor', 'tipo_cierre', 'created_at')
    search_fields = ('ticket__titulo', 'tecnico__username', 'descripcion_avance')
    inlines = [MaterialUtilizadoInline]

# ═══════════════════════════════════════════════════════════════
# REGISTROS DE ADMINISTRACIÓN PRINCIPALES
# ═══════════════════════════════════════════════════════════════

@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'get_full_name', 'rol', 'estado_cuenta', 'correo_institucional', 'fecha_registro')
    list_filter = ('rol', 'estado_cuenta', 'vinculo')
    search_fields = ('username', 'first_name', 'last_name', 'correo_institucional', 'rut')
    
    # Formulario de EDICIÓN de usuarios existentes
    fieldsets = UserAdmin.fieldsets + (
        ('Datos Institucionales', {
            'fields': ('rol', 'rut', 'telefono', 'correo_institucional',
                       'vinculo', 'carrera', 'jornada', 'sede', 'departamento',
                       'turno', 'estado_cuenta', 'aprobado_por'),
        }),
    )

    # Formulario de CREACIÓN de nuevos usuarios desde el panel
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Datos Institucionales Iniciales', {
            'fields': ('rol', 'rut', 'correo_institucional', 'sede', 'estado_cuenta'),
        }),
    )
    
    inlines = [EspecialidadUsuarioInline]


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    # ✔️ CORREGIDO: Removidas las referencias a stock_actual y stock_minimo
    list_display = ('codigo', 'nombre', 'categoria', 'unidad', 'activo')
    list_filter = ('categoria', 'activo', 'unidad')
    search_fields = ('codigo', 'nombre')
    inlines = [EspecialidadMaterialInline]


@admin.register(RegistroMantencion)
class RegistroMantencionAdmin(admin.ModelAdmin):
    """Ficha operativa de la reparación final (Acta de Cierre)."""
    list_display = ('id', 'ticket', 'tecnico', 'causa_raiz', 'fecha_registro')
    list_filter = ('fecha_registro', 'tecnico')
    search_fields = ('ticket__titulo', 'tecnico__username', 'causa_raiz')

# ═══════════════════════════════════════════════════════════════
# REGISTRO DE TABLAS MAESTRAS DE CATEGORÍAS (3FN)
# ═══════════════════════════════════════════════════════════════

@admin.register(CategoriaTicket)
class CategoriaTicketAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre_display', 'activo')
    search_fields = ('codigo', 'nombre_display')
    list_filter = ('activo',)


@admin.register(CategoriaMaterial)
class CategoriaMaterialAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre_display', 'activo')
    search_fields = ('codigo', 'nombre_display')
    list_filter = ('activo',)


@admin.register(Especialidad)
class EspecialidadAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)

# ═══════════════════════════════════════════════════════════════
# RESTO DE ENTIDADES DEL SISTEMA
# ═══════════════════════════════════════════════════════════════

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'titulo', 'estado', 'urgencia', 'categoria', 'creado_por', 'asignado_a', 'created_at')
    list_filter = ('estado', 'urgencia', 'categoria')
    search_fields = ('titulo', 'descripcion', 'ubicacion__edificio', 'ubicacion__sala')
    readonly_fields = ('created_at', 'updated_at', 'cerrado_at')


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


# Registros planos simplificados de entidades menores (Removidos los modelos anidados)
admin.site.register([
    TokenRecuperacion, Ubicacion, ValidacionGuardia,
    NoReparable, Notificacion, Inasistencia, MaterialesFaltantes,
])

# Personalización del Back-Office institucional
admin.site.site_header = 'Campus Seguro – Administración'
admin.site.site_title = 'Campus Seguro'
admin.site.index_title = 'Panel de Administración'