# Business Intelligence — Análisis de Dashboards

> **Sesión:** Junio 2026
> **Responsable:** Jordan García
> **Rama:** Jordan
> **Propósito del documento:** Describir en detalle cada sección del módulo BI de Campus Seguro:
> qué muestra, para qué sirve, qué problema resuelve, cómo encaja en el sistema, qué contrasta,
> qué valores aplica, y por qué es relevante para la toma de decisiones.

---

## Índice

1. [Contexto: por qué existe el BI en Campus Seguro](#1-contexto-por-qué-existe-el-bi-en-campus-seguro)
2. [Arquitectura del módulo BI](#2-arquitectura-del-módulo-bi)
3. [Sección General — visión operativa global](#3-sección-general--visión-operativa-global)
4. [Sección Guardias — desempeño de validación](#4-sección-guardias--desempeño-de-validación)
5. [Sección Mantención — rendimiento técnico](#5-sección-mantención--rendimiento-técnico)
6. [Sección Materiales — consumo e inventario](#6-sección-materiales--consumo-e-inventario)
7. [Riesgos e impacto — capa transversal](#7-riesgos-e-impacto--capa-transversal)
8. [Dashboard del gestor vs BI — cuándo usar cada uno](#8-dashboard-del-gestor-vs-bi--cuándo-usar-cada-uno)
9. [Filtros y períodos — cómo afectan las lecturas](#9-filtros-y-períodos--cómo-afectan-las-lecturas)
10. [Decisiones que habilita el BI](#10-decisiones-que-habilita-el-bi)

---

## 1. Contexto: por qué existe el BI en Campus Seguro

### El problema sin BI

Sin este módulo, el gestor solo puede ver los tickets en estado actual: quién tiene qué asignado,
cuántos están abiertos, cuántos esperan cierre. Eso responde *qué está pasando ahora*,
pero no responde:

- ¿Qué edificio genera más problemas históricamente?
- ¿El guardia está revisando los riesgos que declara el usuario?
- ¿El equipo de mantención está cerrando tickets en tiempo razonable?
- ¿Hay salas con tickets repetidos que indican un problema estructural sin resolver?
- ¿Qué materiales se consumen más? ¿Hay alguno que siempre falta?

Sin BI, esas preguntas se responden con intuición o con consultas manuales a la base de datos.

### La solución

El módulo BI agrega, cruza y presenta los datos capturados durante la operación normal del sistema.
No requiere que nadie ingrese datos adicionales — todo se genera a partir de lo que ya ocurre:
tickets creados, validaciones del guardia, sesiones de mantención, materiales consumidos.

---

## 2. Arquitectura del módulo BI

### URL y acceso

```
/gestor/bi/?seccion=general&rango=mes
```

Solo accesible para el rol `gestor`. Parámetros:

| Parámetro | Valores | Efecto |
|-----------|---------|--------|
| `seccion` | `general`, `guardias`, `mantencion`, `materiales` | Cambia qué análisis se muestra |
| `rango` | `dia`, `semana`, `mes`, `año` | Ventana temporal del análisis |
| `fecha_desde` / `fecha_hasta` | Fechas ISO | Rango personalizado (override de `rango`) |
| `trabajador` | ID del usuario | Filtra guardias o técnicos individualmente |
| `cat_material` | Código de categoría | Filtra materiales por categoría |

### Fuentes de datos por sección

```
General     → Ticket, Ubicacion, CategoriaTicket, EstadoCatalogo
Guardias    → ValidacionGuardia, Ticket, Usuario
Mantención  → RegistroMantencion, SesionTrabajo, Ticket, Usuario
Materiales  → MaterialUtilizado, Material, CategoriaMaterial, SesionTrabajo
```

---

## 3. Sección General — visión operativa global

### Qué muestra

**4 KPIs principales:**

| KPI | Fórmula | Semáforo |
|-----|---------|----------|
| Tickets en período | `COUNT(tickets en rango de fechas)` | Azul (informativo) |
| Tasa de cierre | `cerrados / total × 100` | Verde ≥70%, Amarillo ≥40%, Rojo <40% |
| Afectan clases | `COUNT(afecta_clase=True)` | Amarillo (alerta) |
| Riesgos detectados | `SUM(eléctrico + estructural + accesibilidad)` | Rojo (crítico) |

**3 gráficos de barras:**
- Por categoría: qué tipo de problema se reporta más
- Por urgencia: distribución baja / media / alta / crítica
- Por estado: en qué etapa del flujo están los tickets activos

**2 tablas:**
- Ubicaciones con reincidencia: salas o edificios con más de 1 ticket en el período
- Tickets por edificio: volumen total por edificio

**Tabla de riesgos por ubicación** *(agregada esta sesión)*:
Cuando hay tickets con riesgo activos, aparece una tabla con columnas: `#id / Edificio / Piso / Sala / Categoría / Urgencia / íconos de riesgo / Estado`. Muestra el detalle exacto de dónde está cada problema de riesgo.

### Propósito

Dar al gestor una fotografía completa del período. Es la sección que se revisa primero,
antes de entrar a cualquier análisis específico.

### Problema que resuelve

El gestor no sabe si el volumen de tickets es normal o anómalo, ni si los problemas
se concentran en un área específica. La sección general responde eso en segundos.

### Contraste que mide

- **Tasa de cierre vs tickets en período:** si hay muchos tickets pero baja tasa de cierre,
  hay un cuello de botella en mantención o en el flujo de aprobación.
- **Reincidencia por sala:** si una sala aparece 4 veces en el período, el problema no fue
  resuelto de raíz — necesita intervención preventiva, no reactiva.
- **Urgencia declarada vs volumen:** si hay muchos tickets críticos pero la tasa de cierre
  es alta, el sistema responde bien. Si es baja, hay una crisis de capacidad.

### Por qué es importante para decisiones

La reincidencia por sala es el dato más valioso para justificar inversión en mantención preventiva.
Un ticket repetido en la misma sala es evidencia de que la solución anterior fue paliativa.
Con este dato, el gestor puede escalar a la dirección del campus un requerimiento de intervención
profunda con respaldo numérico.

---

## 4. Sección Guardias — desempeño de validación

### Qué muestra

**5 KPIs de validación:**

| KPI | Qué mide |
|-----|---------|
| Total validaciones | Cuántas inspecciones en terreno hizo el guardia en el período |
| Válidas / Inválidas | Cuántas confirmaron el problema vs lo descartaron |
| Con foto | % de validaciones que adjuntaron evidencia fotográfica |
| Tiempo promedio | Minutos promedio entre asignación y validación |
| Tasa de validez | `validas / total × 100` — qué tan frecuente confirma lo reportado |

**Checklists de seguridad:**
Conteo de cuántas validaciones marcaron cada checklist: eléctrico, estructural, accesibilidad.

**Tabla por guardia** (si hay más de uno):
Ranking de guardias con columnas: nombre, total validaciones, score compuesto,
tasa de validez, % con foto, tiempo promedio.

**Score del guardia** — fórmula compuesta:
```
score = tasa_validez × 0.35
      + tasa_foto    × 0.30
      + actividad    × 0.20   (volumen relativo vs el guardia más activo)
      + checklists   × 0.15   (puntos por haber marcado riesgos de seguridad)
```
Resultado: 0–100. Verde ≥70, Amarillo ≥40, Rojo <40.

### Propósito

Medir si el guardia está haciendo bien su rol como primera línea de verificación.
La validación del guardia es el paso que transforma un reporte de usuario (que puede ser
subjetivo o impreciso) en una confirmación técnica de que el problema existe y es real.

### Problema que resuelve

Sin este análisis, el gestor no sabe si un guardia siempre valida rápido pero sin foto,
o si tiene buena tasa de validez pero ignora los checklists de seguridad.
El score unificado permite comparar guardias con criterios objetivos.

### Contraste que mide

- **Tasa de validez vs tasa con foto:** un guardia puede confirmar muchos tickets
  pero sin evidencia fotográfica — eso no es suficiente para escalar o externalizar.
- **Volumen vs tiempo promedio:** un guardia activo pero lento puede estar generando
  cuellos de botella en el flujo general.
- **Checklists de seguridad vs riesgos declarados** *(cruce implementado esta sesión)*:
  si el usuario declaró riesgo eléctrico en 10 tickets y el guardia solo marcó el
  checklist eléctrico en 4, hay un 60% de cobertura — puede indicar que el guardia
  no revisa bien los riesgos específicos declarados.

### Valores que aplican

| Umbral | Interpretación |
|--------|---------------|
| Score ≥ 70 | Guardia opera con buenas prácticas consistentes |
| Score 40–69 | Desempeño aceptable, hay áreas de mejora específicas |
| Score < 40 | Requiere atención: revisar si falta capacitación o protocolo |
| Cobertura checklist ≥ 80% | Protocolo de seguridad bien seguido |
| Cobertura checklist < 50% | Riesgo de que incidentes no sean correctamente evaluados |

### Por qué es importante para decisiones

El guardia que nunca adjunta foto ni marca checklists es un punto ciego del sistema:
si ese ticket llega a mantención con información incompleta, el técnico llega a la sala
sin saber qué tipo de riesgo enfrentará. El score permite identificar esto con datos
antes de que cause un accidente o una reparación mal ejecutada.

---

## 5. Sección Mantención — rendimiento técnico

### Qué muestra

**KPIs de cierre técnico:**

| KPI | Qué mide |
|-----|---------|
| Tickets cerrados técnicamente | Registros de mantención en el período |
| Horas hombre totales | Suma de HH declaradas en sesiones de trabajo |
| Horas hombre promedio | HH promedio por ticket cerrado |
| Tiempo promedio de resolución | Minutos estimados por ticket |
| Personal adicional requerido | Tickets que necesitaron más de un técnico |
| Requieren nivel mayor | Tickets escalados a peritaje externo |
| Con foto de cierre | % de registros con evidencia de reparación |

**Ranking por técnico:**
Tabla con nombre, total tickets, HH totales, promedio HH, % con foto, score técnico.

**Score del técnico** — fórmula compuesta:
```
score = (volumen_relativo)          × 0.25
      + (eficiencia_hh)             × 0.25   (menor HH = más eficiente)
      + (tasa_foto)                 × 0.25
      + (100 - nivel_mayor_rate)    × 0.25   (menos escalaciones = más resolutivo)
```

### Propósito

Medir la capacidad resolutiva real del equipo de mantención. No solo cuántos tickets
cierran, sino con qué calidad, en cuánto tiempo y con qué evidencia.

### Problema que resuelve

Sin este análisis, el gestor solo sabe que un técnico "cerró 8 tickets esta semana"
pero no sabe si todos tomaron 1 hora o si uno tomó 20 horas y los demás 10 minutos.
Las horas hombre revelan la complejidad real del trabajo.

### Contraste que mide

- **HH totales vs HH promedio:** un técnico con muchas HH totales pero bajo promedio
  resuelve muchos tickets simples. Uno con pocas HH totales pero alto promedio
  enfrenta problemas complejos — ambos son valiosos en roles distintos.
- **Nivel mayor vs total:** si un técnico escala el 30% de sus tickets a peritaje,
  puede necesitar capacitación específica. O puede ser que se le asignen
  los tickets más complejos por diseño.
- **% con foto:** la evidencia fotográfica del cierre es el respaldo ante reclamos
  del usuario. Un técnico que nunca adjunta foto deja al sistema sin trazabilidad.

### Valores que aplican

| Umbral | Interpretación |
|--------|---------------|
| Score ≥ 70 | Técnico consistente y con buenas prácticas |
| % nivel_mayor < 15% | Normal para técnico general |
| % nivel_mayor > 30% | Posible desajuste entre especialidad del técnico y tickets asignados |
| % con foto < 50% | Problema de trazabilidad en cierres |

### Por qué es importante para decisiones

Cuando el gestor necesita asignar un ticket urgente, el score del técnico permite elegir
al más adecuado con criterio objetivo. Además, si el equipo tiene carga desequilibrada
(un técnico con 40 HH y otro con 5), esta sección lo evidencia para redistribuir.

---

## 6. Sección Materiales — consumo e inventario

### Qué muestra

**Top materiales más consumidos:**
Ranking de materiales por cantidad utilizada en el período, con opción de filtrar por
categoría (eléctrico, plomería, pintura, etc.).

**Consumo por tipo de ticket:**
Qué categorías de ticket consumen más materiales — útil para estimar inventario
según el tipo de problema más frecuente.

**Consumo por técnico:**
Qué técnico utiliza más materiales. Permite detectar si hay diferencias significativas
entre técnicos para el mismo tipo de ticket (posible sobreconsumo o subreporte).

### Propósito

Conectar el consumo real de materiales con los tickets que los generaron.
Sin esta sección, el pañol solo sabe qué salió, pero no por qué ni para qué ticket.

### Problema que resuelve

La reposición de inventario sin datos de consumo es ciega — siempre hay exceso
de algunos materiales y falta de otros. Con el historial de consumo por categoría
de ticket, el gestor puede proyectar qué materiales necesitará el próximo período.

### Contraste que mide

- **Consumo por categoría de ticket vs frecuencia de ese ticket:**
  si "Problemas eléctricos" representa el 40% de los tickets y solo el 10%
  del consumo de materiales, hay algo que no cuadra — o los tickets eléctricos
  se cierran sin materiales (se desconecta el cable y listo), o hay subreporte.
- **Consumo por técnico para la misma categoría:**
  si dos técnicos resuelven tickets eléctricos pero uno consume el doble de materiales,
  hay una diferencia de método que vale la pena investigar.

### Por qué es importante para decisiones

Cuando llega la solicitud de presupuesto anual, el gestor puede mostrar con datos
exactos cuántas unidades de cada material se consumieron en el año, en qué tipo
de problema, y proyectar el requerimiento del próximo período con base real.

---

## 7. Riesgos e impacto — capa transversal

### Qué son los campos de riesgo

Al crear un ticket, el usuario puede marcar uno o más checkboxes de impacto:

| Campo | Significado | Implicancia operativa |
|-------|------------|----------------------|
| `afecta_clase` | El problema interrumpe actividades académicas | Prioridad alta automática sugerida |
| `riesgo_electrico` | Cables expuestos, chispas, cortocircuito | El guardia debe marcar `checklist_electrico` |
| `riesgo_estructural` | Grietas, filtraciones, techo dañado | El guardia debe marcar `checklist_estructural` |
| `riesgo_accesibilidad` | Rampa, ascensor, baño adaptado, zona de acceso | El guardia debe marcar `checklist_accesibilidad` |

### Dónde aparecen en el sistema

| Vista | Qué muestra |
|-------|-------------|
| Dashboard del gestor | 4 KPIs de riesgo (solo tickets abiertos) + tabla de riesgos por edificio |
| Dashboard del gestor | Cobertura del guardia: % de checklists marcados sobre riesgos declarados |
| BI sección general | KPI "Riesgos detectados" (total del período) + tabla detallada por ubicación |
| Detalle del ticket | Badges de riesgo visibles para todos los roles |
| Dashboard de mantención | Badges en cada ticket de la lista |
| Formulario no reparable | Se muestran los riesgos del ticket como contexto para el técnico |

### Cruce riesgo declarado vs checklist del guardia

Este es el análisis más importante de los riesgos. Mide si el protocolo de validación
se está cumpliendo correctamente:

```
cobertura_electrico = (tickets con riesgo_electrico=True
                       que tienen ValidacionGuardia con checklist_electrico=True)
                    / (total tickets con riesgo_electrico=True que tienen validación)
                    × 100
```

**Ejemplo real:**
- 10 tickets reportaron riesgo eléctrico
- 8 pasaron por validación del guardia
- Solo 5 tienen `checklist_electrico=True`
- **Cobertura: 62%** — el guardia no verificó el riesgo eléctrico en 3 de cada 8 casos

**Semáforo:**
- Verde ≥80%: el protocolo se cumple correctamente
- Amarillo ≥50%: hay inconsistencias, revisar si es criterio del guardia o falta de capacitación
- Rojo <50%: el sistema de validación de seguridad no está funcionando

### Por qué es importante para decisiones

Si hay un accidente eléctrico en una sala y el ticket tenía `riesgo_electrico=True`
pero la validación del guardia no tiene `checklist_electrico=True`, hay una falla
documentada en el protocolo de seguridad. El BI evidencia esto antes de que ocurra.

Para DuocUC en particular, `riesgo_accesibilidad` tiene implicaciones legales
bajo la normativa DDA (Ley de inclusión). Un riesgo de accesibilidad sin cobertura
de checklist es un pasivo institucional.

---

## 8. Dashboard del gestor vs BI — cuándo usar cada uno

| | Dashboard del gestor | BI |
|--|---------------------|-----|
| **Velocidad** | Carga rápida, datos en tiempo real | Más queries, para análisis reflexivo |
| **Temporal** | Estado actual (ahora mismo) | Período configurable (hoy / semana / mes / año) |
| **Acción** | Ver qué hacer ahora (sin asignar, validados, reparados) | Ver tendencias y patrones |
| **Riesgos** | Conteo de riesgos abiertos + edificio | Tabla detallada sala a sala + cobertura guardia |
| **Uso típico** | Al iniciar el día de trabajo | Al preparar un informe o tomar una decisión |
| **Decisiones** | Operativas (asignar, cerrar, escalar) | Estratégicas (capacitación, recursos, presupuesto) |

---

## 9. Filtros y períodos — cómo afectan las lecturas

### Por qué el período importa

Los mismos datos se leen diferente según el período:

- **Hoy:** útil para monitorear la operación diaria. El score de guardia con un solo
  ticket no es representativo.
- **Semana:** detecta picos puntuales (lunes tras fin de semana suele tener más reportes).
- **Mes:** período más equilibrado para evaluar rendimiento de personas.
- **Año:** para decisiones de presupuesto, contratación, o cambios de política.

### Filtro por trabajador

Cuando el gestor selecciona un guardia o técnico específico, todas las métricas
de esa sección se recalculan solo para esa persona. Útil para:
- Revisar el historial de un trabajador antes de una evaluación
- Detectar si un problema de calidad es de una persona o del equipo completo
- Preparar retroalimentación con datos concretos

### Rango personalizado

Permite comparar períodos no estándar: por ejemplo, la semana de exámenes
(donde los tickets de "afecta clases" deberían subir) vs una semana normal.

---

## 10. Decisiones que habilita el BI

### Decisiones operativas

| Pregunta | Dónde responderla | Acción resultante |
|----------|------------------|-------------------|
| ¿Hay cuellos de botella en el flujo? | General → Tasa de cierre | Reasignar técnicos o revisar SLA |
| ¿Qué sala necesita mantención preventiva? | General → Reincidencia | Programar revisión sin esperar reporte |
| ¿Todos los guardias rinden igual? | Guardias → Score por guardia | Capacitación focalizada |
| ¿Hay técnicos sobrecargados? | Mantención → HH por técnico | Redistribución de carga |
| ¿Qué materiales van a faltar? | Materiales → Top consumo | Orden de compra anticipada |

### Decisiones estratégicas

| Pregunta | Dónde responderla | Acción resultante |
|----------|------------------|-------------------|
| ¿Qué edificio necesita más inversión? | General → Tickets por edificio + Riesgos por edificio | Solicitud de presupuesto focalizada |
| ¿El protocolo de seguridad funciona? | Guardias → Cobertura de checklists | Revisar procedimientos o sanciones |
| ¿Los riesgos de accesibilidad están cubiertos? | Riesgos → Cobertura accesibilidad | Cumplimiento normativa DDA |
| ¿Cuánto costó operacionalmente este año? | Mantención → HH totales + Materiales → Consumo total | Informe de costos de mantenimiento |
| ¿Vale la pena externalizar algún tipo de problema? | Mantención → Nivel mayor + No reparables | Decisión de contrato externo |

---

*Documento generado en la sesión de Junio 2026. Responsable: Jordan García.*
