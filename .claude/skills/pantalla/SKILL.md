---
name: pantalla
description: Construye una pantalla del frontend o backoffice (template Jinja + ruta Flask + CSS) a partir del mockup de Figma, consumiendo la API solo con requests. Usar al crear o modificar templates en src/frontend.
argument-hint: "<nombre de pantalla, ej. Butacas o Backoffice Películas>"
---

# Construir la pantalla: $ARGUMENTS

1. **Mockup**: buscar el `nodeId` en la tabla de `.claude/rules/frontend.md` (desktop y mobile). Con el MCP de Figma
   (archivo `3zp9Q3xZzZjXT6pe4ToVkQ`), obtener `get_screenshot` de ambos frames y `get_design_context` si hace
   falta detalle. Si el MCP no está disponible, pedir una captura.
2. **Datos**: identificar qué endpoints de `docs/endpoints.md` consume la pantalla y qué formularios envía.
   Si el endpoint no existe todavía, avisar y no inventar respuestas.
3. **Ruta** en `routes/publico.py` o `routes/backoffice.py`: `GET` que llama a `llamar(...)` y renderiza; `POST` que
   envía el formulario y redirige (PRG). Solo funciones, sin clases ni POO. `datos, error = llamar(...)`: si hay `error`, `flash(error["mensaje"], "error")` y 401 → login.
4. **Template** en `templates/` (subcarpeta por área si crece: `compra/`, `backoffice/`), extendiendo `base.html`
   y usando/creando macros en `macros.html`.
5. **CSS** mobile-first con los tokens existentes.
6. **Revisión**: grep de `fetch|axios|XMLHttpRequest|Promise|async ` en `src/frontend` → debe estar vacío.
   Si los servidores están levantados, abrir la página en el navegador a 390 px y 1440 px y compararla con el mockup.
7. Prueba en `src/tests/` que renderice la página con `llamar` simulado (caso OK y backend caído).
