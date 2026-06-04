# ═══════════════════════════════════════════════════════════════
# CAMPUS SEGURO - Comando: limpiar_cuentas
# ─────────────────────────────────────────────────────────────
# Archivo: app/management/commands/limpiar_cuentas.py
#
# PROPOSITO:
#   Elimina cuentas de prueba de la BD local y opcionalmente de Auth0.
#   Util para reiniciar el entorno antes de una demo o nueva sesion
#   de pruebas, sin necesidad de borrar toda la base de datos.
#
# QUE PRESERVA (nunca toca):
#   - El usuario gestor (rol='gestor')
#   - Superusuarios de Django (is_superuser=True)
#   - EstadoCatalogo, Ubicacion, Material y demas catalogos
#   - Tickets y registros existentes
#
# QUE ELIMINA:
#   - Usuarios con rol distinto a 'gestor' y no superusuarios
#   - Sus registros en Auth0 (si se usa --auth0)
#   - Sus notificaciones y tokens de recuperacion asociados
#
# USO:
#   python manage.py limpiar_cuentas              (solo BD local, pide confirmacion)
#   python manage.py limpiar_cuentas --auth0      (BD local + Auth0)
#   python manage.py limpiar_cuentas --confirmar  (sin prompt interactivo)
#   python manage.py limpiar_cuentas --auth0 --confirmar
#   python manage.py limpiar_cuentas --dry-run    (solo muestra, no borra)
#
# ADVERTENCIA:
#   Esta operacion es IRREVERSIBLE. Los usuarios eliminados de Auth0
#   no se pueden recuperar. Usar solo en entornos de desarrollo/pruebas.
# ═══════════════════════════════════════════════════════════════

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from app.models import Usuario
from app.auth0_service import obtener_token_mgmt, Auth0Error


def _url_auth0(path):
    return f"https://{settings.AUTH0_DOMAIN}{path}"


