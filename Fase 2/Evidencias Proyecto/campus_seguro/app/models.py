from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from django.utils import timezone
from django.utils.crypto import get_random_string

# ═══════════════════════════════════════════════════════════════
# CATÁLOGO GLOBAL DE ESTADOS (normalización – feedback profesora)
# Tabla 2 del DDL v2.0: reemplaza CHECKs dispersos en 6 entidades
# ═══════════════════════════════════════════════════════════════
class EstadoCatalogo(models.Model):
    """Catálogo ÚNICO de estados del sistema. Centraliza todos los estados de
    ticket, cuenta, asignación, inasistencia y material_faltante."""
    ENTIDAD_CHOICES = [
        ('ticket', 'Ticket'),
        ('ticket_sub', 'Sub-estado de Ticket'),
        ('cuenta', 'Cuenta de Usuario'),
        ('asignacion', 'Asignación de Ticket'),
        ('inasistencia', 'Inasistencia'),
        ('material_faltante', 'Material Faltante'),
    ]

    entidad = models.CharField(max_length=20, choices=ENTIDAD_CHOICES)
    codigo = models.CharField(max_length=30)
    nombre_display = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=300, blank=True, null=True)
    es_inicial = models.BooleanField(default=False)
    es_final = models.BooleanField(default=False)
    orden = models.PositiveIntegerField(default=0)
    color_hex = models.CharField(max_length=7, blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        unique_together = ('entidad', 'codigo')
        ordering = ['entidad', 'orden']
        verbose_name = 'Estado del Catálogo'
        verbose_name_plural = 'Catálogo de Estados'

    def __str__(self):
        return self.nombre_display

    @classmethod
    def para(cls, entidad, codigo):
        """Shortcut para obtener un estado por entidad y código (sin hardcodear IDs)."""
        return cls.objects.get(entidad=entidad, codigo=codigo)


# ═══════════════════════════════════════════════════════════════
# MÁQUINA DE ESTADOS N-N (tabla 3 del DDL v2.0)
# ═══════════════════════════════════════════════════════════════
class TransicionEstado(models.Model):
    """Tabla N-N: define qué transiciones de estado son válidas y qué rol las autoriza."""
    ROL_CHOICES = [
        ('usuario', 'Usuario Base'),
        ('gestor', 'Gestor'),
        ('guardia', 'Guardia'),
        ('mantencion', 'Mantención'),
    ]

    estado_origen = models.ForeignKey(
        EstadoCatalogo, on_delete=models.CASCADE, related_name='transiciones_origen'
    )
    estado_destino = models.ForeignKey(
        EstadoCatalogo, on_delete=models.CASCADE, related_name='transiciones_destino'
    )
    rol_requerido = models.CharField(max_length=20, choices=ROL_CHOICES, blank=True, null=True)
    descripcion = models.CharField(max_length=200, blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        unique_together = ('estado_origen', 'estado_destino')
        verbose_name = 'Transición de Estado'
        verbose_name_plural = 'Transiciones de Estado'

    def __str__(self):
        return f"{self.estado_origen} → {self.estado_destino}"

# Clase maestra de Especialidades
class Especialidad(models.Model):
    nombre = models.CharField(max_length=100) # Electricista SEC, Cerrajero, etc.
    descripcion = models.CharField(max_length=250, blank=True, null=True)

    def __str__(self):
        return self.nombre

# ═══════════════════════════════════════════════════════════════
# NUEVO: TABLAS MAESTRAS PARA CATEGORÍAS DE TICKETS Y MATERIALES
# ═══════════════════════════════════════════════════════════════
class CategoriaTicket(models.Model):
    """Tabla maestra para la clasificación analítica de fallas y KPIs en los dashboards"""
    codigo = models.CharField(max_length=30, unique=True)
    nombre_display = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=300, blank=True, null=True)
    activo = models.BooleanField(default=True)
    

    class Meta:
        verbose_name = 'Categoría de Ticket'
        verbose_name_plural = 'Categorías de Tickets'

    def __str__(self):
        return self.nombre_display


class CategoriaMaterial(models.Model):
    """Tabla maestra para la ordenación logística del inventario del pañol"""
    codigo = models.CharField(max_length=30, unique=True)
    nombre_display = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=300, blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Categoría de Material'
        verbose_name_plural = 'Categorías de Materiales'

    def __str__(self):
        return self.nombre_display

# ═══════════════════════════════════════════════════════════════
# ESTRUCTURA GEOGRÁFICA Y DE INFRAESTRUCTURA NORMALIZADA
# Reemplaza el antiguo catálogo plano hardcodeado
# ═══════════════════════════════════════════════════════════════

class Sede(models.Model):
    """Sedes de la institución (ej: Sede Principal, Sede Norte, etc.)"""
    nombre = models.CharField(max_length=100, unique=True)
    direccion = models.CharField(max_length=250, blank=True, null=True)

    class Meta:
        verbose_name = 'Sede'
        verbose_name_plural = 'Sedes'

    def __str__(self):
        return self.nombre


class Edificio(models.Model):
    """Edificios pertenecientes a una Sede específica"""
    sede = models.ForeignKey(Sede, on_delete=models.CASCADE, related_name='edificios')
    nombre = models.CharField(max_length=100) # Ej: "Edificio E", "Edificio H"

    class Meta:
        verbose_name = 'Edificio'
        verbose_name_plural = 'Edificios'
        unique_together = ('sede', 'nombre')

    def __str__(self):
        return f"{self.nombre} ({self.sede.nombre})"


class Piso(models.Model):
    """Pisos o niveles pertenecientes a un Edificio"""
    edificio = models.ForeignKey(Edificio, on_delete=models.CASCADE, related_name='pisos')
    numero = models.CharField(max_length=10) # Ej: "1", "2", "Subterráneo"

    class Meta:
        verbose_name = 'Piso'
        verbose_name_plural = 'Pisos'
        unique_together = ('edificio', 'numero')

    def __str__(self):
        return f"Piso {self.numero} – {self.edificio.nombre}"


class TipoUbicacion(models.Model):
    """Categorías de salas (Aula, Laboratorio, Baño, Pasillo, etc.)"""
    codigo = models.CharField(max_length=30, unique=True) # Ej: "aula", "baño"
    nombre_display = models.CharField(max_length=100)      # Ej: "Aula", "Baño"

    class Meta:
        verbose_name = 'Tipo de Ubicación'
        verbose_name_plural = 'Tipos de Ubicaciones'

    def __str__(self):
        return self.nombre_display


class Ubicacion(models.Model):
    """La unidad mínima espacial (Sala, Laboratorio o Baño concreto)"""
    piso = models.ForeignKey(Piso, on_delete=models.CASCADE, related_name='ubicaciones')
    tipo = models.ForeignKey(TipoUbicacion, on_delete=models.PROTECT, related_name='ubicaciones')
    sala = models.CharField(max_length=50) # Ej: "E001", "Baño P2"
    id_sap = models.CharField(max_length=50, unique=True, blank=True, null=True)
    capacidad = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        unique_together = ('piso', 'sala')
        ordering = ['piso__edificio__sede', 'piso__edificio', 'piso__numero', 'sala']
        verbose_name = 'Ubicación'
        verbose_name_plural = 'Ubicaciones'

    def __str__(self):
        # Mantiene la estética original conservando la compatibilidad de tus mensajes anteriores
        return f"{self.piso.edificio.sede.nombre} – {self.piso.edificio.nombre} P{self.piso.numero} {self.sala}"

    @classmethod
    def crear_default_campus(cls):
        """
        Crea la estructura relacional por defecto para el Campus Seguro,
        vinculando toda la infraestructura a la Sede San Andrés de Concepción.
        Incluye aulas, baños, pasillos, escaleras, ascensores y el casino central.
        """
        print("🏗️  Creando ubicaciones normalizadas del Campus Seguro...")
        
        # 1. Crear o recuperar la Sede
        sede_institucional, _ = Sede.objects.get_or_create(nombre='Sede San Andrés de Concepción')
        
        # 2. Catálogo Maestro de Tipos de Ubicación (AÑADIDOS: ascensor y casino)
        tipos_dict = {
            'aula': 'Aula',
            'laboratorio': 'Laboratorio',
            'taller': 'Taller',
            'baño': 'Baño',
            'pasillo': 'Pasillo',
            'escalera': 'Escalera',
            'ascensor': 'Ascensor',  # <-- Nuevo Tipo
            'casino': 'Casino',      # <-- Nuevo Tipo
            'oficina': 'Oficina',
            'area_comun': 'Área Común',
            'otro': 'Otro',
        }
        tipos_maestros = {}
        for cod, nom in tipos_dict.items():
            tipo_obj, _ = TipoUbicacion.objects.get_or_create(codigo=cod, defaults={'nombre_display': nom})
            tipos_maestros[cod] = tipo_obj
        
        # Configuración física de los edificios E y H
        edificios_config = {
            'E': {
                'pisos': range(1, 6),  # Pisos 1 al 5
                'salas_por_piso': 16,
                'banos_por_piso': {2: 1},
            },
            'H': {
                'pisos': range(1, 9),  # Pisos 1 al 8
                'salas_por_piso': 16,
                'banos_por_piso': {p: 1 for p in range(1, 9)},
            }
        }
        
        total_creadas = 0
        
        for letra, config in edificios_config.items():
            edificio_obj, _ = Edificio.objects.get_or_create(
                sede=sede_institucional, 
                nombre=f"Edificio {letra}"
            )
            
            for num_piso in config['pisos']:
                piso_obj, _ = Piso.objects.get_or_create(
                    edificio=edificio_obj, 
                    numero=str(num_piso)
                )
                
                # 4. Crear Aulas
                for num_sala in range(1, config['salas_por_piso'] + 1):
                    nombre_sala = f"{letra}{num_sala:03d}"
                    _, creada = cls.objects.get_or_create(
                        piso=piso_obj,
                        sala=nombre_sala,
                        defaults={'tipo': tipos_maestros['aula'], 'capacidad': 30}
                    )
                    if creada: total_creadas += 1
                
                # 5. Crear Baños
                if num_piso in config['banos_por_piso']:
                    num_banos = config['banos_por_piso'][num_piso]
                    for num_bano in range(1, num_banos + 1):
                        _, creada = cls.objects.get_or_create(
                            piso=piso_obj,
                            sala=f"Baño P{num_piso}",
                            defaults={'tipo': tipos_maestros['baño'], 'capacidad': None}
                        )
                        if creada: total_creadas += 1
                
                # 6. Crear Zonas de Tránsito (AÑADIDO: ascensor por cada piso)
                zonas_especiales = [
                    ('pasillo', f"Pasillo General P{num_piso}"),
                    ('escalera', f"Escalera General P{num_piso}"),
                    ('ascensor', f"Ascensor Principal P{num_piso}")  # <-- Se creará en cada piso
                ]
                
                for codigo_tipo, nombre_zona in zonas_especiales:
                    _, creada = cls.objects.get_or_create(
                        piso=piso_obj,
                        sala=nombre_zona,
                        defaults={'tipo': tipos_maestros[codigo_tipo], 'capacidad': None}
                    )
                    if creada: total_creadas += 1
                
                # 7. LÓGICA EXCLUSIVA: Crear el Casino Central solo en el Edificio E - Piso 1
                if letra == 'E' and num_piso == 1:
                    _, creada = cls.objects.get_or_create(
                        piso=piso_obj,
                        sala="Casino Central",
                        defaults={
                            'tipo': tipos_maestros['casino'], 
                            'capacidad': 150  # El casino sí tiene aforo/capacidad estimada
                        }
                    )
                    if creada: total_creadas += 1
                            
        print(f"✨ ¡Estructura relacional sembrada con Ascensores y Casino! Total: {total_creadas}")
        return total_creadas

# ═══════════════════════════════════════════════════════════════
# USUARIO PERSONALIZADO (registro institucional)
# ══════════════════════════════════════════════════════════════
class UsuarioManager(UserManager):
    """Manager personalizado que asigna estado_cuenta automáticamente."""

    def _create_user(self, username, email, password, **extra_fields):
        if 'estado_cuenta' not in extra_fields or extra_fields['estado_cuenta'] is None:
            extra_fields['estado_cuenta'] = EstadoCatalogo.para('cuenta', 'activa')
        if 'rut' not in extra_fields:
            extra_fields.setdefault('rut', username)
        if 'correo_institucional' not in extra_fields:
            extra_fields.setdefault('correo_institucional', email or f'{username}@campus.cl')
        return super()._create_user(username, email, password, **extra_fields)


class Usuario(AbstractUser):
    ROL_CHOICES = [
        ('usuario', 'Usuario Base'),
        ('gestor', 'Gestor'),
        ('guardia', 'Guardia'),
        ('mantencion', 'Mantención'),
    ]
    VINCULO_CHOICES = [
        ('alumno', 'Alumno'),
        ('docente', 'Docente'),
        ('administrativo', 'Administrativo'),
        ('funcionario', 'Funcionario'),
    ]
    JORNADA_CHOICES = [
        ('diurna', 'Diurna'),
        ('vespertina', 'Vespertina'),
        ('mixta', 'Mixta'),
    ]
    # Datos institucionales obligatorios
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default='usuario')
    rut = models.CharField(max_length=12, unique=True)
    telefono = models.CharField(max_length=15, blank=True, null=True)
    correo_institucional = models.EmailField(unique=True)

    # Datos académicos (para usuario base)
    vinculo = models.CharField(max_length=20, choices=VINCULO_CHOICES, blank=True, null=True)
    carrera = models.CharField(max_length=100, blank=True, null=True)
    jornada = models.CharField(max_length=15, choices=JORNADA_CHOICES, blank=True, null=True)
    sede = models.ForeignKey(Sede, on_delete=models.SET_NULL, blank=True, null=True, related_name='estudiantes_funcionarios')
    departamento = models.CharField(max_length=100, blank=True, null=True)

    # Datos operativos (guardia / mantención)
    # CharField de especialidad cambiado por una relación real Muchos a Muchos:
    especialidades = models.ManyToManyField(
        Especialidad, 
        through='EspecialidadUsuario', 
        blank=True,
        related_name='tecnicos'
    )
    turno = models.CharField(max_length=50, blank=True, null=True)  # mañana / tarde / noche

    # Control
    estado_cuenta = models.ForeignKey(
        EstadoCatalogo,
        on_delete=models.PROTECT,
        related_name='usuarios',
        limit_choices_to={'entidad': 'cuenta'},
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_aprobacion = models.DateTimeField(null=True, blank=True)
    aprobado_por = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='cuentas_aprobadas')
    activo = models.BooleanField(default=True)

    # ── Auth0 ────────────────────────────────────────────────
    # Identificador único del usuario en Auth0 (Subject claim del JWT).
    # Formato: "auth0|<id>" — ejemplo: "auth0|66a1b2c3d4e5f6a7b8c9d0e1"
    # Nulo cuando Auth0 no está configurado (autenticación local de desarrollo).
    # Cuando existe, se usa para vincular la sesión Auth0 con el usuario local
    # y para llamadas a la Management API (actualizar rol, revocar sesiones).
    auth0_sub = models.CharField(
        max_length=120,
        unique=True,
        null=True,
        blank=True,
        verbose_name='Auth0 Subject ID',
        help_text='Identificador único del usuario en Auth0. Se asigna automáticamente al registrar vía Auth0.',
    )

    objects = UsuarioManager()

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_rol_display()})"

    def get_estado_cuenta_display(self):
        return self.estado_cuenta.nombre_display if self.estado_cuenta_id else ''

    @property
    def puede_ingresar(self):
        return self.estado_cuenta.codigo == 'activa' and self.activo

    @property
    def tiene_inasistencia_activa(self):
        hoy = timezone.now().date()
        return self.inasistencias.filter(
            fecha_desde__lte=hoy,
            fecha_hasta__gte=hoy,
            estado__codigo='aprobada'
        ).exists()

    @property
    def inasistencia_activa_detalle(self):
        hoy = timezone.now().date()
        return self.inasistencias.filter(
            fecha_desde__lte=hoy,
            fecha_hasta__gte=hoy,
            estado__codigo='aprobada'
        ).first()

    def puede_asumir_tickets(self):
        return not self.tiene_inasistencia_activa and self.estado_cuenta.codigo == 'activa' and self.activo

