# 📄 Documentación: Módulo de Especialidades Técnicas

### 📋 Resumen
Se ha implementado y normalizado completamente el módulo de catálogo y asignación de **Especialidades Técnicas** para el personal de Mantención en el sistema **Campus Seguro**. Se eliminaron por completo las opciones estáticas escritas fijas en el código (*hardcoded*) en favor de una arquitectura relacional Muchos a Muchos (M:N) integrada en el flujo de aprobación del Gestor, el perfil del operario y los dashboards de control.

**Cambios implementados:**
* **Normalización de Base de Datos:** Eliminación del campo de texto plano `especialidad` dentro de `Usuario`. Creación del nuevo modelo maestro `Especialidad` junto con su tabla de quiebre intermedia `EspecialidadUsuario` para admitir perfiles técnicos modulares.
* **Seeding Automatizado:** Inclusión de un comando de gestión personalizado de Django (`poblar_especialidades`) para inyectar de forma segura la matriz de oficios base institucionales sin depender de configuraciones manuales.
* **Ajuste en el Flujo del Gestor:** Modificación de la vista `aprobar_cuenta()` en `app/views.py` para procesar y vincular relacionalmente la especialidad seleccionada al momento de activar perfiles operativos.
* **Interfaz Dinámica Reactiva:** Rediseño del template `revisar_cuenta.html` integrando una función en JavaScript que despliega u oculta de forma condicional el dropdown de especialidades técnicas únicamente cuando el Gestor marca el botón de radio de "Mantención", activando además su obligatoriedad a nivel de navegador.
* **Despliegue de Competencias en Perfil:** Ajuste en `perfil.html` utilizando herencia relacional (`usuario.especialidades.all`) para renderizar de manera limpia etiquetas (*badges*) con los oficios vigentes del técnico en sesión.
* **Mitigación de Errores Críticos:** Refactor integral de las plantillas de control `usuarios.html` y `operativo.html` para resolver las caídas de tipo `VariableDoesNotExist`, reestructurando semánticamente las columnas y abstrayendo iteraciones seguras para listar los oficios separados por comas.

---

### 🎯 Criterios de Aceptación
* [x] La asignación técnica se almacena de forma relacional y consistente en la base de datos a través de la tabla intermedia.
* [x] El menú desplegable en el formulario de decisión es dinámico y valida la presencia obligatoria de la especialidad sólo cuando corresponde.
* [x] El perfil del trabajador de mantención despliega sus especialidades o gestiona un mensaje de resguardo adaptativo en caso de estar vacío.
* [x] Las bandejas de administración general de cuentas y evaluación de rendimiento operativo renderizan establemente los datos M:N sin provocar interrupciones en el servidor Django.

---

### 📂 Archivos Modificados
* `app/models.py` - Nuevos modelos `Especialidad`, `EspecialidadUsuario` y desvinculación del campo estático en `Usuario`.
* `app/views.py` - Modificación del contexto e inyección de la lógica relacional `.add()` en la vista `aprobar_cuenta()`.
* `app/management/commands/poblar_especialidades.py` - Nuevo comando de inicialización y sembrado de la matriz de oficios base.
* `app/templates/app/revisar_cuenta.html` - Integración del bloque contenedor de especialidades y funciones unificadas en JavaScript.
* `app/templates/app/shared/perfil.html` - Reemplazo del campo plano por lógica iterativa de distintivos visuales por rol.
* `app/templates/app/usuarios.html` - Separación semántica de celdas para Vínculo y Especialidad, y renderizado relacional.
* `app/templates/app/operativo.html` - Modificación del bloque iterativo del equipo técnico para listar oficios de forma segura.

---

### ⚙️ Configuración Requerida

> ⚠️ **IMPORTANTE**
> Después de hacer `git pull` de esta rama, es mandatorio aplicar las nuevas migraciones para actualizar la estructura del motor SQL local y posteriormente poblar la tabla con el catálogo de oficios base. De lo contrario, las pantallas del Gestor, perfiles y listados de rendimiento fallarán al consultar los datos relacionales.

Sigue estos pasos en tu terminal local:

#### 1️⃣ Paso 1: Crear los archivos de migración basados en los nuevos modelos
Genera los archivos con los planos de diseño basados en las nuevas clases relacionales expuestas en el `models.py`:
```bash
python manage.py makemigrations
```

#### 2️⃣ Paso 2: Impactar estructuralmente la base de datos
Aplica las migraciones pendientes en el motor SQL para levantar físicamente la tabla maestra y su quiebre intermedia:
```bash
python manage.py migrate
```

#### 3️⃣ Paso 3: Ejecutar el comando personalizado para sembrar las especialidades
Ejecuta el comando en lote para inyectar automáticamente todo el catálogo de oficios base institucional en la tabla correspondiente:
```bash
python manage.py poblar_especialidades
```

🚩 *Sin este procedimiento, el motor de base de datos arrojará errores de consistencia relacional y el dropdown de asignación técnica en el panel de revisión del Gestor aparecerá completamente vacío.*