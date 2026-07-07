# Iconografía con Font Awesome 6 – Campus Seguro

**Sesión:** Junio 2026  
**Responsable:** Jordan Garcia  
**Rama de trabajo:** Jordan → mergeada a dev

---

## Por qué se cambió el sistema de iconos

El sistema usaba símbolos Unicode y emojis para representar elementos visuales en la navegación y las tarjetas. Los símbolos Unicode como `▦`, `◈`, `≡`, `◷` son caracteres de texto sin semántica visual clara: no tienen relación con lo que representan y se ven distintos según la fuente del sistema operativo. Los emojis tienen el mismo problema amplificado: en Windows se renderizan con color y con un estilo específico de Microsoft, en Mac con el estilo de Apple, y en sistemas Linux sin entorno gráfico directamente no aparecen.

Esto genera inconsistencia visual cuando el equipo abre la aplicación desde distintas máquinas. Además, los emojis no escalan limpiamente con el CSS: su tamaño, alineación vertical y color no responden a las variables de diseño del sistema.

---

## Solución implementada: Font Awesome 6 Free via CDN

Font Awesome 6 Free es una biblioteca de iconos vectoriales (SVG via fuente web) disponible sin costo. Se integra con una sola línea en el `<head>` de `base.html`, sin instalación, sin npm, sin build tools. Los iconos se insertan con etiquetas `<i>` y heredan el color del CSS del elemento padre, lo que los hace completamente controlables desde las variables de diseño del sistema (`--accent-blue`, `--accent-green`, etc.).

La línea agregada en `base.html` fue:

```html
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css">
```

Al estar en `base.html`, esta línea carga automáticamente en todas las páginas del sistema. No es necesario agregarla en cada plantilla.

---

## Cómo se usan los iconos en el proyecto

Un icono se inserta así en cualquier plantilla:

```html
<i class="fa-solid fa-nombre-del-icono"></i>
```

La clase `fa-solid` indica el estilo sólido (relleno). Font Awesome también tiene `fa-regular` (contorno) y `fa-brands` (logos de marcas), pero en este proyecto solo se usa `fa-solid`.

Para controlar el tamaño se puede usar `style="font-size: 14px;"` en línea, o las clases utilitarias de Font Awesome: `fa-xs`, `fa-sm`, `fa-lg`, `fa-xl`, `fa-2x`. Para alineación en listas de navegación se puede agregar `fa-fw` que da ancho fijo, útil cuando los iconos deben quedar alineados verticalmente en una columna.

El color del icono se controla con la propiedad CSS `color`, ya sea heredado del elemento padre o aplicado directamente:

```html
<i class="fa-solid fa-circle-check" style="color: var(--accent-green);"></i>
```

---

## Mapa de iconos aplicados

Esta tabla documenta qué icono se usa para cada elemento del sistema y el razonamiento detrás de la elección.

**Navegación lateral (sidebar):**

El logo del sistema usa `fa-shield-halved` porque el sistema se llama Campus Seguro y el escudo cortado es la representación estándar de seguridad en sistemas de gestión modernos.

El ítem Dashboard usa `fa-gauge-high` porque es el icono convencional de panel de control o indicadores de rendimiento en dashboards profesionales.

Notificaciones usa `fa-bell`, el estándar universal para alertas y notificaciones.

Ver mis tickets usa `fa-ticket` porque representa directamente un ticket o solicitud.

Crear ticket usa `fa-plus`, que es la acción de agregar algo nuevo.

Todos los tickets (gestor) usa `fa-table-list` porque representa una lista de registros en vista de tabla.

Rendimiento trabajadores usa `fa-chart-bar` porque refiere a métricas y estadísticas de personal.

Business Intelligence usa `fa-chart-line` porque representa tendencias y análisis de datos.

Solicitudes de cuenta usa `fa-user-clock` porque combina la idea de usuario con tiempo de espera.

Usuarios usa `fa-users` para representar la gestión de múltiples personas.

Inasistencias y Registrar Inasistencia usan `fa-calendar-xmark` porque combina calendario con una marca de ausencia.

Materiales usa `fa-boxes-stacked` porque representa inventario o almacén de items.

Validaciones pendientes (guardia) usa `fa-shield-halved` consistente con el rol de seguridad del guardia.

Mis Trabajos (mantención) usa `fa-wrench` porque es el símbolo universal de mantenimiento técnico.

Mi Perfil usa `fa-circle-user` que es el icono estándar de perfil o cuenta personal.

Cerrar sesión usa `fa-right-from-bracket` que representa gráficamente salir de un espacio.

**Card-titles en dashboards:**

Reparaciones completadas usa `fa-circle-check` en verde porque indica una tarea finalizada satisfactoriamente.

Validados por guardia usa `fa-shield-halved` en amarillo porque refiere al rol del guardia que validó.

No reparados usa `fa-circle-xmark` en rojo porque indica un estado negativo o fallo.

Tickets recientes usa `fa-ticket` en azul como referencia directa al objeto principal del sistema.

Tickets críticos activos usa `fa-circle-exclamation` en rojo porque es el icono de alerta crítica.

Top ubicaciones usa `fa-location-dot` en azul porque refiere a lugares físicos del campus.

Acciones rápidas usa `fa-bolt` en amarillo porque representa velocidad y acción inmediata.

Mis revisiones asignadas (guardia) usa `fa-clipboard-list` porque es una lista de tareas asignadas.

Validaciones pendientes (guardia) usa `fa-hourglass-half` en amarillo porque representa tiempo de espera.

Mis validaciones recientes (guardia) usa `fa-check-double` en verde porque indica múltiples validaciones completadas.

Historial de reparaciones (mantención) usa `fa-clock-rotate-left` en azul porque representa historial o registro temporal.

**Botones de acción:**

Tomar trabajo usa `fa-play` porque es la acción de iniciar algo.

Estimar trabajo usa `fa-stopwatch` porque refiere a medir tiempo.

Registrar Avance / Cierre usa `fa-pen-to-square` porque es la acción de escribir o completar un formulario.

No reparable usa `fa-circle-xmark` porque indica que algo no puede completarse.

Ir a Validar y Validar (guardia) usan `fa-shield-halved` consistente con el rol.

**Estados vacíos (empty states):**

Sin historial usa `fa-inbox` con opacidad reducida porque representa una bandeja vacía.

Sin pendientes usa `fa-circle-check` en verde con opacidad reducida porque indica que no hay trabajo pendiente (estado positivo).

Sin inasistencias usa `fa-calendar-check` en verde porque indica que no hay ausencias registradas.

---

## Cómo agregar un icono nuevo

Para buscar el nombre correcto del icono, ir a `fontawesome.com/icons` y filtrar por "Free" y "Solid". El nombre que aparece en el sitio es exactamente el que va en la clase.

Para insertar un icono en un `card-title`:

```html
<div class="card-title">
  <i class="fa-solid fa-nombre" style="color: var(--accent-blue);"></i> Título de la tarjeta
</div>
```

Para insertarlo en un botón:

```html
<a href="..." class="btn btn-primary">
  <i class="fa-solid fa-nombre"></i> Texto del botón
</a>
```

Para un icono en el nav lateral, dentro del `<span class="icon">` que ya existe:

```html
<span class="icon"><i class="fa-solid fa-nombre"></i></span> Texto del menú
```

---

## Archivos modificados

El CDN y los iconos de navegación están en `app/templates/app/base.html`. Los iconos de tarjetas y botones están en `dashboard.html`, `dashboard_gestor.html`, `guardia.html` y `mantencion/dashboard.html`.

Todos los cambios están en el commit `1ed678f` de la rama Jordan.
