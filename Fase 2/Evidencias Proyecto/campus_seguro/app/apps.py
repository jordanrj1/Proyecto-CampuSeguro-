from django.apps import AppConfig


class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(_setup_inicial, sender=self)


def _setup_inicial(sender, **kwargs):
    """
    Se ejecuta automáticamente después de cada `migrate`.
    Si la BD está vacía (entorno nuevo), puebla los catálogos y crea el admin.
    Si ya tiene datos, no hace nada (idempotente).
    """
    try:
        from app.models import EstadoCatalogo, Usuario

        # ── 1. Catálogos y ubicaciones ───────────────────────────
        if EstadoCatalogo.objects.count() == 0:
            from django.core.management import call_command
            call_command('poblar_sistema', verbosity=0)

        # ── 2. Gestor admin ──────────────────────────────────────
        if not Usuario.objects.filter(is_superuser=True).exists():
            from app.models import EstadoCatalogo as EC
            try:
                estado_activa = EC.objects.get(entidad='cuenta', codigo='activa')
            except EC.DoesNotExist:
                return  # poblar_sistema no corrió aún, seguro en migración temprana

            email = 'gestor@duocuc.cl'
            if not Usuario.objects.filter(correo_institucional__iexact=email).exists():
                u = Usuario(
                    username=email,
                    email=email,
                    correo_institucional=email,
                    first_name='Admin',
                    last_name='Campus',
                    rut='12.345.678-9',
                    rol='gestor',
                    estado_cuenta=estado_activa,
                    is_active=True,
                    is_staff=True,
                    is_superuser=True,
                    activo=True,
                )
                u.set_password('CampusAdmin2024!')
                u.save()
            else:
                # Ya existe: asegurar permisos de admin
                u = Usuario.objects.get(correo_institucional__iexact=email)
                changed = False
                if not u.is_staff:
                    u.is_staff = True
                    changed = True
                if not u.is_superuser:
                    u.is_superuser = True
                    changed = True
                if not u.has_usable_password():
                    u.set_password('CampusAdmin2024!')
                    changed = True
                if changed:
                    u.save()

    except Exception:
        # Durante las primeras migraciones las tablas aún no existen — ignorar
        pass
