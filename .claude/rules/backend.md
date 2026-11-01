---
paths:
  - "src/backend/**/*.py"
---

# Backend (API REST en JSON)

Seguir el patrón de `routes/admin.py` + `services/peliculas.py`, que es la referencia del proyecto.

**Sin programación orientada a objetos** (lo exige la cátedra): solo funciones y `dict`. Nada de `class`, `self`,
herencia, `@dataclass`, `@property` ni clases de excepción propias (para errores, `error_api(...)`).

## Rutas (`routes/<modulo>.py`)

- Solo HTTP: leer `request`, llamar a un service, devolver `jsonify(...)` con el status correcto (201 al crear).
- Sin SQL ni reglas de negocio en las rutas.
- Cada endpoint lleva `@requiere_rol(...)` salvo los públicos listados en `docs/endpoints.md`
  (salud, registro, login, cartelera, cancelación por token).
- El decorador de Flask (`@bp.get`, `@bp.post`, …) va arriba y `@requiere_rol` debajo.
- Verbos: `GET` leer, `POST` crear o acciones (`/confirmar`, `/cancelar`), `PUT` modificar, `DELETE` baja.
- Cuerpo JSON: validar que sea un objeto (`cuerpo_json()` de `routes/comun.py`).
- Blueprint nuevo: registrarlo en `routes/__init__.py`.

## Services (`services/<funcionalidad>.py`)

- Un módulo por funcionalidad (`compras.py`, `funciones.py`, `salas.py`, …). Funciones con nombres de verbo en español
  (`listar`, `obtener`, `crear`, `modificar`, `dar_de_baja`, `confirmar`, `cancelar`).
- Validar tipos y rangos de toda entrada con `type(x) is int`, longitudes según `schema.sql`, etc.
- Errores con `error_api(status, "CODIGO_EN_MAYUSCULAS", "Mensaje en español para el usuario.")` (de `errores.py`;
  corta el request con `flask.abort`, no hace falta `raise`; no definir clases de excepción propias):
  400 `DATOS_INVALIDOS` · 401 · 403 `SIN_PERMISO` (también recurso de otro usuario) · 404 `NO_ENCONTRADO` ·
  409 conflicto de negocio (`BUTACA_OCUPADA`, `FUNCION_SUPERPUESTA`, `FUERA_DE_PLAZO`, `YA_UTILIZADA`, …) ·
  502 servicio externo caído. Reusar los códigos ya documentados en `docs/endpoints.md`.
- Convertir `DATETIME` a texto ISO (`.isoformat()`) y `DECIMAL` a número antes de devolver.
- Operaciones con varias sentencias (reservar butacas, confirmar, cancelar, crear sala con butacas) van dentro de
  **una** `with transaccion() as cursor:`.
- Servicios externos (TMDB, SMTP, QR) en su propio módulo (como `services/tmdb.py`), con `timeout` y
  convirtiendo fallas en `error_api(502, ...)`.
- Configuración desde `current_app.config` (cargada en `config.py` desde `.env`), nunca constantes con secretos.

## Seguridad

- Contraseñas con `werkzeug.security.generate_password_hash(password, method="pbkdf2:sha256")` / `check_password_hash`.
  No usar el método por defecto (`scrypt`): el Python de macOS no trae `hashlib.scrypt` y el login se cae.
- El usuario actual sale de `g.usuario`, nunca del cuerpo del request. Verificar que una compra sea del usuario.
- Tokens de QR y de cancelación firmados con `itsdangerous` y `SECRET_KEY` (igual que `auth.py`).
- No exponer `password_hash`, trazas ni mensajes internos en las respuestas.
