# Documentación de Cambios: Sistema de Control y Validaciones - Módulo de Mantención

## 1. Módulo de Vistas (`app/views.py`)

Se implementó un robusto sistema de guardias de validación dentro de la función `completar_mantencion` para asegurar la integridad de los datos en la base de datos de Aiven, unificando la experiencia de usuario a través del sistema de alertas existente (`responder_con_error`).

### Validaciones en Registro de Avance (Caso A) y Cierre Técnico (Caso B)
* **Observaciones para el Gestor:**
    * Se sanitizó la captura del campo mediante `.strip()`.
    * Se configuró un control de desbordamiento de búfer limitando el texto a un máximo de **500 caracteres** para optimizar el almacenamiento.
    * *Regla de negocio flexible:* Si el técnico no ingresa observaciones, el sistema inyecta automáticamente el texto por defecto: `"Sin observaciones adicionales."` evitando valores nulos o vacíos.

### Validación de Materiales Obligatorios via FormSet
* Por defecto, Django permite el envío de FormSets de materiales vacíos. Se añadió un bucle relacional para inspeccionar cada formulario dinámico enviado.
* Se desarrolló un contador de materiales válidos que ignora filas vacías o marcadas para eliminación (`DELETE`).
* Si el contador es igual a `0`, la vista interrumpe el flujo operativo y retorna un cartel de advertencia obligando a declarar al menos un insumo consumido en el turno.

### Interceptor de Erros Internos de FormSet (Cantidades)
* Se interceptaron las excepciones internas de validación del `MaterialUtilizadoFormSet` (ej: cantidades vacías, menores a 1, o caracteres inválidos).
* Se estructuró un extractor de errores que traduce los nombres técnicos de los campos (`cantidad_utilizada` ➔ `"Cantidad"`) y empaqueta el primer mensaje de error de Django dentro del contenedor estético de advertencias rojas del sistema.

### Validación de Evidencia Fotográfica (Solo Caso B)
* Se implementó el aislamiento de flujos: la foto es opcional para avances diarios, pero **100% obligatoria** para el Acta de Cierre definitivo.
* Se programó una guardia sobre `request.FILES.get('foto_final')` que frena la persistencia en base de datos y Cloudinary si el archivo no está presente al momento de finalizar el ticket.

---

## 2. Componente de Interfaz (`app/templates/app/completar_mantencion.html`)

Se rediseñó la experiencia de usuario (UX) del pañol y los indicadores visuales para reflejar de forma dinámica las nuevas reglas del negocio.

### UI Dinámica para Campos Obligatorios
* Se modificó la función constructora `alternarCamposFormulario()`. Al activar el interruptor de **"Finalizar y Cerrar Ticket"**, el título de la sección fotográfica cambia dinámicamente a **`📷 Foto del trabajo terminado *`**, añadiendo el asterisco visual de obligatoriedad en tiempo de ejecución.

---

## 3. Optimización del Dashboard Técnico (`app/templates/app/dashboard_mantencion.html`)

Se corrigió el error sintáctico y de arquitectura heredado del antiguo modelo `RegistroMantencion` tras migrar la persistencia del esfuerzo temporal al modelo relacional `SesionTrabajo`.

### Corrección de Columnas de Esfuerzo (HH y Tiempo)
* Se eliminaron las llamadas a los campos obsoletos `r.horas_hombre` y `r.tiempo_total_minutos`.
* **Horas Hombre (HH):** Se vinculó de manera segura a la estimación del ciclo de vida del ticket mediante el método `{{ r.ticket.obtener_tiempo_estimado|default:'0.0' }} hrs`.
* **Tiempo de Resolución de Incidencia:** Se resolvió el error `TemplateSyntaxError: Invalid filter 'division_segundos_horas'` reemplazando la lógica personalizada por el filtro nativo y eficiente de Django **`timesince`**:
    ```html
    {% if r.ticket.cerrado_at %}
       En {{ r.ticket.created_at|timesince:r.ticket.cerrado_at }}
    {% endif %}
    ```
    Esto procesa en el servidor la diferencia de tiempo exacta entre la creación del incidente y el cierre definitivo por el técnico de forma nativa.
* **Persistencia de Fecha:** Se unificó el despliegue cronológico utilizando la fecha de término real del trabajo (`r.ticket.fin_trabajo_at`) con un fallback seguro hacia la fecha de registro original.