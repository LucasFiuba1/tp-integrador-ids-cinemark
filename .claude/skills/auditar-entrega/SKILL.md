---
name: auditar-entrega
description: Audita el repo completo contra el enunciado y el hito actual (docs/requisitos.md) y genera un informe de qué falta para la entrega. Usar antes de cada hito o defensa.
argument-hint: "[número de hito]"
disable-model-invocation: true
---

# Auditoría de entrega (hito $ARGUMENTS)

Sin modificar código: solo relevar y reportar.

1. Recorrer cada checkbox de `docs/requisitos.md` y buscar evidencia en el código (archivo:línea) o marcar faltante.
2. Comparar `docs/endpoints.md` con los blueprints registrados (`flask --app src.backend.app routes`):
   endpoints documentados sin implementar y viceversa.
3. Comparar las pantallas de la tabla de Figma en `.claude/rules/frontend.md` con los templates existentes.
4. Correr los chequeos de reglas excluyentes de `/pr` y las pruebas.
5. Si el MCP de Atlassian está disponible, listar las issues abiertas de `SCRUM` (`searchJiraIssuesUsingJql`,
   `project = SCRUM AND statusCategory != Done`) y cruzarlas con lo faltante.
6. Revisar `git shortlog -sn develop` para confirmar que todos los integrantes tienen commits.
7. Entregar el informe: ✅ cumplido · ⚠️ parcial · ❌ faltante, ordenado por riesgo para aprobar,
   con la acción concreta y la tarea SCRUM sugerida para cada faltante.
