from .models import Notificacion


def notificaciones_no_leidas(request):
    "Context processor: hace disponible el conteo de notificaciones no leidas en todos los templates"
    if request.user.is_authenticated:
        count = Notificacion.objects.filter(
            destinatario=request.user, leida=False, archivada=False, deleted_at__isnull=True
        ).count()
        return {'notif_no_leidas_count': count}
    return {'notif_no_leidas_count': 0}
