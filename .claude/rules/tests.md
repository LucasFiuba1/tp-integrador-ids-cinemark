---
paths:
  - "src/tests/**/*.py"
---

# Pruebas (pytest)

- `pytest` + `unittest.mock`. Correr con `python -m pytest src/tests -v` (un archivo: `python -m pytest src/tests/test_x.py -v`).
- **Sin programación orientada a objetos** (lo exige la cátedra): cada prueba es una función `test_*` con `assert`.
  Nada de `unittest.TestCase`, `setUp`, `self` ni clases auxiliares; lo compartido va en fixtures o funciones.
- Un archivo por funcionalidad: `src/tests/test_<funcionalidad>.py`. Docstring con la tarea (`SCRUM-XXX`).
- Fixtures compartidas en `src/tests/conftest.py` (no repetir el armado de la app en cada archivo):
  - Backend: `app_backend` (con contexto), `cliente_backend`, `usuario` (parchea `src.backend.auth.consultar_uno`;
    cambiar `usuario["rol"]` para probar 403) y `cabeceras` (token válido).
  - Frontend: `app_frontend`, `cliente_frontend`, `cliente_admin` (sesión con rol admin), `backend_ok`
    (simula `requests.request`) y `renderizar` (templates/macros sueltos).
- Las pruebas no requieren MySQL, TMDB, SMTP ni servidores levantados:
  - Base: `patch("src.backend.services.<modulo>.consultar_uno")`, `ejecutar`, etc. (parchear donde se **usa**),
    idealmente en una fixture del archivo (ver `bd` en `test_peliculas.py`).
  - Frontend: parchear `requests.request` o `src.frontend.routes.<modulo>.llamar` (devuelve `(datos, error)`).
- Por cada endpoint cubrir: caso feliz, 401 sin token, 403 con otro rol, 400 datos inválidos
  (con `@pytest.mark.parametrize`), 404 inexistente y cada 409 de negocio.
- Afirmar sobre status, `["error"]["codigo"]` y el SQL ejecutado cuando importa (`assert "UPDATE ..." in sql`).
  Para llamar a un service directo, `error_api` corta con `HTTPException`: ver `afirmar_error` en `test_tmdb.py`.
- Nombres en español: `test_<accion>_<condicion>_devuelve_<resultado>`.
