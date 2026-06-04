# ═══════════════════════════════════════════════════════════════
# CAMPUS SEGURO – Comando de inicialización: crear_gestor
# ─────────────────────────────────────────────────────────────
# Archivo: app/management/commands/crear_gestor.py
#
# PROPÓSITO:
#   Crea el usuario gestor inicial en una base de datos recién
#   migrada. Solo se necesita ejecutar UNA VEZ por entorno nuevo.
#
# CUÁNDO USARLO:
#   - Al clonar el repositorio por primera vez (desarrollo local)
#   - Al reiniciar la base de datos de pruebas
#   - NO se necesita en producción ni cuando ya existe el gestor
#
# PREREQUISITO:
#   python manage.py migrate  (debe ejecutarse antes que este comando)
#
# USO INTERACTIVO (pide los datos por consola):
#   python manage.py crear_gestor
#
# USO CON ARGUMENTOS (para scripts o CI):
#   python manage.py crear_gestor \
#       --email gestor@duocuc.cl \
#       --rut 12.345.678-9 \
#       --nombre Jordan \
#       --apellido Garcia
#
# RESULTADO:
#   - Crea un Usuario con rol='gestor', estado_cuenta='activa'
#   - Contraseña NO se guarda (Auth0 la gestiona)
#   - auth0_sub se vincula automáticamente en el primer login
#
# CONEXIONES:
#   - Lee: app/models.py (Usuario, EstadoCatalogo)
#   - Requiere: migración 0006 aplicada (pobla EstadoCatalogo)
# ═══════════════════════════════════════════════════════════════

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from app.models import Usuario, EstadoCatalogo


class Command(BaseCommand):
    help = 'Crea el usuario gestor inicial en una base de datos nueva (ejecutar una sola vez).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Correo institucional del gestor (debe coincidir con la cuenta en Auth0).',
        )
        parser.add_argument(
            '--rut',
            type=str,
            help='RUT del gestor. Ejemplo: 12.345.678-9',
        )
        parser.add_argument(
            '--nombre',
            type=str,
            help='Nombre(s) del gestor.',
        )
        parser.add_argument(
            '--apellido',
            type=str,
            help='Apellido(s) del gestor.',
        )

    def handle(self, *args, **options):
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('=' * 60))
        self.stdout.write(self.style.MIGRATE_HEADING('  CAMPUS SEGURO - Creacion de usuario gestor'))
        self.stdout.write(self.style.MIGRATE_HEADING('=' * 60))
        self.stdout.write('')

        # ── Verificar que las migraciones estén aplicadas ─────
        try:
            EstadoCatalogo.objects.get(entidad='cuenta', codigo='activa')
        except EstadoCatalogo.DoesNotExist:
            raise CommandError(
                'No se encontró el catálogo de estados.\n'
                'Asegúrate de haber ejecutado primero: python manage.py migrate'
            )

        # ── Obtener datos (argumentos o interactivo) ──────────
        email = options.get('email') or self._pedir('Correo institucional del gestor (Auth0)')
        rut = options.get('rut') or self._pedir('RUT del gestor (ej: 12.345.678-9)')
        nombre = options.get('nombre') or self._pedir('Nombre(s)')
        apellido = options.get('apellido') or self._pedir('Apellido(s)')

        email = email.strip().lower()
        rut = rut.strip()
        nombre = nombre.strip()
        apellido = apellido.strip()

        # ── Validaciones básicas ──────────────────────────────
        if not email or '@' not in email:
            raise CommandError('El correo ingresado no es válido.')
        if not rut:
            raise CommandError('El RUT no puede estar vacío.')
        if not nombre or not apellido:
            raise CommandError('Nombre y apellido son obligatorios.')

        # ── Verificar si ya existe ─────────────────────────────
        if Usuario.objects.filter(correo_institucional__iexact=email).exists():
            self.stdout.write(
                self.style.WARNING(f'  Ya existe un usuario con el correo: {email}')
            )
            self.stdout.write(
                self.style.WARNING('  No se creó ningún usuario nuevo.')
            )
            return

        if Usuario.objects.filter(rut=rut).exists():
            raise CommandError(f'Ya existe un usuario con el RUT: {rut}')

        # ── Crear el gestor ───────────────────────────────────
        estado_activa = EstadoCatalogo.objects.get(entidad='cuenta', codigo='activa')

        try:
            gestor = Usuario(
                username=email,
                email=email,
                correo_institucional=email,
                first_name=nombre,
                last_name=apellido,
                rut=rut,
                rol='gestor',
                estado_cuenta=estado_activa,
                is_active=True,
                is_staff=True,
                is_superuser=False,
                auth0_sub=None,
            )
            gestor.set_unusable_password()
            gestor.save()

        except IntegrityError as e:
            raise CommandError(f'Error al crear el gestor: {e}')

        # ── Resultado ─────────────────────────────────────────
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('  OK Gestor creado correctamente'))
        self.stdout.write('')
        self.stdout.write(f'    Nombre:   {gestor.get_full_name()}')
        self.stdout.write(f'    Correo:   {email}')
        self.stdout.write(f'    RUT:      {rut}')
        self.stdout.write(f'    Rol:      gestor')
        self.stdout.write(f'    Estado:   activa')
        self.stdout.write(f'    Auth0 ID: se vincula automáticamente en el primer login')
        self.stdout.write('')
        self.stdout.write(
            self.style.NOTICE(
                '  IMPORTANTE: La contraseña la gestiona Auth0.\n'
                '  Inicia sesión con el correo y la contraseña de tu cuenta Auth0.'
            )
        )
        self.stdout.write('')

    def _pedir(self, label):
        """Solicita un valor por consola con formato consistente."""
        return input(f'  {label}: ')
