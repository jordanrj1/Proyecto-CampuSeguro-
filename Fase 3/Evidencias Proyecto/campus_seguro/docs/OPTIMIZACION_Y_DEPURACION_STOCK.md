# 📄 Documentación: Optimización del Catálogo y Depuración del Módulo de Stock (Fase 2)

## 📋 Resumen

Se ha realizado una reestructuración integral y una depuración arquitectónica del módulo de **Catálogo de Materiales** en el sistema **Campus Seguro**. Con el objetivo de optimizar el alcance del proyecto de título, asegurar los plazos de entrega de la Fase 2 y mitigar la complejidad logística innecesaria en terreno, **se eliminó por completo el control activo de stock físico e inventarios** (`stock_actual`, `stock_minimo`, alertas de reabastecimiento) tanto de la base de datos como de las interfaces del sistema.

Este cambio estratégico transforma el antiguo panel de inventario estático en un **Catálogo Maestro Operativo y Analítico**, alineado directamente con los requerimientos técnicos de la comisión evaluadora. En lugar de procesar mermas y alertas de pañol, el sistema delega el peso logístico y se enfoca en el **Motor Analítico de Business Intelligence (BI)**, implementando agregaciones dinámicas que calculan el consumo histórico transaccional en tiempo real. 

De este modo, se garantiza que el Gestor disponga de métricas exactas sobre las tendencias de consumo por rubro, técnico e incidente para compras inteligentes, sin lidiar con los riesgos de inconsistencia de stock que conllevan los flujos manuales de terreno.

---

### 🛠️ Cambios Implementados

* **Simplificación y Limpieza del Modelo Local (`app/models.py`):** Eliminación física de las columnas `stock_actual` y `stock_minimo` dentro de la entidad `Material`, así como la propiedad computada `@property def bajo_stock`. Inclusión de una nueva propiedad optimizada orientada a objetos: `@property def total_utilizado`, la cual aprovecha la relación inversa del ORM de Django (`self.consumos.all()`) para sumar de forma matemática las cantidades reales de insumos consumidos en terreno.
* **Depuración del Script de Seeding (`poblar_sistema.py`):** Remoción de los atributos e índices de existencias (`'stock_actual'`, `'stock_minimo'`) dentro de los diccionarios de datos estructurados de la lista `materiales_base` y en el método transaccional `get_or_create()`, blindando el comando de población masiva contra fallas de columnas inexistentes.
* **Ajuste del Back-Office en Suite del Superusuario (`app/admin.py`):** Modificación del configurador visual `MaterialAdmin`. Se extirparon las variables de inventario de las tuplas de control del panel administrativo (`list_display` y `list_filter`), reemplazándolas por un filtro interactivo por `unidad` de medida (metros, unidades, rollos) para una ordenación más limpia de la bodega.
* **Limpieza de Capa de Formularios Django (`app/forms.py`):** Actualización de los metadatos de la clase `MaterialForm` para suprimir los inputs numéricos de stock, evitando que el motor del framework lance excepciones de tipo `FieldError` al validar o instanciar peticiones POST de nuevos insumos.
* **Refactor del Motor Analítico de BI (`app/views.py`):** Reestructuración integral del controlador de analíticas `gestor_bi`. Se eliminaron las consultas SQL agregadas encargadas de auditar productos críticos o desabastecidos (`stock_cero` y `stock_bajo`), protegiendo la API del panel de control de caídas críticas por llamadas a palabras clave obsoletas.
* **Refactor de Interfaz de Business Intelligence (`bi.html`):** Rediseño visual de la sección de visualización de materiales. Se redujo la grilla de KPIs transaccionales de 4 a **2 columnas** de lectura masiva (*"Materiales distintos usados"* y *"Categorías consumidas"*). Asimismo, se removió la tabla completa de auditoría de *"Stock bajo mínimo – Acción de compra requerida"* que residía al final de la plantilla.
* **Adecuación de Vistas del Catálogo Operativo (Templates HTML):**
  * Refactor de la plantilla maestra del pañol (`materiales.html`) para retirar las columnas de inventario físico y estado crítico, inyectando la nueva columna analítica de lectura orientada a objetos: `{{ m.total_utilizado|default:"0" }}`.
  * Modificación del formulario transaccional de creación y edición (`material_form.html`) para remover el contenedor CSS `form-grid-3` y depurar la interfaz del técnico, logrando una carga limpia centrada únicamente en propiedades técnicas permanentes.

---

### 🎯 Criterios de Aceptación

* La visualización del catálogo maestro de insumos carga de manera estable e inmediata en el frontend sin requerir columnas de existencias estáticas.
* Las peticiones de guardado, actualización y edición de materiales se ejecutan de manera consistente en el motor SQL local **sin exigir límites numéricos de inventario**.
* El módulo de **Business Intelligence (BI)** procesa el tráfico de datos del pañol basándose estrictamente en agregaciones históricas reales de consumo, desplegando gráficos coherentes de tendencias y demanda.
* La propiedad dinámica `total_utilizado` calcula de forma exacta el acumulado de materiales gastados en terreno a través de todas las órdenes de mantención finalizadas o registradas como avances, reflejándose los cambios de inmediato en la grilla del catálogo.
* El esquema de la base de datos prescinde de lógica redundante de stock, **disminuyendo el peso de almacenamiento** y optimizando el rendimiento de las consultas para auditorías de compras inteligentes.

---

### 📂 Archivos Modificados

* `app/models.py` - Eliminación de variables físicas de inventario en `Material` e inyección de la propiedad inversa acumulativa `.total_utilizado`.
* `app/admin.py` - Remoción de campos obsoletos en la clase `MaterialAdmin` y personalización de filtros por unidad de medida.
* `app/forms.py` - Depuración de campos en el meta-formulario `MaterialForm` de inserción del catálogo.
* `app/views.py` - Saneamiento de consultas con filtros o anotaciones relativas a existencias dentro de la vista analítica del gestor (`gestor_bi`).
* `app/management/commands/poblar_sistema.py` - Corrección de la matriz estructurada de insumos base de la Fase 2, omitiendo claves numéricas de stock.
* `app/templates/app/materiales.html` - Modificación de la tabla del catálogo para remover el estado de stock e incorporar la columna de total consumido histórico.
* `app/templates/app/material_form.html` *(Edición/Creación)* - Limpieza estructural del formulario HTML para descartar los inputs de stock mínimo y actual.
* `app/templates/app/bi.html` - Ajuste de la grilla de componentes visuales de KPIs, rediseño de pestañas de materiales y eliminación de tablas de alertas de reposición.