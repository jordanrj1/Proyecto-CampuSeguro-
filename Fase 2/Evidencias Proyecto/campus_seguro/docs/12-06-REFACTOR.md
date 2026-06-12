# 📄 Documentación: Normalización Maestra y Motor Analítico (3FN)

## 📋 Resumen

Se ha implementado, normalizado y optimizado completamente el módulo analítico de **Categorías de Tickets**, **Categorías de Materiales**, y el sistema relacional de **Especialidades Técnicas** para el personal de Mantención en el sistema **Campus Seguro**. Se eliminaron por completo las opciones estáticas de texto plano escritas fijas en el código (`CHOICES` hardcoded) en favor de una arquitectura dinámica indexada hacia tablas maestras independientes.

Este cambio estratégico blinda el modelo relacional del proyecto de título ante la comisión, dejando la base de datos optimizada en **Tercera Forma Normal (3FN)**. Esto permite el correcto funcionamiento de las consultas de agregación avanzadas del motor de *Business Intelligence* (BI), garantizando que los tableros de control y métricas de KPIs en los Dashboards del Gestor rendericen nombres descriptivos limpios en lugar de claves primarias numéricas o códigos internos. 

Asimismo, se mantiene una arquitectura desacoplada con **Auth0**, delegando en la nube únicamente la Identidad y el Rol Global, mientras que las competencias y oficios técnicos específicos se administran localmente a través de relaciones Muchos a Muchos (M:N) controladas por el Gestor.

---

### Cambios implementados

* **Normalización de Base de Datos (3FN & M:N):** Eliminación de los arreglos estáticos `CATEGORIA_CHOICES` dentro de los modelos `Ticket` y `Material`. Creación de los nuevos modelos maestros `CategoriaTicket` y `CategoriaMaterial` vinculados mediante llaves foráneas (`ForeignKey`). Consolidación del modelo `Especialidad` vinculado a `Usuario` mediante una tabla intermedia de quiebre para admitir perfiles técnicos modulares.
* **Seeding Unificado Avanzado:** Actualización del comando de gestión en lote de Django (`poblar_sistema`) que consolida de forma automatizada y segura la inyección de categorías de tickets, categorías logísticas de bodega, catálogo de especialidades institucionales e insumos base del pañol, entrelazándolos dinámicamente.
* **Refactor del Motor de Business Intelligence (`app/views.py`):** Reestructuración integral de las funciones de agrupación métrica (`gestor_bi`, `dashboard_gestor` y `reporte_materiales`). Se mutaron los métodos `.values()` y `.annotate()` para navegar relacionalmente a través de las llaves foráneas usando el doble guion bajo (`categoria__nombre_display`), resolviendo las fugas de datos que mostraban IDs numéricos crudos en los gráficos del frontend.
* **Administración Dinámica de Especialidades:** Creación del endpoint controlador `actualizar_especialidades_mantenedor()` que utiliza el método relacional `.set()` de Django para limpiar, actualizar y guardar en lote las competencias de un técnico en la tabla intermedia sin alterar su registro de identidad en Auth0.
* **Habilitación en el Back-Office (`app/admin.py`):** Registro formal de las nuevas entidades maestras en el panel de administración de Django, configurando columnas de visualización optimizadas (`list_display`) y filtros interactivos para el control total del Superusuario.
* **Migración de Lógica Relacional en Frontend (Templates HTML):** Refactor completo de las plantillas transaccionales del sistema (`ticket.html`, `derivar.html`, `completar.html`) para resolver las pérdidas de renderizado y caídas del servidor. Se reemplazó el método de texto plano antiguo `{{ t.get_categoria_display }}` por navegación orientada a objetos: `{{ t.categoria.nombre_display|default:'Sin Categoría' }}`.
* **Interfaz Operativa Reactiva Modal:** Rediseño de la bandeja `usuarios.html` mediante la integración de un contenedor modal emergente y funciones en JavaScript que permiten al Gestor modificar los oficios de cualquier mantenedor en tiempo real de forma segura y visual.

---

### 🎯 Criterios de Aceptación

* El catálogo de clasificación operativa, oficios técnicos e insumos logísticos se administra de manera **100% dinámica** desde la base de datos y no requiere alterar código Python para añadir nuevos rubros.
* Las peticiones POST de creación y derivación de incidentes **validan e insertan** de forma consistente los identificadores relacionales numéricos en el motor SQL local.
* Los tableros de control y reportes de rendimiento de **Business Intelligence (BI)** renderizan establemente cadenas de texto con los nombres descriptivos de las categorías en todas sus secciones.
* El Gestor puede añadir o remover múltiples especialidades a un técnico activo desde la lista de usuarios, reflejándose los cambios de inmediato mediante distintivos visuales (badges).
* El motor de base de datos **aprovecha los índices de claves foráneas**, quedando listo para calcular sumas, promedios y conteos analíticos de KPIs a gran escala sin degradación de rendimiento.

---

