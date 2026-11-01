---
paths:
  - "src/tests/**/*.py"
---

# Pruebas (unittest)

- Solo `unittest` y `unittest.mock` (sin pytest). Correr con `python -m unittest discover -s src/tests -v`.
- Un archivo por funcionalidad: `src/tests/test_<funcionalidad>.py`. Docstring con la tarea (`SCRUM-XXX`).
- Las pruebas no requieren MySQL, TMDB, SMTP ni servidores levantados:
  - Base: `patch("src.backend.services.<modulo>.consultar_uno")`, `ejecutar`, etc. (parchear donde se **usa**).
  - Autenticación: parchear `src.backend.auth.consultar_uno` y generar el token con `generar_token(1)` dentro de
    `app.app_context()` (ver `test_peliculas.py`).
  - Frontend: parchear `requests.request` o `src.frontend.routes.<modulo>.llamar`.
- Por cada endpoint cubrir: caso feliz, 401 sin token, 403 con otro rol, 400 datos inválidos (con `subTest`),
  404 inexistente y cada 409 de negocio.
- Afirmar sobre status, `["error"]["codigo"]` y el SQL ejecutado cuando importa (`assertIn("UPDATE ...", ...)`).
- Nombres en español: `test_<accion>_<condicion>_devuelve_<resultado>`.
