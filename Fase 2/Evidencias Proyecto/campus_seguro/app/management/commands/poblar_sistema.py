# ═══════════════════════════════════════════════════════════════
# CAMPUS SEGURO – Comando de inicialización unificado: poblar_sistema
# ─────────────────────────────────────────────────────────────
# Archivo: app/management/commands/poblar_sistema.py
#
# PROPÓSITO:
#   Puebla de forma centralizada todas las tablas maestras relacionales:
#   Catálogo de Estados, Categorías de Tickets y Materiales, Especialidades
#   Técnicas, Insumos del pañol e Infraestructura Geográfica (Sede, Edificios, Pisos y Salas).
#
# USO:
#   python manage.py poblar_sistema
# ═══════════════════════════════════════════════════════════════

from django.core.management.base import BaseCommand
from app.models import (
    EstadoCatalogo, CategoriaTicket, CategoriaMaterial, Especialidad, 
    Material, EspecialidadMaterial, Sede, Edificio, Piso, TipoUbicacion, Ubicacion
)


# ─────────────────────────────────────────────────────────────────
# Matriz Maestra del Catálogo Operativo (30 estados iniciales)
# ─────────────────────────────────────────────────────────────────
ESTADOS_INICIALES = [
    # ticket
    dict(entidad='ticket', codigo='enviado',       nombre_display='Enviado',       es_inicial=True,  es_final=False, orden=1,  color_hex='#6c757d'),
    dict(entidad='ticket', codigo='en_proceso',    nombre_display='En Proceso',    es_inicial=False, es_final=False, orden=2,  color_hex='#007bff'),
    dict(entidad='ticket', codigo='en_validacion', nombre_display='En Validación', es_inicial=False, es_final=False, orden=3,  color_hex='#fd7e14'),
    dict(entidad='ticket', codigo='validado',       nombre_display='Validado',       es_inicial=False, es_final=False, orden=4,  color_hex='#20c997'),
    dict(entidad='ticket', codigo='en_mantencion', nombre_display='En Mantención', es_inicial=False, es_final=False, orden=5,  color_hex='#17a2b8'),
    dict(entidad='ticket', codigo='reparado',       nombre_display='Reparado',       es_inicial=False, es_final=False, orden=6,  color_hex='#28a745'),
    dict(entidad='ticket', codigo='pausado',       nombre_display='Pausado',       es_inicial=False, es_final=False, orden=7,  color_hex='#ffc107'),
    dict(entidad='ticket', codigo='no_reparado',   nombre_display='No Reparado',   es_inicial=False, es_final=True,  orden=8,  color_hex='#dc3545'),
    dict(entidad='ticket', codigo='cerrado',       nombre_display='Cerrado',       es_inicial=False, es_final=True,  orden=9,  color_hex='#343a40'),
    dict(entidad='ticket', codigo='cancelado',     nombre_display='Cancelado',     es_inicial=False, es_final=True,  orden=10, color_hex='#6f42c1'),
    dict(entidad='ticket', codigo='revocado',      nombre_display='Revocado',      es_inicial=False, es_final=True,  orden=11, color_hex='#e83e8c'),
    dict(entidad='ticket', codigo='eliminado',     nombre_display='Eliminado',     es_inicial=False, es_final=True,  orden=12, color_hex='#6c757d'),
    # ticket_sub
    dict(entidad='ticket_sub', codigo='pendiente_revision',  nombre_display='Pendiente Revisión',    es_inicial=True,  es_final=False, orden=1),
    dict(entidad='ticket_sub', codigo='revisado',             nombre_display='Revisado',              es_inicial=False, es_final=False, orden=2),
    dict(entidad='ticket_sub', codigo='asignado_mantencion',  nombre_display='Asignado a Mantención', es_inicial=False, es_final=False, orden=3),
    dict(entidad='ticket_sub', codigo='escalado',             nombre_display='Escalado',              es_inicial=False, es_final=True,  orden=4),
    dict(entidad='ticket_sub', codigo='asignado_guardia',    nombre_display='Asignado a Guardia',    es_inicial=False, es_final=False, orden=5),
    dict(entidad='ticket_sub', codigo='asignado_tecnico',    nombre_display='Asignado a Técnico',    es_inicial=False, es_final=False, orden=6),
    # cuenta
    dict(entidad='cuenta', codigo='pendiente',  nombre_display='Pendiente',  es_inicial=True,  es_final=False, orden=1, color_hex='#ffc107'),
    dict(entidad='cuenta', codigo='activa',     nombre_display='Activa',     es_inicial=False, es_final=False, orden=2, color_hex='#28a745'),
    dict(entidad='cuenta', codigo='suspendida', nombre_display='Suspendida', es_inicial=False, es_final=False, orden=3, color_hex='#fd7e14'),
    dict(entidad='cuenta', codigo='rechazada',  nombre_display='Rechazada',  es_inicial=False, es_final=True,  orden=4, color_hex='#dc3545'),
    # asignacion
    dict(entidad='asignacion', codigo='activa',     nombre_display='Activa',     es_inicial=True,  es_final=False, orden=1),
    dict(entidad='asignacion', codigo='completada', nombre_display='Completada', es_inicial=False, es_final=True,  orden=2),
    dict(entidad='asignacion', codigo='cancelada',  nombre_display='Cancelada',  es_inicial=False, es_final=True,  orden=3),
    dict(entidad='asignacion', codigo='pendiente',  nombre_display='Pendiente',  es_inicial=False, es_final=False, orden=4),
    # inasistencia
    dict(entidad='inasistencia', codigo='pendiente', nombre_display='Pendiente', es_inicial=True,  es_final=False, orden=1),
    dict(entidad='inasistencia', codigo='aprobada',  nombre_display='Aprobada',  es_inicial=False, es_final=True,  orden=2),
    dict(entidad='inasistencia', codigo='rechazada', nombre_display='Rechazada', es_inicial=False, es_final=True,  orden=3),
    # material_faltante
    dict(entidad='material_faltante', codigo='pendiente',  nombre_display='Pendiente',  es_inicial=True,  es_final=False, orden=1),
    dict(entidad='material_faltante', codigo='solicitado', nombre_display='Solicitado', es_inicial=False, es_final=False, orden=2),
    dict(entidad='material_faltante', codigo='recibido',   nombre_display='Recibido',   es_inicial=False, es_final=True,  orden=3),
    dict(entidad='material_faltante', codigo='cancelado',  nombre_display='Cancelado',  es_inicial=False, es_final=True,  orden=4),
    # urgencia_ticket — administrable desde admin sin migración
    dict(entidad='urgencia_ticket', codigo='baja',    nombre_display='Baja',    es_inicial=False, es_final=False, orden=1, color_hex='#28a745'),
    dict(entidad='urgencia_ticket', codigo='media',   nombre_display='Media',   es_inicial=False, es_final=False, orden=2, color_hex='#ffc107'),
    dict(entidad='urgencia_ticket', codigo='alta',    nombre_display='Alta',    es_inicial=False, es_final=False, orden=3, color_hex='#fd7e14'),
    dict(entidad='urgencia_ticket', codigo='critica', nombre_display='Crítica', es_inicial=False, es_final=False, orden=4, color_hex='#dc3545'),
    # pausa_ticket — razones de pausa administrables desde admin
    dict(entidad='pausa_ticket', codigo='material',        nombre_display='Aprobación de materiales',    es_inicial=False, es_final=False, orden=1),
    dict(entidad='pausa_ticket', codigo='personal',        nombre_display='Personal técnico',            es_inicial=False, es_final=False, orden=2),
    dict(entidad='pausa_ticket', codigo='nivel_mayor',     nombre_display='Peritaje (análisis técnico)', es_inicial=False, es_final=False, orden=3),
    dict(entidad='pausa_ticket', codigo='externalizacion', nombre_display='Requiere externalización',    es_inicial=False, es_final=False, orden=4),
    # criticidad — nivel de criticidad de ítems no reparables
    dict(entidad='criticidad', codigo='baja',    nombre_display='Baja',    es_inicial=False, es_final=False, orden=1, color_hex='#28a745'),
    dict(entidad='criticidad', codigo='media',   nombre_display='Media',   es_inicial=False, es_final=False, orden=2, color_hex='#ffc107'),
    dict(entidad='criticidad', codigo='alta',    nombre_display='Alta',    es_inicial=False, es_final=False, orden=3, color_hex='#fd7e14'),
    dict(entidad='criticidad', codigo='critica', nombre_display='Crítica', es_inicial=False, es_final=False, orden=4, color_hex='#dc3545'),
    # motivo_inasistencia — motivos de ausencia del personal
    dict(entidad='motivo_inasistencia', codigo='enfermedad',   nombre_display='Enfermedad',             es_inicial=False, es_final=False, orden=1),
    dict(entidad='motivo_inasistencia', codigo='permiso',      nombre_display='Permiso Administrativo', es_inicial=False, es_final=False, orden=2),
    dict(entidad='motivo_inasistencia', codigo='capacitacion', nombre_display='Capacitación',           es_inicial=False, es_final=False, orden=3),
    dict(entidad='motivo_inasistencia', codigo='vacaciones',   nombre_display='Vacaciones',             es_inicial=False, es_final=False, orden=4),
    dict(entidad='motivo_inasistencia', codigo='otro',         nombre_display='Otro',                   es_inicial=False, es_final=False, orden=5),
]