# Tabla intermedia explícita para la relación Muchos a Muchos entre Usuario y Especialidad,
# permitiendo agregar campos adicionales en el futuro si es necesario (por ejemplo, fecha de obtención de la especialidad, certificación, etc.).
class EspecialidadUsuario(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    especialidad = models.ForeignKey(Especialidad, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('usuario', 'especialidad')

# ═══════════════════════════════════════════════════════════════
# RECUPERACIÓN DE CONTRASEÑA
# ═══════════════════════════════════════════════════════════════
class TokenRecuperacion(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='tokens_recuperacion')
    token = models.CharField(max_length=64, unique=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    expira_en = models.DateTimeField()
    usado = models.BooleanField(default=False)
    ip_solicitud = models.GenericIPAddressField(null=True, blank=True)

    @classmethod
    def generar(cls, usuario, ip=None, horas=2):
        token = get_random_string(48)
        return cls.objects.create(
            usuario=usuario,
            token=token,
            expira_en=timezone.now() + timezone.timedelta(hours=horas),
            ip_solicitud=ip,
        )

    @property
    def es_valido(self):
        return not self.usado and timezone.now() < self.expira_en

# ═══════════════════════════════════════════════════════════════
# CATÁLOGO DE MATERIALES (BI compras inteligentes)
# ═══════════════════════════════════════════════════════════════
class Material(models.Model):
    UNIDAD_CHOICES = [
        ('unidad', 'Unidad'),
        ('metro', 'Metro'),
        ('kg', 'Kilogramo'),
        ('litro', 'Litro'),
        ('caja', 'Caja'),
        ('rollo', 'Rollo'),
    ]
    codigo = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=200)
    # 🔗 RELACIÓN CAMBIADA: De CharField plano a Llave Foránea Real
    categoria = models.ForeignKey(CategoriaMaterial, on_delete=models.PROTECT, related_name='materiales')
    unidad = models.CharField(max_length=20, choices=UNIDAD_CHOICES)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    # 🔗 RELACIÓN DE SEGURIDAD: Para filtrar en el formulario del técnico
    especialidades = models.ManyToManyField(
        Especialidad,
        through='EspecialidadMaterial',
        blank=True,
        related_name='materiales',
        help_text="Especialidades que están autorizadas a ver y usar este material en sus reportes."
    )

    class Meta:
        ordering = ['categoria__nombre_display', 'nombre']

    def __str__(self):
        return f"{self.codigo} – {self.nombre}"
    
    @property
    def total_utilizado(self):
        """Calcula el total histórico consumido sumando los registros de MaterialUtilizado"""
        return sum(consumo.cantidad_utilizada for consumo in self.consumos.all())

class EspecialidadMaterial(models.Model):
    """Tabla intermedia para cumplir con el DER y mapear qué materiales ve cada oficio"""
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    especialidad = models.ForeignKey(Especialidad, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('material', 'especialidad')
        verbose_name = 'Especialidad de Material'
        verbose_name_plural = 'Especialidades de Materiales'

    def __str__(self):
        return f"{self.material.nombre} - {self.especialidad.nombre}"

# ═══════════════════════════════════════════════════════════════
# TICKET
# ═══════════════════════════════════════════════════════════════
class Ticket(models.Model):
    URGENCIA_CHOICES = [
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta'),
        ('critica', 'Crítica'),
    ]
    PAUSA_CHOICES = [
        ('material', 'En Pausa – Aprobación de materiales'),
        ('personal', 'En Pausa – Personal técnico'),
        ('nivel_mayor', 'En Pausa – Peritaje (análisis técnico)'),
        ('externalizacion', 'En Pausa – Requiere externalización'),
    ]

    # Relaciones
    creado_por = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='tickets_creados')
    asignado_a = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets_asignados')
    validado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets_validados')
    gestor_responsable = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets_gestionados')

    # Estado (FK a EstadoCatalogo – sin hardcodeos de VARCHAR)
    estado = models.ForeignKey(
        EstadoCatalogo,
        on_delete=models.PROTECT,
        related_name='tickets_estado',
        limit_choices_to={'entidad': 'ticket'},
    )
    sub_estado = models.ForeignKey(
        EstadoCatalogo,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tickets_sub_estado',
        limit_choices_to={'entidad': 'ticket_sub'},
    )
    estado_pausa = models.CharField(max_length=120, blank=True, null=True)
    motivo_pausa = models.TextField(blank=True, null=True)
    comentario_reactivacion = models.TextField(blank=True, null=True)

    # Ubicación (FK obligatoria — única fuente de verdad, DDL v3.0)
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.PROTECT, related_name='tickets')

    # Clasificación
    # 🔗 RELACIÓN CAMBIADA: De CharField plano a Llave Foránea Real hacia el catálogo dinámico
    categoria = models.ForeignKey(CategoriaTicket, on_delete=models.PROTECT, related_name='tickets')
    urgencia = models.CharField(max_length=10, choices=URGENCIA_CHOICES, default='media')
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField()

    # Impacto
    afecta_clase = models.BooleanField(default=False)
    riesgo_electrico = models.BooleanField(default=False)
    riesgo_estructural = models.BooleanField(default=False)
    riesgo_accesibilidad = models.BooleanField(default=False)

    # Evidencia
    foto_evidencia = models.ImageField(upload_to='tickets/evidencia/', null=True, blank=True)

    # Activo vinculado (BI)
    id_activo_sap = models.CharField(max_length=50, blank=True, null=True)

    # Control de trabajo de mantención
    inicio_trabajo_at = models.DateTimeField(null=True, blank=True)

    # Auditoría
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cerrado_at = models.DateTimeField(null=True, blank=True)
    cancelado_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def get_estado_display(self):
        return self.estado.nombre_display if self.estado_id else ''

    def get_sub_estado_display(self):
        return self.sub_estado.nombre_display if self.sub_estado_id else ''

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.estado = EstadoCatalogo.para('ticket', 'eliminado')
        self.save()

    def es_editable(self):
        return self.estado.codigo == 'enviado' and self.deleted_at is None

    def __str__(self):
        return f"#{self.pk} – {self.titulo}"

    @property
    def tiempo_resolucion(self):
        if self.cerrado_at:
            return self.cerrado_at - self.created_at
        return None
    
    @property
    def esta_estimado(self):
        """Retorna True si el técnico actual ya ingresó las horas estimadas en su asignación."""
        if not self.asignado_a:
            return False
        # Busca la asignación que corresponde al técnico que tiene el ticket actualmente
        asignacion = self.asignaciones.filter(usuario=self.asignado_a).first()
        return asignacion.tiempo_estimado is not None if asignacion else False

    @property
    def obtener_tiempo_estimado(self):
        """Retorna el valor numérico del tiempo estimado para mostrarlo en la interfaz."""
        if self.asignado_a:
            asignacion = self.asignaciones.filter(usuario=self.asignado_a).first()
            if asignacion:
                return asignacion.tiempo_estimado
        return 0


# ═══════════════════════════════════════════════════════════════
# VALIDACIÓN GUARDIA
# ═══════════════════════════════════════════════════════════════
class ValidacionGuardia(models.Model):
    RESULTADO_CHOICES = [
        ('valido', 'Válido'),
        ('invalido', 'Inválido'),
    ]

    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name='validacion')
    guardia = models.ForeignKey(Usuario, on_delete=models.PROTECT)
    resultado = models.CharField(max_length=10, choices=RESULTADO_CHOICES)
    comentario = models.TextField()
    foto_evidencia = models.ImageField(upload_to='validaciones/', null=True, blank=True)
    checklist_electrico = models.BooleanField(default=False)
    checklist_estructural = models.BooleanField(default=False)
    checklist_accesibilidad = models.BooleanField(default=False)
    evidencia_obligatoria_presente = models.BooleanField(default=False)
    tiempo_validacion_minutos = models.PositiveIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Validación #{self.ticket.pk} – {self.get_resultado_display()}"


