# Entrega Hito 2 (02/11): endpoints, tablas SQL y templates

Cine Paradiso, grupo 15. Estado relevado sobre `develop` (commit `159d3e2`, 31/10/2026).

Referencias del repositorio:

- Contrato completo de la API: [`docs/endpoints.md`](endpoints.md)
- Modelo de datos y reglas de negocio: [`docs/base_de_datos.md`](base_de_datos.md)
- Scripts SQL: [`src/backend/db/schema.sql`](../src/backend/db/schema.sql) y [`src/backend/db/seed.sql`](../src/backend/db/seed.sql)
- Mockups: [Figma](https://www.figma.com/design/3zp9Q3xZzZjXT6pe4ToVkQ/Cine-Paradiso---Mockups)

Referencias de estado: ✅ desarrollado y con pruebas · 🟡 blueprint creado, endpoint especificado · ⬜ pendiente.

---

## a. Servicios / endpoints

Backend Flask (`src/backend`) con un blueprint por módulo, JSON de entrada y salida, errores con formato único
`{"error": {"codigo", "mensaje"}}` y autenticación con token firmado (`Authorization: Bearer <token>`) y decorador
`@requiere_rol(...)`.

### Infraestructura común (desarrollada)

| Componente | Archivo | Qué hace |
|---|---|---|
| App factory | `src/backend/app.py` | `create_app()`, registra blueprints y manejadores de error. |
| Acceso a datos | `src/backend/db.py` | `consultar`, `consultar_uno`, `ejecutar`, `transaccion()`; SQL parametrizado, sin ORM. |
| Seguridad | `src/backend/auth.py` | Token firmado (`generar_token`) y `@requiere_rol("admin")` / `@requiere_rol("cliente", "admin")`. |
| Errores | `src/backend/errores.py` | `ErrorApi(status, codigo, mensaje)` → JSON uniforme. |
| Cliente TMDB | `src/backend/services/tmdb.py` | Búsqueda y detalle de películas (duración, género, clasificación, póster). |

### Endpoints

| Módulo | Método | Ruta | Rol | Estado |
|---|---|---|---|---|
| Salud | GET | `/api/salud` | público | ✅ |
| Autenticación | POST | `/api/auth/registro` | público | 🟡 |
| | POST | `/api/auth/login` | público | 🟡 |
| | GET | `/api/auth/me` | cliente | 🟡 |
| Cartelera | GET | `/api/locales` | público | 🟡 |
| | GET | `/api/cartelera?local_id=&fecha=` | público | 🟡 |
| | GET | `/api/peliculas/<id>` | público | 🟡 |
| | GET | `/api/funciones/<id>` | público | 🟡 |
| | GET | `/api/funciones/<id>/butacas` | público | 🟡 |
| | GET | `/api/servicios` | público | 🟡 |
| Compras | POST | `/api/compras` | cliente | 🟡 |
| | PUT | `/api/compras/<id>/servicios` | cliente | 🟡 |
| | POST | `/api/compras/<id>/confirmar` | cliente | 🟡 |
| | GET | `/api/compras/<id>` | cliente | 🟡 |
| | POST | `/api/compras/<id>/cancelar` | cliente | 🟡 |
| | POST | `/api/compras/cancelar-por-token` | público (token firmado) | 🟡 |
| Perfil | GET | `/api/me/compras` | cliente | 🟡 |
| | GET | `/api/me/peliculas-vistas` | cliente | 🟡 |
| Películas (admin) | GET | `/api/admin/tmdb/buscar?q=` | admin | ✅ |
| | GET | `/api/admin/peliculas` | admin | ✅ |
| | POST | `/api/admin/peliculas` | admin | ✅ |
| | GET | `/api/admin/peliculas/<id>` | admin | ✅ |
| | PUT | `/api/admin/peliculas/<id>` | admin | ✅ |
| | DELETE | `/api/admin/peliculas/<id>` | admin | ✅ |
| Locales y salas (admin) | GET / POST | `/api/admin/locales` | admin | 🟡 |
| | PUT / DELETE | `/api/admin/locales/<id>` | admin | 🟡 |
| | GET / POST | `/api/admin/salas` | admin | 🟡 |
| | GET / PUT / DELETE | `/api/admin/salas/<id>` | admin | 🟡 |
| Funciones (admin) | GET / POST | `/api/admin/funciones` | admin | 🟡 |
| | PUT / DELETE | `/api/admin/funciones/<id>` | admin | 🟡 |
| Servicios (admin) | GET / POST | `/api/admin/servicios` | admin | 🟡 |
| | PUT / DELETE | `/api/admin/servicios/<id>` | admin | 🟡 |
| Ingreso (admin) | POST | `/api/admin/ingresos/validar` | admin | 🟡 |
| Dashboards (admin) | GET | `/api/admin/dashboards/ocupacion` | admin | 🟡 |
| | GET | `/api/admin/dashboards/ventas-genero` | admin | 🟡 |
| | GET | `/api/admin/dashboards/franjas-horarias` | admin | 🟡 |
| | GET | `/api/admin/dashboards/cancelaciones` | admin | 🟡 |

Total: 46 endpoints especificados (con ejemplos de request/response y códigos de error en `docs/endpoints.md`),
7 desarrollados y probados. Pruebas: `python -m unittest discover -s src/tests -v` → 25 pruebas OK.

---

## b. Tablas SQL

Base MySQL `cine_paradiso`, 10 tablas. Script re-ejecutable `schema.sql` y carga inicial `seed.sql`
(admin, 3 locales, 5 salas con sus butacas generadas y 4 servicios). Todas las fechas en un único `DATETIME`.

| Tabla | Clave / restricciones relevantes | Para qué sirve |
|---|---|---|
| `usuarios` | `email` UNIQUE, `rol` ENUM(`cliente`, `admin`) | Clientes y administradores, contraseña con hash. |
| `locales` | `nombre` UNIQUE | Los 3 centros de Cine Paradiso. |
| `salas` | FK `local_id`, UNIQUE (`local_id`, `nombre`), `activa` | Salas de cada local; capacidad = filas × columnas. |
| `butacas` | FK `sala_id`, UNIQUE (`sala_id`, `fila`, `numero`) | Asientos de cada sala. |
| `peliculas` | `tmdb_id` UNIQUE, CHECK `disponible_hasta > disponible_desde`, `activa` | Catálogo importado de TMDB con período de disponibilidad. |
| `funciones` | FK película y sala, índice (`sala_id`, `fecha_hora`), CHECK `precio > 0` | Película en una sala, en una fecha y hora. |
| `servicios` | `nombre` UNIQUE, CHECK `precio > 0`, `activo` | Comida, bebidas, estacionamiento, VIP. |
| `compras` | FK usuario y función, `estado` ENUM, `token_qr` UNIQUE | Compra de un cliente: estado, total, QR y fechas de cada etapa. |
| `entradas` | UNIQUE (`funcion_id`, `butaca_id`, `activa`), FK compuesta (`compra_id`, `funcion_id`) | Cada butaca vendida; impide la doble venta. |
| `compra_servicios` | PK (`compra_id`, `servicio_id`), CHECK `cantidad > 0` | Servicios de una compra con el precio del momento. |

Reglas de negocio resueltas en la base:

- **Doble venta:** `UNIQUE (funcion_id, butaca_id, activa)`; al cancelar o vencer, `activa = NULL` libera la butaca sin perder el historial.
- **Coherencia:** la FK compuesta impide una entrada de una función distinta a la de su compra.
- **QR de un solo uso:** `compras.token_qr` único y `compras.utilizada_en` registra el ingreso.
- **Precio histórico:** `entradas.precio` y `compra_servicios.precio_unitario`.
- **Bajas lógicas:** `salas.activa`, `peliculas.activa`, `funciones.activa`, `servicios.activo`.

Diagrama entidad-relación: ver `docs/base_de_datos.md`.

---

## c. Templates

Frontend Flask + Jinja (`src/frontend`), sin peticiones desde el navegador: todo pasa por `api_client.llamar(...)`
con `requests`. CSS mobile-first con tokens de color y tipografía tomados de los mockups.

| Mockup (Figma) | Template | Estado |
|---|---|---|
| Componentes (botones, campos) | `macros.html` (`campo`, `boton`) | ✅ parcial |
| Cabecera y pie | `base.html` | ✅ |
| Home / cartelera | `inicio.html` (portada + estado de la API) | 🟡 sin cartelera |
| Error 404 / 500 | `errores/404.html`, `errores/500.html` | ✅ |
| Detalle de película | `pelicula.html` | ⬜ |
| Selección de butacas | `compra/butacas.html` | ⬜ |
| Servicios | `compra/servicios.html` | ⬜ |
| Pago | `compra/pago.html` | ⬜ |
| Compra confirmada | `compra/confirmada.html` | ⬜ |
| Ingresar | `auth/login.html` | ⬜ |
| Crear cuenta | `auth/registro.html` | ⬜ |
| Mi perfil | `perfil.html` | ⬜ |
| Email de confirmación | `emails/confirmacion.html` | ⬜ |
| Backoffice: Dashboards | `admin/dashboards.html` | ⬜ |
| Backoffice: Películas | `admin/peliculas.html` | ⬜ |
| Backoffice: Funciones | `admin/funciones.html` | ⬜ |
| Backoffice: Locales y salas | `admin/locales.html` | ⬜ |
| Backoffice: Servicios | `admin/servicios.html` | ⬜ |
| Backoffice: Validar ingreso | `admin/validar.html` | ⬜ |
