# ═══════════════════════════════════════════════════════════════
# CAMPUS SEGURO – Comando: sincronizar_auth0
# ─────────────────────────────────────────────────────────────
# Archivo: app/management/commands/sincronizar_auth0.py
#
# PROPÓSITO:
#   Consulta Auth0 Management API y crea en la BD local los usuarios
#   que existen en Auth0 pero no en el SQLite local.
#
#   Problema que resuelve:
#     Cuando compañeros registran cuentas en sus propios entornos Django,
#     Auth0 recibe el usuario (fuente compartida) pero la BD local de cada
#     entorno queda aislada. Este comando sincroniza Auth0 → BD local,
#     dejando visibles todas las solicitudes para el gestor.
#
# CUÁNDO USARLO:
#   - Después de clonar el repositorio (para traer usuarios previos)
#   - Cuando aparezcan "Auth0 autenticó a X pero no existe en BD local"
#   - Antes de iniciar sesiones de prueba en equipo
#
# USO:
#   python manage.py sincronizar_auth0               (importa todo)
#   python manage.py sincronizar_auth0 --dry-run     (solo muestra, no crea)
#
# COMPORTAMIENTO:
#   - NUNCA sobreescribe usuarios existentes en la BD local
#   - Asigna estado según app_metadata de Auth0 (pendiente/activa/etc.)
#   - El RUT se genera como placeholder temporal (SYNC-XXXXXXX)
#     → El gestor puede corregirlo al aprobar la cuenta
#   - auth0_sub se vincula directamente desde Auth0
#
# PREREQUISITOS:
#   - AUTH0_MGMT_CLIENT_ID y AUTH0_MGMT_CLIENT_SECRET configurados en .env
#   - python manage.py migrate ejecutado previamente
# ═══════════════════════════════════════════════════════════════

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from app.models import Usuario, EstadoCatalogo
from app.auth0_service import obtener_token_mgmt, Auth0Error


# Roles válidos reconocidos por Campus Seguro
_ROLES_VALIDOS = {'usuario', 'gestor', 'guardia', 'mantencion', 'enc_seguridad'}

# Mapeo de campus_estado (Auth0 app_metadata) → codigo de EstadoCatalogo
_ESTADO_MAP = {
    'pendiente':  'pendiente',
    'activa':     'activa',
    'suspendida': 'suspendida',
    'rechazada':  'rechazada',
}


def _url_auth0(path):
    return f"https://{settings.AUTH0_DOMAIN}{path}"