# ═══════════════════════════════════════════════════════════════
# ASIGNACIÓN DE TICKET (N-N Ticket ↔ Usuario) – HU-07, HU-09
# ═══════════════════════════════════════════════════════════════
class AsignacionTicket(models.Model):
    """Tabla de intersección N-N entre Ticket y Usuario para asignación de guardias y técnicos."""
    ROL_ASIGNACION_CHOICES = [
        ('guardia', 'Guardia'),
        ('mantencion', 'Mantención'),
    ]

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='asignaciones')
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='asignaciones_recibidas')
    rol_asignacion = models.CharField(max_length=20, choices=ROL_ASIGNACION_CHOICES)
    asignado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='asignaciones_realizadas')
    estado = models.ForeignKey(
        EstadoCatalogo,
        on_delete=models.PROTECT,
        related_name='asignaciones_estado',
        limit_choices_to={'entidad': 'asignacion'},
    )
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    fecha_completado = models.DateTimeField(null=True, blank=True)
    
    # ═══════════════════════════════════════════════════════════════
    # NUEVO: Campo para TARJETA 08 - Asignación de Guardia para Validar
    # Permite programar la fecha en que el guardia debe realizar la validación
    # en terreno. Se usa para filtrar guardias disponibles y mostrar en el
    # dashboard del guardia la fecha programada de cada revisión asignada.
    # ═══════════════════════════════════════════════════════════════
    fecha_programada = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha programada',
        help_text='Fecha en la que se debe realizar la validación o el trabajo asignado'
    )
    
    # ⏱️ Nuevos Atributos del Análisis Preliminar / Reasignaciones Estables
    tiempo_estimado = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Horas estimadas de trabajo real.")
    diagnostico_preliminar = models.TextField(null=True, blank=True, help_text="Diagnóstico inicial ingresado por el mantenedor.")

    class Meta:
        db_table = 'asignacion_ticket'
        ordering = ['-fecha_asignacion']

    def get_estado_display(self):
        return self.estado.nombre_display if self.estado_id else ''

    def __str__(self):
        return f"Ticket #{self.ticket.pk} → {self.usuario} ({self.get_rol_asignacion_display()})"

