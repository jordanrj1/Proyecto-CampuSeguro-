# Mejoras de Interfaz de Usuario – Campus Seguro

**Sesión:** Junio 2026  
**Responsable:** Jordan Garcia  
**Rama de trabajo:** Jordan → mergeada a dev

---

## Contexto

La profesora evaluadora señaló que la interfaz debía ser más amigable con el usuario, con mejor jerarquía visual y menos ruido. El sistema funcionaba correctamente pero la navegación resultaba poco clara: no había indicación de en qué sección estaba el usuario, los títulos de las tarjetas mezclaban texto con emojis sin consistencia, y algunos errores silenciosos hacían que columnas importantes mostraran datos vacíos. Esta sesión abordó todas esas observaciones.

---

## Breadcrumbs en todos los dashboards

Se agregó un bloque `{% block breadcrumb %}` en la plantilla base (`base.html`) que muestra la ruta de navegación debajo del logo, en todo momento. Cada plantilla que hereda de la base puede definir su propia miga de pan. El bloque ya estaba definido en `base.html` con el enlace "Inicio" fijo; cada vista hija agrega los segmentos específicos.

Los dashboards que no tenían breadcrumb fueron actualizados:

`dashboard.html` ahora muestra `Inicio › Mi Panel`, que le dice al usuario base exactamente dónde está parado.

`dashboard_gestor.html` muestra `Inicio › Panel de Gestión`, consistente con el título de la página.

Las demás vistas que ya tenían breadcrumb desde sesiones anteriores no fueron modificadas.

---

## Limpieza de card-titles

Los títulos de las tarjetas (`card-title`) mezclaban emojis de sistema operativo con texto. Esto genera inconsistencia visual porque los emojis se renderizan distinto en Windows, Mac y Linux, y su tamaño no respeta la tipografía del diseño. Se eliminaron todos los emojis de los `card-title` en los cuatro dashboards principales.

En `dashboard_gestor.html` los títulos afectados fueron: "Reparaciones completadas", "Validados por guardia", "No reparados", "Tickets recientes", "Tickets críticos activos", "Top ubicaciones con incidentes" y "Acciones rápidas". Los iconos de las alertas operativas (los banners de aviso amarillo, verde, rojo) también se limpiaron para que el color lo controle el CSS y no un emoji.

En `guardia.html` y `mantencion/dashboard.html` se hizo el mismo proceso en los títulos de sus tarjetas.

---

## Corrección de datos en dashboards

Durante la revisión se detectaron dos errores silenciosos que mostraban datos incorrectos.

**Dashboard de mantención – columna Horas Hombre:** La tabla de historial de reparaciones mostraba el tiempo estimado (`obtener_tiempo_estimado`) en lugar de las horas reales trabajadas. Esto es incorrecto porque el tiempo estimado viene de `AsignacionTicket` y es una proyección inicial, no lo que el técnico efectivamente registró. Se corrigió en `views.py` usando una anotación con `Subquery` que suma `SesionTrabajo.horas_hombre` filtrado por técnico y ticket:

```python
from django.db.models import OuterRef, Subquery, Sum

hh_subquery = SesionTrabajo.objects.filter(
    tecnico=user, ticket=OuterRef('ticket')
).values('ticket').annotate(total=Sum('horas_hombre')).values('total')

historial_qs = completados.select_related('ticket').annotate(
    hh_reales=Subquery(hh_subquery)
).order_by('-fecha_registro')[:8]
```

La plantilla lee `{{ r.hh_reales }}` en lugar del campo de estimación anterior.

**Dashboard de guardia – badge "Vencida":** El template usaba `{% if asignacion.fecha_programada < today %}` pero la variable `today` nunca se pasaba desde la vista. El resultado era que el badge nunca aparecía aunque la fecha ya hubiera pasado. Se corrigió en `dashboard_guardia` en `views.py` agregando `'today': hoy` al diccionario de contexto.

---

## Corrección del campo estado en dashboards

Las tablas de tickets en `dashboard.html` y `dashboard_gestor.html` usaban `t.get_estado_display` para mostrar el nombre del estado. Como `estado` es una clave foránea a `EstadoCatalogo` y no un campo de elección estático, Django no genera automáticamente ese método. El valor correcto es `t.estado.nombre_display`, que accede directamente al atributo del modelo relacionado. Se corrigió en ambos archivos con reemplazo global.

---

## Archivos modificados

Las vistas afectadas están en `app/views.py` en las funciones `dashboard_usuario`, `dashboard_gestor`, `dashboard_guardia` y `dashboard_mantencion`. Las plantillas afectadas son `app/templates/app/dashboard.html`, `dashboard_gestor.html`, `guardia.html` y `mantencion/dashboard.html`.

Todos los cambios están en el commit `cb80209` de la rama Jordan.