### 📂 Archivos Modificados

* `app/models.py` - Inclusión de los modelos `CategoriaTicket`, `CategoriaMaterial` y tablas de quiebre para `Especialidad`.
* `app/views.py` - Ajuste de consultas de agrupación analítica (`__nombre_display`), actualización de filtros por código de categoría y nueva lógica transaccional para el guardado de especialidades técnicos (`.set()`).
* `app/forms.py` - Adecuación del inicializador `__init__` en `TicketForm` para limpiar y gestionar las propiedades de nulos y etiquetas de los selectores.
* `app/admin.py` - Registro y personalización visual de las nuevas tablas maestras de categorías en la suite del Superusuario.
* `app/management/commands/poblar_sistema.py` - Comando centralizado de inicialización de datos y sembrado del catálogo institucional de la Fase 2.
* `app/templates/app/crear_ticket.html` - Acople del formulario dinámico del incidente al contexto de opciones relacionales.
* `app/templates/app/mis_tickets.html` - Modificación de la celda de categoría en la grilla del historial del solicitante.
* `app/templates/app/ticket.html` - Actualización sintáctica de la columna de clasificación en el panel general de supervisión del Gestor y ajuste del filtro.
* `app/templates/app/derivar.html` - Ajuste del resumen informativo del incidente previo a la asignación de guardias/técnicos con fecha programada.
* `app/templates/app/bi.html` - Refactor de las variables de renderizado para adoptar las claves extendidas del diccionario del agregador de BI.
* `app/templates/app/materiales.html` - Adaptación de las directivas de filtrado para interactuar con la clave lógica de la tabla maestra.
* `app/templates/app/usuarios.html` - Inyección de la estructura del modal interactivo, checkboxes de selección y scripts controladores para la actualización en vivo de especialidades.
* `app/templates/app/mantencion/completar.html` - Corrección del tag del encabezado informativo para desplegar la propiedad nominal de la categoría del ticket.
* `app/templates/app/shared/ticket_detalle.html` *(Trazabilidad)* - Reemplazo del tag analítico en la sección de información técnica del incidente.

---

### ⚙️ Configuración Requerida

> ⚠️ **¡ADVERTENCIA CRÍTICA ANTES DE EMPEZAR!**
> **Todos los tickets históricos y su información asociada (logs, validaciones, mantenciones) se eliminarán por completo**. Esto es obligatorio debido al cambio radical en la arquitectura de la base de datos. Asegúrate de estar en tu rama local de desarrollo antes de proceder.

Sigue rigurosamente este flujo de comandos secuenciales para actualizar tu entorno local tras realizar un `git pull`:

**1️⃣ Paso 1: Eliminar el archivo físico de la base de datos y migraciones viejas**
* Elimina manualmente el archivo `db.sqlite3` de la raíz del proyecto.
* Ve a la carpeta `app/migrations/` y elimina todos los archivos numerados (ej: `0001_...`). **¡No borres bajo ninguna circunstancia el archivo `__init__.py`!**

**2️⃣ Paso 2: Reconstruir la estructura relacional limpia desde cero**
Genera los nuevos planos relacionales limpios de la aplicación e impacta el motor de base de datos local para levantar las tablas desde cero:
```bash
python manage.py makemigrations
python manage.py migrate
```

**3️⃣ Paso 3: Inicializar la cuenta de gestión administrativa**
Ejecuta el comando de automatización (siguiendo las instrucciones de Jordan):
```bash
python manage.py crear_gestor
```

**4️⃣ Paso 4: Sincronizar y recuperar las cuentas de usuarios desde Auth0**
Ejecuta el comando de integración para traer automáticamente todos los usuarios registrados en el tenant de Auth0 hacia tu base de datos local:
```bash
python manage.py sincronizar_auth0
```

**5️⃣ Paso 5: Sembrar el catálogo maestro de categorías e insumos**
Rellena las nuevas tablas maestras con el catálogo unificado del pañol, especialidades relacionales y clasificaciones analíticas operativas de la Fase 2:
```bash
python manage.py poblar_sistema
```

**6️⃣ Paso 6: Sembrar la infraestructura física y ubicaciones (Edificios, Pisos y Salas)**
Es mandatorio poblar las ubicaciones institucionales para que el selector del formulario transaccional de "Crear Ticket" no aparezca vacío en el frontend. Abre la shell interna de Django y ejecuta el método de inicialización:
```bash
python manage.py shell
```
Dentro del intérprete interactivo (`>>>`), copia y pega secuencialmente las siguientes instrucciones:
```python
from app.models import Ubicacion
Ubicacion.crear_default_campus()
exit()
```

---

🚩 **Nota final:** Al terminar la secuencia de comandos, ejecuten el servidor de desarrollo de manera habitual:
```bash
python manage.py runserver
```
El sistema encenderá de forma perfecta, las categorías relacionales se verán reflejadas en todas las pantallas y las bandejas del Gestor quedarán listas para operar al 100%.