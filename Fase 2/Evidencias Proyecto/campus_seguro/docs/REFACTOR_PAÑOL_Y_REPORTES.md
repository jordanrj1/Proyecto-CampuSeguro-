# 📄 Documentación: Restricción por Especialidad y Fixes Analíticos en Bodega

### 📋 Resumen
Se ha implementado una regla de negocio que restringe el catálogo de insumos de bodega en base a las **Especialidades Técnicas (M:N)** del técnico en sesión para optimizar sus tiempos de búsqueda en terreno. Adicionalmente, se integró un bypass dinámico (*checkbox*) fila por fila en el frontend, se corrigieron los bugs de duplicación del Formset y se resolvieron las fugas de IDs numéricos crudos en los selectores/filtros del motor de *Business Intelligence* (BI).

---

### Cambios implementados

* **Filtrado Adaptativo del Pañol (`app/views.py`):** Modificación del controlador `completar_mantencion`. Si el técnico posee especialidades, el sistema aísla relacionalmente sus insumos; si la cuenta es genérica (no posee oficios registrados), levanta el catálogo de bodega completo de manera segura.
* **Bypass de Catálogo Fila por Fila (`app/templates/app/mantencion/completar.html`):** Inyección de un interruptor condicional (`🔓 Mostrar todo el pañol`) integrado en cada fila dinámica de materiales. Al activarse, JavaScript conmuta las opciones del selector en caliente de forma independiente sin alterar las demás filas.
* **Refactor Integral del Clonador de Formularios (JS):** Reescritura del script del botón `+ Agregar material` utilizando selectores dinámicos basados en expresiones regulares (`id$="-TOTAL_FORMS"`). Esto mitiga los crasheos de duplicación al independizar el script de los prefijos nativos de Django.
* **Flujo de Deshacer Eliminación (UX):** El botón de remoción de materiales (`✕`) ahora opera como un interruptor. Al presionarlo en un registro existente, marca el campo oculto `DELETE`, bloquea los controles internos y muta visualmente a un ícono de restauración (`↩️`) para evitar pérdidas accidentales de datos escritos.
* **Aliasing Relacional en BI (`F() Expression`):** Corrección de pérdidas de renderizado en la pestaña de materiales de BI. Se implementó una función de alias en la vista para empaquetar la navegación de claves foráneas con doble guion bajo (`material__categoria__nombre_display`) en una clave plana unificada (`categoria_nombre`), estabilizando los gráficos del frontend.
* **Fix de Consistencia en Filtros Transaccionales:** Resolución del crasheo `ValueError: Field 'id' expected a number but got 'plomeria'`. Se reestructuró la query analítica para interceptar el código lógico de la URL mediante la propiedad de navegación `material__categoria__codigo`.

---

### 🎯 Criterios de Aceptación
* [x] El mantenedor ve inicialmente solo los materiales que competen a sus áreas de peritaje técnico en la pantalla de reparación.
* [x] El técnico puede evadir el filtro de su especialidad y desplegar todo el pañol de la institución de forma individual por fila.
* [x] El botón de añadir materiales clona de forma indefinida y consistente los índices incrementales del Formset.
* [x] Las opciones del dropdown de filtros en el módulo de BI y los chips informativos de selección despliegan nombres institucionales descriptivos en lugar de IDs numéricos o códigos lógicos de URLs.

---

### 📂 Archivos Modificados
* `app/views.py` - Inyección de lógica de aislamiento por especialidad en `completar_mantencion`, aliasing con `F()` en `materiales_top`, sanación del filtro por código en `gestor_bi` y serialización de catálogos en JSON.
* `app/templates/app/mantencion/completar.html` - Incorporación de la directiva informativa calipso, checkboxes de bypass de pañol, ocultamiento estético de variables de control y nuevo script controlador del Formset.
* `app/templates/app/dashboard_usuario.html` - Corrección de la celda de estado transaccional para leer `t.estado.nombre_display`.
* `app/templates/app/dashboard_gestor.html` - Refactor del widget "Por categoría" para renderizar la propiedad agrupada `c.categoria__nombre_display`.
* `app/templates/app/materiales.html` - Reemplazo del método estático extinto por navegación orientada a objetos en la columna de familias logísticas.
* `app/templates/app/bi.html` - Adaptación de la grilla global de compras para acoplarse al alias del backend, corrección sintáctica del bucle de stock crítico y desempaquetado de tuplas `(código, nombre)` en los selectores de búsqueda.

---

### ⚙️ Instrucciones para el Equipo

> 💡 **Nota Operativa:**
> Tras realizar un `git pull` de esta rama, **no es necesario ejecutar migraciones de base de datos**, ya que toda la lógica fue resuelta a nivel de controladores (Python), manipulación dinámica del DOM (JavaScript) y consultas relacionales nativas del ORM. El sistema se encuentra listo para pruebas en caliente en el entorno local.