class Command(BaseCommand):
    help = 'Puebla las tablas maestras de estados, categorías, especialidades, materiales e infraestructura del campus.'

    def handle(self, *args, **options):
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('=' * 60))
        self.stdout.write(self.style.MIGRATE_HEADING('   CAMPUS SEGURO - Inicialización de Datos Relacionales'))
        self.stdout.write(self.style.MIGRATE_HEADING('=' * 60))
        self.stdout.write('')

        # Contadores de control global
        creados = 0
        omitidos = 0

        # ═══════════════════════════════════════════════════════════════
        # 1. SEMBRADO: MATRIZ MAESTRA DE ESTADOS DEL SISTEMA
        # ═══════════════════════════════════════════════════════════════
        self.stdout.write(self.style.MIGRATE_HEADING('--> Procesando Matriz del Catálogo de Estados...'))
        for estado_data in ESTADOS_INICIALES:
            _, creada = EstadoCatalogo.objects.get_or_create(
                entidad=estado_data['entidad'],
                codigo=estado_data['codigo'],
                defaults=estado_data,
            )
            if creada:
                creados += 1
            else:
                omitidos += 1
        self.stdout.write(self.style.SUCCESS(f'   [✓] Sincronizados {len(ESTADOS_INICIALES)} estados base del motor de estados.'))

        # ═══════════════════════════════════════════════════════════════
        # 2. SEMBRADO: CATEGORÍAS DE TICKETS (Nombres originales exactos)
        # ═══════════════════════════════════════════════════════════════
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('--> Procesando Categorías de Tickets...'))
        cat_tickets_base = [
            {'codigo': 'electrico', 'nombre': 'Eléctrico'},
            {'codigo': 'plomeria', 'nombre': 'Plomería'},
            {'codigo': 'infraestructura', 'nombre': 'Infraestructura'},
            {'codigo': 'climatizacion', 'nombre': 'Climatización'},
            {'codigo': 'tecnologia', 'nombre': 'Tecnología'},
            {'codigo': 'accesibilidad', 'nombre': 'Accesibilidad'},
            {'codigo': 'mobiliario', 'nombre': 'Mobiliario'},
            {'codigo': 'otro', 'nombre': 'Otro'},
        ]

        for cat_data in cat_tickets_base:
            cat_t, creada = CategoriaTicket.objects.get_or_create(
                codigo=cat_data['codigo'],
                defaults={
                    'nombre_display': cat_data['nombre'],
                    'activo': True
                }
            )
            if creada:
                self.stdout.write(self.style.SUCCESS(f'   [✓] Categoría Ticket: {cat_t.nombre_display}'))
                creados += 1
            else:
                omitidos += 1

        # ═══════════════════════════════════════════════════════════════
        # 3. SEMBRADO: CATEGORÍAS DE MATERIALES (Logística Bodega)
        # ═══════════════════════════════════════════════════════════════
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('--> Procesando Categorías de Materiales...'))
        cat_materiales_base = [
            {'codigo': 'electrico', 'nombre': 'Materiales Eléctricos'},
            {'codigo': 'plomeria', 'nombre': 'Gasfitería e Hidráulica'},
            {'codigo': 'construccion', 'nombre': 'Obra Gruesa y Terminaciones'},
            {'codigo': 'ferreteria', 'nombre': 'Ferretería General e Insumos'},
            {'codigo': 'limpieza', 'nombre': 'Aseo y Sanitización'},
            {'codigo': 'tecnologia', 'nombre': 'Componentes Tecnológicos'},
        ]

        cat_mat_objetos = {}
        for cat_mat_data in cat_materiales_base:
            cat_m, creada = CategoriaMaterial.objects.get_or_create(
                codigo=cat_mat_data['codigo'],
                defaults={'nombre_display': cat_mat_data['nombre'], 'activo': True}
            )
            cat_mat_objetos[cat_mat_data['codigo']] = cat_m
            if creada:
                self.stdout.write(self.style.SUCCESS(f'   [✓] Categoría Material: {cat_m.nombre_display}'))
                creados += 1
            else:
                omitidos += 1

        # ═══════════════════════════════════════════════════════════════
        # 4. SEMBRADO: ESPECIALIDADES TÉCNICAS (Tus strings originales)
        # ═══════════════════════════════════════════════════════════════
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('--> Procesando Especialidades Técnicas...'))
        especialidades_base = [
            {
                'nombre': 'Electricista Certificado SEC',
                'descripcion': 'Personal calificado para intervenir tableros eléctricos, luminarias, enchufes y redes de baja tensión.'
            },
            {
                'nombre': 'Gasfíter Plomero',
                'descripcion': 'Especialista en redes de agua potable, alcantarillado, filtraciones, griferías y sanitarios de la sede.'
            },
            {
                'nombre': 'Cerrajero de Infraestructura',
                'descripcion': 'Encargado del mantenimiento de chapas, cerraduras biométricas, puertas, portones y accesos físicos.'
            },
            {
                'nombre': 'Técnico en Climatización y HVAC',
                'descripcion': 'Mantenimiento preventivo y correctivo de aires acondicionados, sistemas de ventilación y calefacción.'
            },
            {
                'nombre': 'Carpintero y Reparador de Mobiliario',
                'descripcion': 'Reparación estructural de bancos, mesas, sillas, pizarras, muros de tabiquería y cielos falsos.'
            }
        ]

        esp_objetos = {}
        for esp_data in list(especialidades_base):
            especialidad, creada = Especialidad.objects.get_or_create(
                nombre=esp_data['nombre'],
                defaults={'descripcion': esp_data['descripcion']}
            )
            esp_objetos[esp_data['nombre']] = especialidad
            if creada:
                self.stdout.write(self.style.SUCCESS(f'   [✓] Especialidad: {especialidad.nombre}'))
                creados += 1
            else:
                omitidos += 1

        # ═══════════════════════════════════════════════════════════════
        # 5. SEMBRADO: CATALOGO DE MATERIALES E INTERMEDIAS M:N
        # ═══════════════════════════════════════════════════════════════
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('--> Procesando Catálogo de Materiales e Intermedias M:N...'))
        materiales_base = [
            # Rubro Eléctrico
            {
                'codigo': 'MAT-ELEC-001', 'nombre': 'Tubo Fluorescente LED 18W',
                'cat_cod': 'electrico', 'unidad': 'unidad',
                'permisos': ['Electricista Certificado SEC']
            },
            {
                'codigo': 'MAT-ELEC-002', 'nombre': 'Cinta Aisladora Negra 20m',
                'cat_cod': 'electrico', 'unidad': 'rollo',
                'permisos': ['Electricista Certificado SEC', 'Técnico en Climatización y HVAC']
            },
            # Rubro Gasfitería
            {
                'codigo': 'MAT-PLOM-001', 'nombre': 'Tubo PVC Sanitario 40mm x 3m',
                'cat_cod': 'plomeria', 'unidad': 'unidad',
                'permisos': ['Gasfíter Plomero']
            },
            {
                'codigo': 'MAT-PLOM-002', 'nombre': 'Cinta de Teflón Profesional 3/4',
                'cat_cod': 'plomeria', 'unidad': 'rollo',
                'permisos': ['Gasfíter Plomero', 'Técnico en Climatización y HVAC']
            },
            # Rubro Ferretería / Cerrajeros / Carpinteros
            {
                'codigo': 'MAT-FERR-001', 'nombre': 'Cerradura de Pomo para Aula (Chapa)',
                'cat_cod': 'ferreteria', 'unidad': 'unidad',
                'permisos': ['Cerrajero de Infraestructura']
            },
            {
                'codigo': 'MAT-FERR-002', 'nombre': 'Tornillo Madera Zincado 1 1/2 (Caja x100)',
                'cat_cod': 'ferreteria', 'unidad': 'caja',
                'permisos': ['Carpintero y Reparador de Mobiliario', 'Cerrajero de Infraestructura']
            }
        ]

        uniones_creadas = 0
        for mat_data in materiales_base:
            instancia_cat = cat_mat_objetos[mat_data['cat_cod']]
            
            material, creado_mat = Material.objects.get_or_create(
                codigo=mat_data['codigo'],
                defaults={
                    'nombre': mat_data['nombre'],
                    'categoria': instancia_cat,
                    'unidad': mat_data['unidad'],
                    'activo': True
                }
            )
            if creado_mat:
                self.stdout.write(self.style.SUCCESS(f'   [✓] Material: {material.nombre}'))
                creados += 1
            else:
                omitidos += 1

            for nombre_esp in mat_data['permisos']:
                instancia_esp = esp_objetos[nombre_esp]
                _, creada_union = EspecialidadMaterial.objects.get_or_create(
                    material=material,
                    especialidad=instancia_esp
                )
                if creada_union:
                    uniones_creadas += 1

        # ═══════════════════════════════════════════════════════════════
