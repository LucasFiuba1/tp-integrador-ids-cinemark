---
paths:
  - "src/tests/**/*.py"
---

# Pruebas funcionales (pytest)

- Las pruebas nuevas se escriben como funciones de nivel superior, sin clases. Correr con `python -m pytest src/tests -v`.
- Un archivo por funcionalidad: `src/tests/test_<funcionalidad>.py`. Docstring con la tarea (`SCRUM-XXX`).
- Las pruebas no requieren MySQL, TMDB, SMTP ni servidores levantados:
- No usar `unittest.mock.patch`; preferir funciones puras o integración con servicios de prueba disponibles.
- Por cada endpoint cubrir: caso feliz, 401 sin token, 403 con otro rol, 400 datos inválidos,
  404 inexistente y cada 409 de negocio.
- Afirmar sobre status, `["error"]["codigo"]` y el SQL ejecutado cuando importa.
- Nombres en español: `test_<accion>_<condicion>_devuelve_<resultado>`.
