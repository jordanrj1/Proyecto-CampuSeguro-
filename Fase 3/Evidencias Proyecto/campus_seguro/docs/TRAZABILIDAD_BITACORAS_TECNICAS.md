# Documentación de Cambios: Módulo de Trazabilidad y Bitácoras Técnicas
**Sistema:** Campus Seguro  
**Fase:** Evidencias de Proyecto / Sprint 2  
**Autor:** Moisés Muñoz S.  

---

## 📑 1. Propósito de los Cambios
Optimizar el flujo de auditoría logística e ingeniería del módulo de trazabilidad de tickets. Se corrigió un desacoplamiento estructural entre la tabla de logs globales (`LogAuditoria`) y las entidades de control operativo (`SesionTrabajo` y `MaterialUtilizado`), permitiendo un desglose granular de las bitácoras diarias y del cierre definitivo de fallas, aislando además el contexto administrativo del perfil de usuario base (alumno/funcionario).

---

## 🛠️ 2. Modificaciones en Backend (`app/views.py`)

### A. Optimización de Consultas Relacionales (Evitar N+1)
En la función `trazabilidad_ticket`, se implementaron políticas de carga ansiosa (*Eager Loading*) mediante el ORM de Django para compactar las peticiones a la base de datos MySQL alojada en Aiven, trayendo los grafos relacionales en un único viaje de red.
* Se incorporó `.prefetch_related('materiales_utilizados__material')` a las sesiones asociadas al ticket.
* Se inyectó `.select_related('material', 'sesion_trabajo')` a la consulta de materiales consumidos para disponibilizar las fechas de término de turno de forma cruzada.

### B. Consolidación de Horas Hombre Dinámicas
Se eliminó la lectura rígida de la columna `horas_hombre` desde la tabla maestra del ticket. Ahora el backend calcula en tiempo de ejecución el costo real acumulado mediante la función de agregación `Sum` de Django:
```python
total_horas_hombre = ticket.sesiones.aggregate(total=Sum('horas_hombre'))['total'] or 0
```

---

## 🎨 3. Rediseño de Interfaces y UX (`trazabilidad.html`)

### A. Ley de Proximidad e Integración del DOM
* **Alineación Conectada:** Se modificó la distribución espacial del historial detallado. Se sustituyó el esquema `justify-content: space-between` por un contenedor flex agrupado a la izquierda (`justify-content: flex-start; gap: 12px;`).
* **Estilo Pill Badge:** El botón "Ver bitácora" fue re-estilizado como una pequeña etiqueta interactiva redondeada con fondos translúcidos, eliminando la confusión visual con botones de envío pesados.

### B. Payload Dinámico en Modales (Avances vs. Finalización)
Se implementó un clonador nativo en JavaScript que extrae plantillas HTML pre-cocinadas y ocultas en el DOM (`payload-log-{{ log.pk }}`). La bitácora adapta su tamaño y contenido según el hito:
* **Hito de Avance Diario:** Despliega de forma compacta la descripción del turno, herramientas utilizadas, duración de la jornada y notas al gestor.
* **Hito de Cierre Definitivo:** Cruza la información física del modelo (alineado a `Relational_1.html`) y dibuja una sección destacada en color verde con la **Causa Raíz** y el **Resumen Técnico General** de la solución (extraído de la sesión de tipo `completado`).

---

## 📊 4. Normalización de Datos en Tablas de Materiales
Se detectó y solucionó un bug de desajuste de atributos donde la cantidad se leía de forma errónea como `{{ m.cantidad }}` en lugar del campo físico legítimo **`cantidad_utilizada`**.
* **Separación de Columnas:** Se normalizó la tabla del pañol separando estrictamente la **Cantidad** (valor numérico) de la **Unidad** (métrica/display).
* **Fecha de Imputación:** Se agregó una columna dedicada a la fecha exacta de uso, mapeada dinámicamente desde el cierre de la jornada de trabajo (`{{ m.sesion_trabajo.fin }}`).

---

## 📸 5. Corrección de Aspecto Visual en Evidencias (Antes y Después)
Se extirpó la propiedad CSS `object-fit: cover;` en la galería de evidencias por terreno debido al efecto de recorte con zoom destructivo que provocaba en las imágenes.
* **Integridad de Imagen:** Se sustituyó por `object-fit: contain;` acompañado de un contenedor de fondo oscuro (`rgba(0,0,0,0.4)`). Esto garantiza la visualización al 100% de la fotografía original (sea vertical u horizontal) sin pérdida de información de los bordes.
* **Feedback de Ampliación:** Se agregó una transición de escala fluida (`transform: scale(1.01);`) al pasar el cursor, manteniendo el enlace con apertura hacia pestaña independiente (`target="_blank"`).

---

## 🔒 6. Matriz de Seguridad y Aislamiento por Rol

Para cumplir con las directrices de diseño de software relativas a la **separación de contextos**, se restringió la visibilidad de datos sensibles del pañol y rendimiento operativo. El usuario base (alumno) y el personal de gestión poseen capas de presentación asimétricas:

```html
{% if request.user.rol != 'usuario' %}
  <div class="card">
    <div class="form-section-title">Historial detallado</div>
    </div>
{% endif %}
```

### Resumen de Permisos de Datos:
1. **Perfil Gestor / Técnico:** Posee control total. Visualiza el Stepper de progreso, desglose de materiales imputados con su fecha, horas hombre acumuladas de la planilla interna y acceso mediante modales a las bitácoras diarias de cada turno de mantención.
2. **Perfil Usuario Base (Alumno):** Capa simplificada. Al consultar el detalle de su incidencia en la vista compartida `shared/ticket_detalle.html`, el sistema oculta por completo las tarjetas de materiales, bitácoras privadas e historial de logs. El alumno solo interactúa con la información de su reporte inicial y el **Stepper de Progreso (Delivery Tracker)**, evitando la sobrecarga de información innecesaria.