# ═══════════════════════════════════════════════════════════════
# SESIONES DE TRABAJO (Cronómetro en tiempo real & Turnos técnicos)
# Reemplaza la antigua bitácora fija diaria.
# ═══════════════════════════════════════════════════════════════
class SesionTrabajo(models.Model):
    TIPO_CIERRE_CHOICES = [
        ('fin_turno', 'Fin de turno — continúa mañana'),
        ('pausa_material', 'Bloqueado — espera material'),
        ('pausa_tecnica', 'Bloqueado — problema técnico'),
        ('completado', 'Trabajo completado en esta sesión'),
    ]

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='sesiones')
    tecnico = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='sesiones_trabajo')
    
    # Control de tiempos automático
    inicio = models.DateTimeField(default=timezone.now)
    fin = models.DateTimeField(null=True, blank=True)  # null = sesión activa ejecutándose en pañol/terreno
    horas_hombre = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    descripcion_avance = models.TextField()
    herramientas_utilizadas = models.TextField(blank=True, null=True)
    
    personal_adicional_requerido = models.BooleanField(default=False)
    requiere_nivel_mayor = models.BooleanField(default=False)
    observaciones = models.TextField(blank=True, null=True) # Notas para el gestor
    
    # Métricas de control de carga laboral (Propuesta compañero)
    tipo_cierre = models.CharField(max_length=50, choices=TIPO_CIERRE_CHOICES, null=True, blank=True)
    progreso = models.PositiveSmallIntegerField(null=True, blank=True)  # 0 a 100%
    fecha_estimada_fin = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sesion_trabajo'
        ordering = ['-inicio']
        verbose_name = 'Sesión de Trabajo'
        verbose_name_plural = 'Sesiones de Trabajo'

    def __str__(self):
        return f"Sesión #{self.id} - Ticket #{self.ticket.pk} ({self.tecnico.username})"

