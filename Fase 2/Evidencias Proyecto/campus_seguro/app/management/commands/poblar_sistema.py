# ═══════════════════════════════════════════════════════════════
# CAMPUS SEGURO – Comando de inicialización unificado: poblar_sistema
# ─────────────────────────────────────────────────────────────
# Archivo: app/management/commands/poblar_sistema.py
#
# PROPÓSITO:
#   Puebla de forma centralizada todas las tablas maestras relacionales:
#   Categorías de Tickets, Categorías de Materiales, Especialidades
#   Técnicas institucionales e Insumos base del pañol.
#
# USO:
#   python manage.py poblar_sistema
# ═══════════════════════════════════════════════════════════════

from django.core.management.base import BaseCommand
from app.models import CategoriaTicket, CategoriaMaterial, Especialidad, Material, EspecialidadMaterial


class Command(BaseCommand):
    help = 'Puebla las tablas maestras de categorías, especialidades y materiales con el catálogo institucional base.'

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
        # 1. SEMBRADO: CATEGORÍAS DE TICKETS (Tus nombres originales exactos)
        # ═══════════════════════════════════════════════════════════════
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
        # 2. SEMBRADO: CATEGORÍAS DE MATERIALES (Logística Bodega)
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
        # 3. SEMBRADO: ESPECIALIDADES TÉCNICAS (Tus strings originales)
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
        # 4. SEMBRADO: CATALOGO DE MATERIALES E INTERMEDIAS M:N (Opción B)
        # ═══════════════════════════════════════════════════════════════
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('--> Procesando Catálogo de Materiales e Intermedias M:N...'))
        materiales_base = [
            # Rubro Eléctrico
            {
                'codigo': 'MAT-ELEC-001', 'nombre': 'Tubo Fluorescente LED 18W',
                'cat_cod': 'electrico', 'unidad': 'unidad', 'stock': 40,
                'permisos': ['Electricista Certificado SEC']
            },
            {
                'codigo': 'MAT-ELEC-002', 'nombre': 'Cinta Aisladora Negra 20m',
                'cat_cod': 'electrico', 'unidad': 'rollo', 'stock': 60,
                'permisos': ['Electricista Certificado SEC', 'Técnico en Climatización y HVAC'] # Cruzado M:N
            },
            # Rubro Gasfitería
            {
                'codigo': 'MAT-PLOM-001', 'nombre': 'Tubo PVC Sanitario 40mm x 3m',
                'cat_cod': 'plomeria', 'unidad': 'unidad', 'stock': 12,
                'permisos': ['Gasfíter Plomero']
            },
            {
                'codigo': 'MAT-PLOM-002', 'nombre': 'Cinta de Teflón Profesional 3/4',
                'cat_cod': 'plomeria', 'unidad': 'rollo', 'stock': 45,
                'permisos': ['Gasfíter Plomero', 'Técnico en Climatización y HVAC'] # Cruzado M:N
            },
            # Rubro Ferretería / Cerrajeros / Carpinteros
            {
                'codigo': 'MAT-FERR-001', 'nombre': 'Cerradura de Pomo para Aula (Chapa)',
                'cat_cod': 'ferreteria', 'unidad': 'unidad', 'stock': 18,
                'permisos': ['Cerrajero de Infraestructura']
            },
            {
                'codigo': 'MAT-FERR-002', 'nombre': 'Tornillo Madera Zincado 1 1/2 (Caja x100)',
                'cat_cod': 'ferreteria', 'unidad': 'caja', 'stock': 25,
                'permisos': ['Carpintero y Reparador de Mobiliario', 'Cerrajero de Infraestructura'] # Cruzado M:N
            }
        ]

        uniones_creadas = 0
        for mat_data in materiales_base:
            instancia_cat = cat_mat_objetos[mat_data['cat_cod']]
            
            material, creado_mat = Material.objects.get_or_create(
                codigo=mat_data['codigo'],
                defaults={
                    'nombre': mat_data['nombre'],
                    'categoria': instancia_cat, # FK asignada
                    'unidad': mat_data['unidad'],
                    'stock_actual': mat_data['stock'],
                    'stock_minimo': 5,
                    'activo': True
                }
            )
            if creado_mat:
                self.stdout.write(self.style.SUCCESS(f'   [✓] Material: {material.nombre}'))
                creados += 1
            else:
                omitidos += 1

            # Mapeo de la tabla de quiebre (EspecialidadMaterial)
            for nombre_esp in mat_data['permisos']:
                instancia_esp = esp_objetos[nombre_esp]
                _, creada_union = EspecialidadMaterial.objects.get_or_create(
                    material=material,
                    especialidad=instancia_esp
                )
                if creada_union:
                    uniones_creadas += 1

        # ── Resumen de ejecución ──────────────────────────────────────
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('-' * 60))
        self.stdout.write(self.style.SUCCESS(f'   PROCESO FINALIZADO CON ÉXITO.'))
        self.stdout.write(f'    Registros nuevos añadidos al sistema: {creados}')
        self.stdout.write(f'    Relaciones M:N Material <-> Especialidad inyectadas: {uniones_creadas}')
        self.stdout.write(f'    Registros omitidos (ya existían en la BD): {omitidos}')
        self.stdout.write(self.style.MIGRATE_HEADING('-' * 60))
        self.stdout.write('')