class Command(BaseCommand):
    help = (
        'Elimina cuentas de prueba de la BD local (y opcionalmente de Auth0). '
        'Nunca elimina al gestor ni superusuarios.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--auth0',
            action='store_true',
            help='Tambien elimina los usuarios de Auth0 (requiere credenciales M2M).',
        )
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Omite la confirmacion interactiva (para scripts).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo muestra que se eliminaria, sin borrar nada.',
        )

    def handle(self, *args, **options):
        incluir_auth0 = options['auth0']
        confirmar     = options['confirmar']
        dry_run       = options['dry_run']

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('=' * 60))
        self.stdout.write(self.style.MIGRATE_HEADING('  CAMPUS SEGURO - Limpieza de cuentas de prueba'))
        if dry_run:
            self.stdout.write(self.style.WARNING('  MODO DRY-RUN: no se eliminara nada'))
        self.stdout.write(self.style.MIGRATE_HEADING('=' * 60))
        self.stdout.write('')

        # ── Obtener usuarios candidatos a eliminar ─────────
        candidatos = Usuario.objects.filter(
            is_superuser=False
        ).exclude(rol='gestor')

        if not candidatos.exists():
            self.stdout.write('  No hay cuentas de prueba para eliminar.')
            self.stdout.write('')
            return

        # ── Mostrar lista ──────────────────────────────────
        self.stdout.write(f'  Se eliminaran {candidatos.count()} cuenta(s):\n')
        for u in candidatos:
            auth0_tag = f'  [Auth0: {u.auth0_sub}]' if u.auth0_sub else '  [sin Auth0 sub]'
            self.stdout.write(
                f'    - {u.correo_institucional:<35} '
                f'rol={u.rol:<12} '
                f'estado={u.estado_cuenta.codigo}'
            )
            if incluir_auth0:
                self.stdout.write(f'      {auth0_tag}')

        self.stdout.write('')

        if incluir_auth0:
            self.stdout.write(
                self.style.WARNING(
                    '  ADVERTENCIA: Se eliminaran tambien de Auth0.\n'
                    '  Esta accion es IRREVERSIBLE en Auth0.'
                )
            )
            self.stdout.write('')

        # ── Confirmacion ───────────────────────────────────
        if dry_run:
            self.stdout.write(self.style.NOTICE('  [DRY-RUN] No se realizo ninguna eliminacion.'))
            self.stdout.write('')
            return

        if not confirmar:
            respuesta = input('  Confirmar eliminacion? [s/N]: ').strip().lower()
            if respuesta not in ('s', 'si', 'sí', 'y', 'yes'):
                self.stdout.write(self.style.WARNING('  Operacion cancelada.'))
                self.stdout.write('')
                return

        # ── Preparar token Auth0 si se necesita ───────────────
        token_auth0 = None
        if incluir_auth0:
            try:
                token_auth0 = obtener_token_mgmt()
            except Auth0Error as e:
                raise CommandError(
                    f'No se pudo obtener token de Auth0: {e.message}\n'
                    f'Verifica AUTH0_MGMT_CLIENT_ID y AUTH0_MGMT_CLIENT_SECRET en .env'
                )

        # ── Eliminar usuario por usuario (Django primero, Auth0 despues) ──
        # Orden correcto: si Django falla por PROTECT, NO se borra de Auth0.
        # Esto evita el estado inconsistente donde Auth0 elimina al usuario
        # pero Django no puede hacerlo por tener tickets u otras relaciones.
        # PROTECT aplica en: Ticket.creado_por, ValidacionGuardia.guardia,
        # RegistroMantencion.tecnico, AsignacionTicket.usuario, NoReparable.tecnico.
        # Solucion para usuarios con PROTECT: usar /gestor/usuarios/<pk>/suspender/
        eliminados_local  = 0
        eliminados_auth0  = 0
        fallidos_protect  = 0
        fallidos_auth0    = 0

        self.stdout.write('')
        self.stdout.write('  Eliminando...')

        for u in list(candidatos):
            # 1. Intentar eliminar de Django primero
            try:
                with transaction.atomic():
                    u.delete()
                eliminados_local += 1
                self.stdout.write(f'    OK BD local: {u.correo_institucional}')
            except Exception:
                fallidos_protect += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'    OMITIDO {u.correo_institucional} '
                        f'(tiene tickets o registros protegidos - suspender en lugar de eliminar)'
                    )
                )
                continue  # No tocar Auth0 si Django fallo

            # 2. Solo si Django tuvo exito: eliminar de Auth0
            if token_auth0 and u.auth0_sub:
                try:
                    sub_encoded = requests.utils.quote(u.auth0_sub, safe='')
                    resp = requests.delete(
                        _url_auth0(f'/api/v2/users/{sub_encoded}'),
                        headers={'Authorization': f'Bearer {token_auth0}'},
                        timeout=10,
                    )
                    if resp.status_code in (204, 404):
                        eliminados_auth0 += 1
                        self.stdout.write(f'      + Auth0: {u.correo_institucional} eliminado')
                    else:
                        fallidos_auth0 += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f'      + Auth0 ERR {u.correo_institucional} - HTTP {resp.status_code}'
                            )
                        )
                except Exception as e:
                    fallidos_auth0 += 1
                    self.stdout.write(
                        self.style.ERROR(f'      + Auth0 ERR {u.correo_institucional} - {e}')
                    )

        total_local = eliminados_local
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(f'  OK {eliminados_local} usuario(s) eliminado(s) de la BD local')
        )
        if fallidos_protect:
            self.stdout.write(
                self.style.WARNING(
                    f'  {fallidos_protect} usuario(s) omitido(s) por tener datos protegidos.\n'
                    f'  Para desactivarlos usa: /gestor/usuarios/<pk>/suspender/'
                )
            )

        # ── Resumen ────────────────────────────────────────
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('-' * 60))
        self.stdout.write(f'  BD local  : {eliminados_local} eliminado(s), {fallidos_protect} omitido(s) por PROTECT')
        if incluir_auth0:
            self.stdout.write(f'  Auth0     : {eliminados_auth0} eliminado(s), {fallidos_auth0} fallido(s)')
        self.stdout.write(self.style.MIGRATE_HEADING('-' * 60))
        self.stdout.write('')