# ═══════════════════════════════════════════════════════════════
# MANTENCIÓN + MATERIALES UTILIZADOS
# ══════════════════════════════════════════════════════════════
class RegistroMantencion(models.Model):
    # Relación 1:1 limpia. Almacena solo auditoría y firmas técnicas de fin de ciclo
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name='mantencion')
    tecnico = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='cierres_firmados')
    
    # Datos exclusivos del cierre definitivo
    causa_raiz = models.TextField()
    foto_final = models.ImageField(upload_to='mantencion/fotos/', null=True, blank=True) # Destino Cloudinary Storage
    
    # Trazabilidad
    fecha_registro = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'registro_mantencion'
        verbose_name = 'Registro de Mantención'
        verbose_name_plural = 'Registros de Mantenciones'

    def __str__(self):
        return f"Acta de Cierre Técnico - Ticket #{self.ticket.pk}"

class MaterialUtilizado(models.Model):
    """Cada material consumido en una sesión diaria → para BI y compras inteligentes"""
    sesion_trabajo = models.ForeignKey(SesionTrabajo, on_delete=models.CASCADE, related_name='materiales_utilizados')
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name='consumos')
    cantidad_utilizada = models.DecimalField(max_digits=8, decimal_places=2) # Usa el nombre de tu diagrama
    observacion = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        db_table = 'material_utilizado'

    def __str__(self):
        return f"{self.cantidad_utilizada} {self.material.unidad} de {self.material.nombre}"

