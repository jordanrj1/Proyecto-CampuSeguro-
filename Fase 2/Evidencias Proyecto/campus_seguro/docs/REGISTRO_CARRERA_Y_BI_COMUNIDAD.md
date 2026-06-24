# Registro: mejoras al formulario y nuevo módulo BI Comunidad

## ¿Qué se hizo en esta sesión?

Se trabajó en dos áreas principales: el formulario de registro de usuarios y el panel de Business Intelligence. El eje central fue convertir el campo `carrera` de un simple texto libre a una entidad real en la base de datos, y aprovechar eso para cruzar información en el BI.

---

## Formulario de registro (`/registro/`)

### Problema que había

El campo "Carrera" era un `CharField` libre. Cualquiera podía escribir lo que quisiera (errores, abreviaciones, datos inconsistentes). Eso hacía imposible cruzar información después.

Además, los campos académicos se mostraban o escondían de forma básica sin considerar qué tiene sentido para cada tipo de usuario.

### Qué se cambió

**Validaciones de entrada:**
- RUT: validación con algoritmo Módulo 11 correcto, acepta dígito verificador K, auto-formatea con puntos y guión
- Teléfono: solo acepta dígitos, espacios y caracteres `+`, `-`, `()`

**Lógica dinámica por vínculo:**

| Vínculo | Carrera | Jornada | Sede |
|---|---|---|---|
| Alumno | Sí (requerida) | Sí | Sí |
| Docente | Sí (opcional) | Sí | Sí |
| Administrativo | No | Sí | Sí |
| Funcionario | No | Sí | Sí |

Al cambiar el vínculo, todos los campos se resetean para que no queden datos del vínculo anterior.

**Selector de carrera en dos pasos:**
1. Primero se elige la **Escuela** (8 escuelas de Duoc San Andrés)
2. Aparece la **Carrera** filtrada para esa escuela

Esto reduce el dropdown de 28 opciones a 3-6 según la escuela seleccionada.

---

## Modelo `Carrera` (nuevo)

Se creó el modelo `Carrera` con los campos:

```
nombre   → nombre oficial de la carrera
escuela  → escuela a la que pertenece (para agrupar)
sede     → FK a Sede (null = disponible en todas)
activa   → bool para mostrar/ocultar del formulario sin borrar
```

El campo `Usuario.carrera` pasó de `CharField` a `ForeignKey(Carrera)`. Esto garantiza que los datos sean consistentes y permite filtrar/agrupar en queries sin depender de que el texto esté escrito igual.

Se sembró con las **28 carreras actuales de Duoc UC Sede San Andrés de Concepción** directamente en la migración.

### Escalabilidad vía Django Admin

Desde `/admin/` → **Carreras** se pueden agregar nuevas carreras, desactivar las que ya no se dictan, o asignarlas a nuevas sedes cuando el sistema se expanda.

---

## Templates actualizados

Los templates que usaban `{{ u.carrera }}` (string) fueron actualizados a `{{ u.carrera.nombre }}` (FK):

- `solicitudes__cuenta.html`
- `revisar_cuenta.html`

---

## BI — nueva pestaña "Comunidad"

### Por qué se agregó

Con el cambio a FK, ahora es posible cruzar los tickets con el perfil académico del solicitante. Antes eso era imposible porque el texto de la carrera no era consistente.

### Qué muestra la pestaña

**KPIs superiores**
Cantidad de usuarios registrados por vínculo (todos los tiempos).

**Tickets por vínculo del solicitante**
Quién reporta más: alumnos, docentes, administrativos o funcionarios. Útil para evaluar si el canal de reporte está llegando a toda la comunidad.

**Tickets por jornada**
Distribución entre diurna, vespertina y mixta. Si vespertina genera más tickets, puede indicar problemas con iluminación o seguridad en horario tarde.

**Tickets reportados por escuela**
Qué escuela genera más incidencias en el período. Permite priorizar mantenimiento por facultad.

**Clases afectadas por escuela**
De todos los tickets con `afecta_clase=True`, cuáles vienen de cada escuela. Este cruce es de alto valor para argumentar prioridades de mantención frente a dirección.

### Nota técnica

Los cruces de escuela solo consideran tickets cuyos solicitantes tengan vínculo `alumno` o `docente` y carrera asignada. Tickets sin esos datos no aparecen en esos bloques. El filtro de período aplica igual que en las demás pestañas.

---

## Migraciones generadas

| Migración | Qué hace |
|---|---|
| `0003_unique_asignacion_ticket` | Restricción de unicidad en asignaciones |
| `0004_carrera_model` | Crea tabla `Carrera`, siembra las 28 carreras, cambia `Usuario.carrera` a FK |
