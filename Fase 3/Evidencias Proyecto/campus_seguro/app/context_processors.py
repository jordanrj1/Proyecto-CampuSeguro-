from django.core.cache import cache
from .models import Notificacion


def notificaciones_no_leidas(request):
    """
    Cuenta las notificaciones no leídas del usuario y las deja disponibles
    en todos los templates como {{ notif_no_leidas_count }}.

    Se guarda en cache 60 segundos para no golpear la base de datos en cada
    request — este procesador corre en absolutamente todas las páginas del
    sistema. Cuando el usuario marca notificaciones como leídas, las vistas
    correspondientes limpian el cache para que el badge se actualice de inmediato.
    """
    if request.user.is_authenticated:
        cache_key = f'notif_count_{request.user.pk}'
        count = cache.get(cache_key)
        if count is None:
            count = Notificacion.objects.filter(
                destinatario=request.user, leida=False, archivada=False, deleted_at__isnull=True
            ).count()
            cache.set(cache_key, count, 60)
        return {'notif_no_leidas_count': count}
    return {'notif_no_leidas_count': 0}