# ═══════════════════════════════════════════════════════════════
# NO REPARABLE
# ═══════════════════════════════════════════════════════════════
class NoReparable(models.Model):
    CRITICIDAD_CHOICES = [
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta'),
        ('critica', 'Crítica'),
    ]

    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name='no_reparable')
    tecnico = models.ForeignKey(Usuario, on_delete=models.PROTECT)
    motivo_tecnico = models.TextField()
    material_requerido = models.TextField()
    criticidad = models.CharField(max_length=10, choices=CRITICIDAD_CHOICES)
    requiere_externalizacion = models.BooleanField(default=False)
    herramientas_faltantes = models.TextField(blank=True, null=True)
    personal_especializado_requerido = models.CharField(max_length=200, blank=True, null=True)
    foto_diagnostico = models.ImageField(upload_to='no_reparable/', null=True, blank=True)
    costo_estimado_externo = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    empresa_externa_sugerida = models.CharField(max_length=200, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)


# ═══════════════════════════════════════════════════════════════
# LOG DE AUDITORÍA (Trazabilidad total)
# ═══════════════════════════════════════════════════════════════
class LogAuditoria(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='logs', null=True, blank=True)
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)
    accion = models.CharField(max_length=200)
    estado_anterior = models.CharField(max_length=30, blank=True, null=True)
    estado_nuevo = models.CharField(max_length=30, blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    es_interno = models.BooleanField(default=False)
    detalle = models.TextField(blank=True, null=True)
    modulo = models.CharField(max_length=50, default='ticket')  # ticket, cuenta, sistema
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


# ═══════════════════════════════════════════════════════════════
# NOTIFICACIONES
# ═══════════════════════════════════════════════════════════════
class Notificacion(models.Model):
    TIPO_CHOICES = [
        ('ticket_enviado', 'Ticket Enviado'),
        ('ticket_cerrado', 'Ticket Cerrado'),
        ('asignacion', 'Asignación'),
        ('validacion', 'Validación'),
        ('pausa', 'Pausa'),
        ('reactivacion', 'Reactivación'),
        ('no_reparado', 'No Reparado'),
        ('inasistencia', 'Inasistencia'),
        ('cuenta_solicitud', 'Solicitud de Cuenta'),
        ('cuenta_aprobada', 'Cuenta Aprobada'),
        ('cuenta_rechazada', 'Cuenta Rechazada'),
        ('reset_password', 'Recuperación de Contraseña'),
        ('general', 'General'),
    ]
    PRIORIDAD_CHOICES = [
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta'),
    ]

    destinatario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='notificaciones')
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, null=True, blank=True)
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    prioridad = models.CharField(max_length=10, choices=PRIORIDAD_CHOICES, default='media')
    titulo = models.CharField(max_length=200)
    mensaje = models.TextField()
    url_accion = models.CharField(max_length=300, blank=True, null=True)
    leida = models.BooleanField(default=False)
    archivada = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


