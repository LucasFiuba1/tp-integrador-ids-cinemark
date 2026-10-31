---
name: tarea
description: Arranca una tarea de Jira SCRUM-XXX - lee el ticket, crea la rama SCRUM-XXX/descripcion desde develop y arma el plan de implementación. Usar cuando alguien dice "empecemos SCRUM-XXX" o "/tarea SCRUM-XXX".
argument-hint: SCRUM-XXX
disable-model-invocation: true
---

# Empezar la tarea $ARGUMENTS

1. **Leer el ticket** con el MCP de Atlassian (`getJiraIssue`, sitio `tp-ids-final.atlassian.net`, clave `$ARGUMENTS`):
   resumen, descripción, criterios de aceptación, subtareas y links. Si el MCP no está disponible, pedir que peguen el ticket.
2. **Contrastar** con `docs/endpoints.md`, `docs/base_de_datos.md`, `docs/requisitos.md` y las hipótesis de Confluence.
   Señalar cualquier contradicción antes de escribir código.
3. **Rama**: verificar `git status` limpio; luego
   `git fetch origin && git switch develop && git pull && git switch -c $ARGUMENTS/<descripcion-corta>`.
   Si hay cambios sin commitear, preguntar qué hacer; no descartarlos.
4. **Plan** corto: endpoints (método, ruta, rol, códigos de error), cambios de SQL, services, templates
   (con el frame de Figma de `.claude/rules/frontend.md`) y pruebas. Esperar el OK antes de implementar.
5. Al implementar, seguir `/endpoint` o `/pantalla` según corresponda, y cerrar con `/pr`.
