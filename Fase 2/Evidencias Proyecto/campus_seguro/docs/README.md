# Documentación del Proyecto – Campus Seguro

Esta carpeta contiene toda la documentación del proyecto. Aquí puedes encontrar rápidamente el documento que necesitas según lo que quieres hacer.

---

## Quiero hacer pruebas con el equipo

**Empieza aquí:** [MANUAL_EQUIPO.md](MANUAL_EQUIPO.md)

Este documento explica en lenguaje simple qué hace cada integrante del equipo (Jordan, Moisés, Ignacio) durante una sesión de pruebas. No requiere conocimientos técnicos.

---

## Quiero entender cómo funciona el sistema

**Por qué se usa Auth0 y qué hace:** [GUIA_AUTH0_PARA_EQUIPO.md](GUIA_AUTH0_PARA_EQUIPO.md)

Explica en términos sencillos por qué el sistema delega las contraseñas a un servicio externo, qué protección ofrece eso, y qué puede hacer el gestor desde el panel de Auth0.

**Cómo fluye una sesión de login de principio a fin:** [FLUJO_AUTENTICACION.md](FLUJO_AUTENTICACION.md)

**Cómo está estructurado el sistema completo:** [ARQUITECTURA_GENERAL.md](ARQUITECTURA_GENERAL.md)

---

## Quiero levantar el proyecto en mi computador

**Guía de instalación paso a paso:** [SETUP_NUEVO_ENTORNO.md](SETUP_NUEVO_ENTORNO.md)

Cubre desde clonar el repositorio hasta crear el gestor y levantar el servidor. Incluye los nuevos comandos de gestión del Sprint 2.

---

## Necesito configurar o revisar Auth0

**Configuración técnica de Auth0:** [AUTH0_CONFIGURACION.md](AUTH0_CONFIGURACION.md)

Pasos para configurar el tenant, URLs, permisos y variables de entorno. Versionado: incluye la configuración original (Sprint 1) y la actualización para pruebas en equipo con ngrok (Sprint 2).

---

## Quiero entender por qué el sistema funciona así

**Por qué existe la solución de pruebas compartidas:** [SOLUCION_ENTORNOS_COMPARTIDOS.md](SOLUCION_ENTORNOS_COMPARTIDOS.md)

Explica el problema técnico que se resolvió en Sprint 2 (bases de datos aisladas entre entornos), la solución elegida, y cómo se comporta el sistema cuando se eliminan usuarios o se hacen cambios en Auth0.

**Qué cambió en el sistema de registro y roles:** [CAMBIOS_REGISTRO_Y_ROLES.md](CAMBIOS_REGISTRO_Y_ROLES.md)

Documenta el cambio del Sprint 1: por qué los usuarios ya no eligen su propio rol y cómo funciona ahora el flujo de aprobación.