# ═══════════════════════════════════════════════════════════════
# INASISTENCIAS
# ═══════════════════════════════════════════════════════════════
class Inasistencia(models.Model):
    MOTIVO_CHOICES = [
        ('enfermedad', 'Enfermedad'),
        ('permiso', 'Permiso Administrativo'),
        ('capacitacion', 'Capacitación'),
        ('vacaciones', 'Vacaciones'),
        ('otro', 'Otro'),
    ]

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='inasistencias')
    fecha_desde = models.DateField()
    fecha_hasta = models.DateField()
    motivo = models.CharField(max_length=20, choices=MOTIVO_CHOICES)
    detalle = models.TextField(blank=True, null=True)
    estado = models.ForeignKey(
        EstadoCatalogo,
        on_delete=models.PROTECT,
        related_name='inasistencias_estado',
        limit_choices_to={'entidad': 'inasistencia'},
    )
    revisado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='inasistencias_revisadas')
    created_at = models.DateTimeField(auto_now_add=True)

    def get_estado_display(self):
        return self.estado.nombre_display if self.estado_id else ''

    def esta_activa(self):
        hoy = timezone.now().date()
        return self.fecha_desde <= hoy <= self.fecha_hasta and self.estado.codigo == 'aprobada'

# ═══════════════════════════════════════════════════════════════
# HISTORIAL DE ACCIONES (Trazabilidad global e interna – HU-15)
# ══════════════════════════════════════════════════════════════
class HistorialAcciones(models.Model):
    """Tabla única de trazabilidad. es_global=True visible a todos; False solo a staff (gestor/operativos)."""
    TIPO_ACCION_CHOICES = [
        ('creacion', 'Creación'),
        ('asignacion', 'Asignación'),
        ('reasignacion', 'Reasignación'),
        ('cambio_estado', 'Cambio de Estado'),
        ('validacion', 'Validación (Guardia)'),
        ('rechazo_validacion', 'Rechazo Validación'),
        ('inicio_mantencion', 'Inicio Mantención'),
        ('completar_mantencion', 'Reparación Completada'),
        ('no_reparable', 'Marcado No Reparable'),
        ('reactivacion', 'Reactivación'),
        ('pausa', 'Pausa'),
        ('cierre', 'Cierre'),
        ('cancelacion', 'Cancelación'),
        ('revocacion', 'Revocación'),
        ('vinculacion_activo', 'Vinculación a Activo'),
        ('comentario', 'Comentario'),
        ('comentario_interno', 'Comentario Interno'),
        ('derivacion', 'Derivación'),
        ('reasignacion_por_inasistencia', 'Reasignación por Inasistencia'),
    ]

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='historial_acciones')
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, related_name='acciones_realizadas')
    tipo_accion = models.CharField(max_length=30, choices=TIPO_ACCION_CHOICES)
    estado_anterior = models.CharField(max_length=30, blank=True, null=True)
    estado_nuevo = models.CharField(max_length=30, blank=True, null=True)
    sub_estado_nuevo = models.CharField(max_length=30, blank=True, null=True)
    duracion_estado_anterior_min = models.PositiveIntegerField(null=True, blank=True)
    descripcion = models.TextField(blank=True, null=True)
    es_global = models.BooleanField(default=True)  # HU-15: True=visible a todos; False=solo staff
    usuario_reasignado_a = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets_reasignados_a_este')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Historial de Acciones'

    def __str__(self):
        return f"Ticket #{self.ticket.pk} - {self.get_tipo_accion_display()} por {self.usuario}"


# ═══════════════════════════════════════════════════════════════
# MATERIALES FALTANTES EN MANTENCIÓN
# ═══════════════════════════════════════════════════════════════
class MaterialesFaltantes(models.Model):
    """Registra materiales que faltaron durante una sesión de trabajo específica."""
    sesion_trabajo = models.ForeignKey(SesionTrabajo, on_delete=models.CASCADE, related_name='materiales_faltantes')
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name='solicitudes')
    cantidad_requerida = models.DecimalField(max_digits=8, decimal_places=2)
    cantidad_recibida = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    estado = models.ForeignKey(
        EstadoCatalogo,
        on_delete=models.PROTECT,
        related_name='materiales_faltantes_estado',
        limit_choices_to={'entidad': 'material_faltante'},
    )
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_recepcion = models.DateTimeField(null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Material faltante: {self.material.nombre} (Sesión #{self.sesion_trabajo.id})"