<<<<<<< HEAD
        # 6. SEMBRADO: INFRAESTRUCTURA GEOGRÁFICA Y DE UBICACIONES (NUEVO)
        # ═══════════════════════════════════════════════════════════════
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('--> Procesando Infraestructura de Sede, Edificios, Pisos y Salas...'))
        
        # Sede
        sede_institucional, _ = Sede.objects.get_or_create(nombre='Sede San Andrés de Concepción')
        
        # Catálogo Maestro de Tipos de Ubicación
        tipos_dict = {
            'aula': 'Aula', 'laboratorio': 'Laboratorio', 'taller': 'Taller',
            'baño': 'Baño', 'pasillo': 'Pasillo', 'escalera': 'Escalera',
            'ascensor': 'Ascensor', 'casino': 'Casino', 'oficina': 'Oficina',
            'area_comun': 'Área Común', 'otro': 'Otro',
        }
        tipos_maestros = {}
        for cod, nom in tipos_dict.items():
            tipo_obj, _ = TipoUbicacion.objects.get_or_create(codigo=cod, defaults={'nombre_display': nom})
            tipos_maestros[cod] = tipo_obj
        
        edificios_config = {
            'E': {'pisos': range(1, 6), 'salas_por_piso': 16, 'banos_por_piso': {2: 1}},
            'H': {'pisos': range(1, 9), 'salas_por_piso': 16, 'banos_por_piso': {p: 1 for p in range(1, 9)}}
        }
        
        ubicaciones_count = 0
        for letra, config in edificios_config.items():
            edificio_obj, _ = Edificio.objects.get_or_create(sede=sede_institucional, nombre=f"Edificio {letra}")
            
            for num_piso in config['pisos']:
                piso_obj, _ = Piso.objects.get_or_create(edificio=edificio_obj, numero=str(num_piso))
                
                # Aulas tradicionales
                for num_sala in range(1, config['salas_por_piso'] + 1):
                    _, creada = Ubicacion.objects.get_or_create(
                        piso=piso_obj, sala=f"{letra}{num_sala:03d}",
                        defaults={'tipo': tipos_maestros['aula'], 'capacidad': 30}
                    )
                    if creada: ubicaciones_count += 1
                
                # Baños según configuración
                if num_piso in config['banos_por_piso']:
                    for num_bano in range(1, config['banos_por_piso'][num_piso] + 1):
                        _, creada = Ubicacion.objects.get_or_create(
                            piso=piso_obj, sala=f"Baño P{num_piso}",
                            defaults={'tipo': tipos_maestros['baño'], 'capacidad': None}
                        )
                        if creada: ubicaciones_count += 1
                
                # Zonas comunes del piso (Pasillos, Escaleras y Ascensores)
                zonas_especiales = [
                    ('pasillo', f"Pasillo General P{num_piso}"),
                    ('escalera', f"Escalera General P{num_piso}"),
                    ('ascensor', f"Ascensor Principal P{num_piso}")
                ]
                for codigo_tipo, nombre_zona in zonas_especiales:
                    _, creada = Ubicacion.objects.get_or_create(
                        piso=piso_obj, sala=nombre_zona,
                        defaults={'tipo': tipos_maestros[codigo_tipo], 'capacidad': None}
                    )
                    if creada: ubicaciones_count += 1
                
                # Casino Central (Únicamente Edificio E - Piso 1)
                if letra == 'E' and num_piso == 1:
                    _, creada = Ubicacion.objects.get_or_create(
                        piso=piso_obj, sala="Casino Central",
                        defaults={'tipo': tipos_maestros['casino'], 'capacidad': 150}
                    )
                    if creada: ubicaciones_count += 1

        self.stdout.write(self.style.SUCCESS(f'   [✓] Sembradas exitosamente {ubicaciones_count} salas/zonas en la Sede San Andrés.'))
        creados += ubicaciones_count
=======
        # 6. SEMBRADO: UBICACIONES DEL CAMPUS (Edificio E y H)
        # ═══════════════════════════════════════════════════════════════
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('--> Procesando Ubicaciones del Campus...'))
        ubicaciones_nuevas = Ubicacion.crear_default_campus()
        self.stdout.write(self.style.SUCCESS(f'   [✓] Ubicaciones creadas: {ubicaciones_nuevas}'))
>>>>>>> dev

        # ── Resumen de ejecución ──────────────────────────────────────
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('-' * 60))
        self.stdout.write(self.style.SUCCESS(f'   PROCESO FINALIZADO CON ÉXITO.'))
        self.stdout.write(f'    Registros nuevos añadidos al sistema: {creados}')
        self.stdout.write(f'    Relaciones M:N Material <-> Especialidad inyectadas: {uniones_creadas}')
        self.stdout.write(f'    Registros de resguardo omitidos u obsoletos: {omitidos}')
        self.stdout.write(self.style.MIGRATE_HEADING('-' * 60))
        self.stdout.write('')