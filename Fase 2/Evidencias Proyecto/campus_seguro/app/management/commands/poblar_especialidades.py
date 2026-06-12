# ═══════════════════════════════════════════════════════════════
# CAMPUS SEGURO – Comando de inicialización: poblar_especialidades
# ─────────────────────────────────────────────────────────────
# Archivo: app/management/commands/poblar_especialidades.py
#
# PROPÓSITO:
#   Puebla la tabla maestra de Especialidades Técnicas con el catálogo
#   institucional base. Evita la inserción manual por base de datos.
#
# CUÁNDO USARLO:
#   - Al inicializar el entorno de desarrollo local por primera vez.
#   - Al reiniciar o limpiar la base de datos de pruebas.
#   - Se puede ejecutar múltiples veces sin duplicar registros.
#
# PREREQUISITO:
#   python manage.py migrate  (debe existir la tabla Especialidad)
#
# USO:
#   python manage.py poblar_especialidades
#
# CONEXIONES:
#   - Lee/Escribe: app/models.py (Especialidad)
# ═══════════════════════════════════════════════════════════════

from django.core.management.base import BaseCommand
from app.models import Especialidad


class Command(BaseCommand):
    help = 'Puebla la tabla de especialidades técnicas con el catálogo base institucional.'

    def handle(self, *args, **options):
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('=' * 60))
        self.stdout.write(self.style.MIGRATE_HEADING('  CAMPUS SEGURO - Catálogo de Especialidades'))
        self.stdout.write(self.style.MIGRATE_HEADING('=' * 60))
        self.stdout.write('')

        # Definimos la lista base de especialidades profesionales que requiere Campus Seguro
        # de acuerdo a los rubros operativos de los mantenedores.
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

        nuevas_creadas = 0
        ya_existentes = 0

        for esp_data in especialidades_base:
            # Usamos get_or_create para que el comando sea idiopático (seguro de correr muchas veces)
            especialidad, creada = Especialidad.objects.get_or_create(
                nombre=esp_data['nombre'],
                defaults={'descripcion': esp_data['descripcion']}
            )

            if creada:
                self.stdout.write(self.style.SUCCESS(f'  [✓] Creada: {especialidad.nombre}'))
                nuevas_creadas += 1
            else:
                self.stdout.write(f'  [-] Ya existía: {especialidad.nombre}')
                ya_existentes += 1

        # ── Resumen de ejecución ──────────────────────────────────────
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('-' * 60))
        self.stdout.write(self.style.SUCCESS(f'  PROCESO FINALIZADO CON ÉXITO.'))
        self.stdout.write(f'    Especialidades nuevas añadidas: {nuevas_creadas}')
        self.stdout.write(f'    Especialidades omitidas (ya existían): {ya_existentes}')
        self.stdout.write(self.style.MIGRATE_HEADING('-' * 60))
        self.stdout.write('')