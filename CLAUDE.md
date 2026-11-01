# Cine Paradiso: venta de entradas de cine

Proyecto Integrador de Introducción al Desarrollo de Software (FIUBA, Cátedra Lanzillotta, 2C 2026), grupo 15.
Web para comprar entradas (película → función → butacas → servicios → pago simulado → email con factura y QR) y backoffice
para administrar películas (desde TMDB), locales, salas, funciones, servicios, validar QR y ver dashboards.

Todo el código, los nombres, los mensajes de error y los commits van **en español**.

## Comandos

```bash
bash init.sh                                              # .venv + dependencias + .env
bash init.sh --db                                         # crea la base y carga datos iniciales
source .venv/bin/activate
flask --app src.backend.app run --port 5000 --debug       # API (JSON)
flask --app src.frontend.app run --port 5001 --debug      # sitio + backoffice (Jinja)
python -m unittest discover -s src/tests -v               # pruebas (no requieren MySQL)
python -m unittest src.tests.test_peliculas -v            # un solo archivo
```

Admin de prueba: ver `src/backend/db/seed.sql`. Variables de entorno: `.env.example`.

## Arquitectura

Dos apps Flask separadas, ambas con `create_app()`:

- `src/backend/` API REST en JSON sobre MySQL.
  - `routes/<modulo>.py`: un blueprint por módulo. Solo HTTP: lee el request, llama al service, devuelve `jsonify(...)`.
  - `services/<funcionalidad>.py`: casos de uso y validaciones. Lanzan `ErrorApi(status, CODIGO, mensaje)`.
  - `db.py`: `consultar`, `consultar_uno`, `ejecutar`, `transaccion()`. Única forma de tocar la base.
  - `auth.py`: token firmado (`generar_token`) y decorador `@requiere_rol("admin")` / `@requiere_rol("cliente", "admin")`; deja el usuario en `g.usuario`.
  - `errores.py`: formato único `{"error": {"codigo": ..., "mensaje": ...}}`.
  - `db/schema.sql` y `db/seed.sql`: creación y carga de la base.
- `src/frontend/` sitio del cliente y backoffice con Jinja.
  - `api_client.py`: `llamar(metodo, ruta, json=, params=)` es la **única** puerta al backend; lanza `ErrorBackend`.
  - `routes/publico.py` (cliente) y `routes/backoffice.py` (`/admin`).
  - `templates/base.html`, `templates/macros.html`, `static/css/estilos.css`.
- `src/tests/` pruebas con `unittest` y `unittest.mock` (base y servicios externos simulados).
- `docs/endpoints.md` (contrato de la API) y `docs/base_de_datos.md` (modelo y reglas de negocio).

## Reglas obligatorias de la cátedra (incumplirlas desaprueba)

1. **Prohibido** que el navegador haga peticiones: nada de `fetch`, `axios`, `XMLHttpRequest`, promesas ni equivalentes.
   El frontend habla con el backend solo desde Python con `requests` (vía `api_client.llamar`). Formularios HTML + redirect.
2. **Prohibido cualquier ORM** y las clases Python que mapeen tablas. SQL explícito, siempre parametrizado (`%s`), nunca con f-strings ni concatenando datos del usuario.
3. Fecha y hora en **un único campo `DATETIME`**. En JSON, formato ISO `YYYY-MM-DDTHH:MM:SS`.
4. Endpoints con el verbo HTTP correcto, JSON de entrada y salida, y **todos con seguridad** (salvo salud, login, registro y cartelera pública).
5. Sin variables globales mutables, sin ciclos infinitos, sin código repetido: extraer helpers, macros de Jinja y funciones comunes.
6. El programa no puede romper ante la interacción del usuario: validar toda entrada y mostrar errores amigables.
7. Sitio **responsive** (mobile-first); no se usa Kivy.
8. Dependencias nuevas: agregarlas a `requirements.txt` con versión fija (las instala `init.sh`).

## Reglas de negocio clave

Detalle en `docs/base_de_datos.md` y en Confluence. Resumen:

- Una butaca no se vende dos veces en la misma función: transacción + `UNIQUE (funcion_id, butaca_id, activa)` en `entradas`.
- Compra `pendiente` por `MINUTOS_RESERVA` (10); si vence, se liberan las butacas.
- Cancelación hasta `HORAS_LIMITE_CANCELACION` (2) antes de la función; libera butacas e invalida el QR.
- QR único por compra (token firmado); al validar: misma función y fecha, no cancelado, no usado → se marca `utilizada_en`.
- Funciones de una sala no se superponen: duración de la película + 15 minutos de limpieza.
- Bajas lógicas (`activa`/`activo`) cuando hay historial.
- Película "vista" = compra con QR validado.

## Flujo de trabajo

- Ramas: `main` (entregas) ← `develop` (integración) ← `SCRUM-XXX/descripcion` (una rama por tarea, desde `develop`).
- Commits y títulos de PR: `SCRUM-XXX: descripcion` (la cátedra exige asociar cada commit a una tarea).
- PR a `develop` con revisión de otra persona. Nunca push directo a `main` ni a `develop`.
- Al agregar o cambiar un endpoint, actualizar `docs/endpoints.md` en el mismo PR.
- Backlog en Jira, proyecto `SCRUM` (sitio `tp-ids-final.atlassian.net`).

## Referencias

- Requisitos del enunciado e hitos: @docs/requisitos.md
- Alcance, hipótesis y supuestos (Confluence): https://tp-ids-final.atlassian.net/wiki/spaces/~7120200d86d4e20fe64bbfa6c0b78ff3290878/pages/2621441
- Mockups (Figma, archivo `3zp9Q3xZzZjXT6pe4ToVkQ`): https://www.figma.com/design/3zp9Q3xZzZjXT6pe4ToVkQ/Cine-Paradiso---Mockups
- Repositorio: https://github.com/LucasFiuba1/tp-integrador-ids-cinemark

Reglas por área en `.claude/rules/` (se cargan al trabajar en esos archivos) y flujos en `.claude/skills/`.