class Command(BaseCommand):
    help = (
        'Sincroniza usuarios de Auth0 hacia la BD local. '
        'Solo crea registros nuevos, nunca modifica los existentes.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué se importaría sin crear ningún registro.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('=' * 60))
        self.stdout.write(self.style.MIGRATE_HEADING('  CAMPUS SEGURO - Sincronizacion Auth0 -> BD local'))
        if dry_run:
            self.stdout.write(self.style.WARNING('  MODO DRY-RUN: no se creara ningun registro'))
        self.stdout.write(self.style.MIGRATE_HEADING('=' * 60))
        self.stdout.write('')

        # ── 1. Obtener usuarios de Auth0 ─────────────────────
        self.stdout.write('  Conectando con Auth0 Management API...')
        try:
            auth0_users = self._obtener_usuarios_auth0()
        except CommandError as e:
            raise
        except Exception as e:
            raise CommandError(f'Error al consultar Auth0: {e}')

        self.stdout.write(f'  >> {len(auth0_users)} usuario(s) encontrado(s) en Auth0')
        self.stdout.write('')

        # ── 2. Procesar cada usuario ──────────────────────────
        creados   = []
        omitidos  = []
        errores   = []

        for auth0_user in auth0_users:
            email   = (auth0_user.get('email') or '').strip().lower()
            user_id = auth0_user.get('user_id', '')

            if not email or not user_id:
                continue

            # Saltar si ya existe en BD local (por email o por auth0_sub)
            ya_existe = (
                Usuario.objects.filter(correo_institucional__iexact=email).exists()
                or Usuario.objects.filter(auth0_sub=user_id).exists()
            )
            if ya_existe:
                omitidos.append(email)
                continue

            # Extraer datos del usuario Auth0
            app_metadata = auth0_user.get('app_metadata') or {}
            campus_rol   = app_metadata.get('campus_rol', 'usuario')
            campus_estado = app_metadata.get('campus_estado', 'pendiente')

            if campus_rol not in _ROLES_VALIDOS:
                campus_rol = 'usuario'

            codigo_estado = _ESTADO_MAP.get(campus_estado, 'pendiente')

            try:
                estado_obj = EstadoCatalogo.objects.get(entidad='cuenta', codigo=codigo_estado)
            except EstadoCatalogo.DoesNotExist:
                estado_obj = EstadoCatalogo.objects.get(entidad='cuenta', codigo='pendiente')
                codigo_estado = 'pendiente'

            # Nombres (given_name/family_name o split del campo name)
            first_name = (auth0_user.get('given_name') or '').strip()
            last_name  = (auth0_user.get('family_name') or '').strip()
            if not first_name and not last_name:
                nombre_completo = (auth0_user.get('name') or email).strip().split()
                first_name = nombre_completo[0] if nombre_completo else ''
                last_name  = ' '.join(nombre_completo[1:]) if len(nombre_completo) > 1 else ''

            # RUT temporal único basado en el auth0_sub
            rut_temp = ('SYNC-' + user_id[-7:])[:12]

            if dry_run:
                self.stdout.write(
                    f'  [DRY-RUN] {email:<35} '
                    f'rol={campus_rol:<12} estado={codigo_estado}'
                )
                creados.append(email)
                continue

            # Crear el usuario local
            try:
                nuevo = Usuario(
                    username=email,
                    email=email,
                    correo_institucional=email,
                    first_name=first_name,
                    last_name=last_name,
                    rut=rut_temp,
                    rol=campus_rol,
                    estado_cuenta=estado_obj,
                    auth0_sub=user_id,
                    is_active=(codigo_estado == 'activa'),
                    activo=True,
                )
                nuevo.set_unusable_password()
                nuevo.save()
                creados.append(email)
                self.stdout.write(
                    self.style.SUCCESS(f'  OK {email:<35} rol={campus_rol:<12} estado={codigo_estado}')
                )

            except IntegrityError as e:
                errores.append(email)
                self.stdout.write(
                    self.style.ERROR(f'  ERR {email} - IntegrityError: {e}')
                )
            except Exception as e:
                errores.append(email)
                self.stdout.write(
                    self.style.ERROR(f'  ERR {email} - Error: {e}')
                )

        # ── 3. Resumen ────────────────────────────────────────
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('-' * 60))
        self.stdout.write(
            self.style.SUCCESS(f'  Creados : {len(creados)}') if creados
            else f'  Creados : {len(creados)}'
        )
        self.stdout.write(f'  Omitidos (ya existían): {len(omitidos)}')
        if errores:
            self.stdout.write(self.style.ERROR(f'  Errores:  {len(errores)}'))
        self.stdout.write(self.style.MIGRATE_HEADING('-' * 60))

        if creados and not dry_run:
            self.stdout.write('')
            self.stdout.write(
                self.style.NOTICE(
                    '  NOTA: Los usuarios importados con estado "pendiente"\n'
                    '  aparecen en el panel del gestor para su aprobacion.\n'
                    '  El campo RUT tiene valor temporal (SYNC-XXXXXXX);\n'
                    '  puede corregirse desde el panel de administracion.'
                )
            )
        self.stdout.write('')

    # ── Auth0 Management API: obtener todos los usuarios ─────
    def _obtener_usuarios_auth0(self):
        try:
            token = obtener_token_mgmt()
        except Auth0Error as e:
            raise CommandError(
                f'No se pudo obtener token de Management API.\n'
                f'Verifica AUTH0_MGMT_CLIENT_ID y AUTH0_MGMT_CLIENT_SECRET en .env\n'
                f'Error: {e.message}'
            )

        usuarios = []
        page = 0

        while True:
            response = requests.get(
                _url_auth0('/api/v2/users'),
                headers={'Authorization': f'Bearer {token}'},
                params={
                    'per_page': 100,
                    'page': page,
                    'include_totals': 'true',
                    'fields': 'user_id,email,given_name,family_name,name,app_metadata',
                },
                timeout=15,
            )

            if response.status_code != 200:
                raise CommandError(
                    f'Auth0 respondió con HTTP {response.status_code}: {response.text[:200]}'
                )

            data = response.json()

            # Auth0 con include_totals=true devuelve {users: [...], total: N, ...}
            if isinstance(data, list):
                usuarios.extend(data)
                break

            page_users = data.get('users', [])
            total      = data.get('total', 0)
            usuarios.extend(page_users)

            if len(usuarios) >= total or not page_users:
                break

            page += 1

        return usuarios
