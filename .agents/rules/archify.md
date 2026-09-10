---
trigger: always_on
description: Visualiza la arquitectura, flujos de trabajo, secuencias de llamadas API y ciclo de vida del bot Dalet usando Archify.
---

## archify

Este proyecto cuenta con Archify para la generacion de diagramas interactivos y verificables (arquitectura, flujos, secuencias, dataflow y ciclos de vida).

Reglas:
- Cuando el usuario solicite diagramas interactivos o visualizacion de arquitectura de componentes, servicios, pipelines o flujos de Discord, utiliza node "C:\Users\juans\.agents\skills\archify\bin\archify.mjs" render <type> <input.json> [output.html].
- Tipos de diagramas soportados: architecture, workflow, sequence, dataflow, lifecycle.
- Almacena los diagramas generados en docs/architecture/ o en el directorio de artefactos para su visualizacion.
