# Endpoints de la API

Backend Flask en `http://localhost:5000`. Todas las respuestas son JSON.

## Convenciones

- **Autenticación:** el login devuelve un token que se envía en cada request en el header `Authorization: Bearer <token>`.
- **Roles:** 🌐 público · 👤 cliente logueado · 🛠️ administrador.
- **Fechas:** formato ISO `YYYY-MM-DDTHH:MM:SS` (un solo campo fecha/hora).
- **Errores:** siempre con el mismo formato:

```json
{ "error": { "codigo": "BUTACA_OCUPADA", "mensaje": "La butaca F7 ya fue vendida para esta función." } }
```

| Código HTTP | Cuándo |
|---|---|
| 200 / 201 | OK / recurso creado |
| 400 | Datos inválidos o faltantes |
| 401 | Sin token o token inválido/vencido |
| 403 | El rol no tiene permiso o el recurso es de otro usuario |
| 404 | Recurso inexistente |
| 405 | Verbo HTTP no permitido para esa ruta |
| 409 | Conflicto con una regla de negocio (butaca ocupada, funciones superpuestas, fuera de plazo…) |
| 500 | Error inesperado |
| 502 | TMDB no disponible (falta `TMDB_API_KEY`, error de red o respuesta de error del proveedor) |

Códigos genéricos que puede devolver cualquier endpoint (los arma `src/backend/errores.py`):
| HTTP | Código | Cuándo |
|---|---|---|
| 400 | `DATOS_INVALIDOS` | Cuerpo o parámetros inválidos. |
| 401 | `NO_AUTENTICADO` | Falta el header `Authorization: Bearer <token>` en un endpoint protegido. |
| 401 | `TOKEN_INVALIDO` | El token tiene una firma inválida o venció. |
| 403 | `SIN_PERMISO` | El rol no alcanza o el recurso es de otro usuario. |
| 404 | `NO_ENCONTRADO` | Ruta o recurso inexistente. |
| 405 | `METODO_NO_PERMITIDO` | La ruta existe pero no con ese verbo. |
| 500 | `ERROR_INTERNO` | Error inesperado (el detalle queda en el log, no en la respuesta). |

### Filtros de los listados

Los query params de los listados (`local_id`, `fecha`, `desde`, `hasta`, `funcion_id`) se validan con un helper
común (`src/backend/filtros.py`, SCRUM-106). Cada listado acepta solo sus filtros: un parámetro desconocido se
ignora y un valor inválido devuelve 400 `DATOS_INVALIDOS`. Los ids son enteros positivos de hasta 18 dígitos,
`fecha` es `YYYY-MM-DD` (el día completo) y `desde`/`hasta` son `YYYY-MM-DDTHH:MM:SS` con ambos extremos
incluidos (`desde` posterior a `hasta` → 400).

Un parámetro **vacío** (`?local_id=`) se trata según el listado:

| Listado | Vacío |
|---|---|
| `GET /api/cartelera`, dashboards, `GET /api/admin/ingresos` | 400 `DATOS_INVALIDOS` |
| `GET /api/admin/funciones`, `GET /api/admin/salas` | Se ignora (sin filtro): es lo que mandan los formularios al elegir "Todos" |

---

## Salud

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/salud` | 🌐 | Verifica que la API esté levantada. |

## Autenticación

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| POST | `/api/auth/registro` | 🌐 | Registra un cliente nuevo. |
| POST | `/api/auth/login` | 🌐 | Inicia sesión y devuelve el token. |
| POST | `/api/auth/recuperar` | 🌐 | Olvidé mi contraseña: envía por email el enlace para restablecerla. |
| GET | `/api/auth/restablecer?token=` | 🌐 | Indica si el enlace de recuperación sigue vigente. |
| POST | `/api/auth/restablecer` | 🌐 | Cambia la contraseña con el token del enlace. |
| GET | `/api/auth/me` | 👤 🛠️ | Datos del usuario logueado. |

```http
POST /api/auth/registro
{ "nombre": "Ana Pérez", "email": "ana@mail.com", "password": "secreta123" }

201 Created
{ "id": 7, "nombre": "Ana Pérez", "email": "ana@mail.com", "rol": "cliente" }
```

```http
POST /api/auth/login
{ "email": "ana@mail.com", "password": "secreta123" }

200 OK
{ "token": "eyJ1c2VyX2lkIjo3fQ...", "rol": "cliente", "nombre": "Ana Pérez" }
```

Reglas: el email se guarda en minúsculas y sin espacios; la contraseña (8 a 128 caracteres) se guarda con hash
`pbkdf2:sha256`. Todo registro nuevo es rol `cliente` (los admin se cargan desde `seed.sql`; un `rol` en el cuerpo
se ignora).

Errores: 400 `DATOS_INVALIDOS` (campo faltante, email sin formato válido, nombre de más de 100 caracteres,
contraseña fuera de rango) · 409 `EMAIL_REGISTRADO` · 401 `CREDENCIALES_INVALIDAS` (mismo mensaje si falla el
email o la contraseña).

El nombre debe tener hasta 100 caracteres, el email hasta 150 y la contraseña entre 8 y 128 caracteres.
La contraseña se guarda con hash `pbkdf2:sha256`; nunca se devuelve en las respuestas.

```http
GET /api/auth/me
Authorization: Bearer <token>

200 OK
{ "id": 7, "nombre": "Ana Pérez", "email": "ana@email.com", "rol": "cliente" }
```

Errores de `/me`: 401 sin token, token inválido o vencido · 403 si el rol no está habilitado.

### Recuperación de contraseña

```http
POST /api/auth/recuperar
{ "email": "ana@mail.com" }

200 OK
{ "mensaje": "Si el email corresponde a una cuenta, te enviamos un enlace para restablecer la contraseña." }
```

Si el email es de una cuenta, se envía por Mailjet (igual que la factura) un email con el enlace
`FRONTEND_URL/restablecer/<token>`. La respuesta es **la misma** exista o no la cuenta y aunque el email no salga,
para no revelar qué emails están registrados. Errores: 400 `DATOS_INVALIDOS` (email sin formato válido).

```http
GET /api/auth/restablecer?token=<token>
200 OK
{ "valido": true }

POST /api/auth/restablecer
{ "token": "<token>", "password": "nueva-clave-456" }

200 OK
{ "mensaje": "Listo, ya podés ingresar con tu nueva contraseña." }
```

El token va firmado con `SECRET_KEY` (salt propio: no sirve como token de sesión, QR ni cancelación), **vence a la
hora** y lleva una huella del hash actual de la contraseña: al cambiarla deja de valer, así que cada enlace sirve
una sola vez sin guardar nada en la base. Son públicos como el login porque quien olvidó la contraseña no tiene
sesión; la seguridad la da el token que solo llega a la casilla del usuario.
Errores: 400 `TOKEN_INVALIDO` (falta, alterado, vencido, ya usado o de un usuario inexistente) ·
400 `DATOS_INVALIDOS` (contraseña fuera de 8 a 128 caracteres).

## Cartelera (público)

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/locales` | 🌐 | Locales con al menos una sala activa (`id` y `nombre`, ordenados por nombre), para los filtros de la cartelera y el header. |
| GET | `/api/catalogos/generos` | 🌐 | Géneros usados por películas con funciones vigentes, sin repetidos y ordenados alfabéticamente. |
| GET | `/api/catalogos/clasificaciones` | 🌐 | Clasificaciones usadas por películas con funciones vigentes, sin repetidos y ordenadas alfabéticamente. |
| GET | `/api/cartelera?local_id=&fecha=` | 🌐 | Películas con funciones vigentes y su próxima función. `fecha` es `YYYY-MM-DD` y `local_id` un entero positivo (si no, 400 `DATOS_INVALIDOS`). |
| GET | `/api/peliculas/<id>` | 🌐 | Detalle de la película activa y sus funciones futuras, cada una con `local_id` y `nombre_local` (404 `NO_ENCONTRADO` si no existe o está dada de baja). |
| GET | `/api/funciones/<id>` | 🌐 | Detalle de una función (película, sala, local, fecha y hora, precio). |
| GET | `/api/funciones/<id>/butacas` | 🌐 | Mapa de butacas con su estado y capacidad. |
| GET | `/api/servicios` | 🌐 | Servicios activos para agregar a una compra. |

```http
GET /api/locales

200 OK
[
  { "id": 2, "nombre": "Paradiso Belgrano" },
  { "id": 1, "nombre": "Paradiso Centro" },
  { "id": 3, "nombre": "Paradiso Palermo" }
]
```

```http
GET /api/cartelera?local_id=1

200 OK
[
  {
    "id": 3, "titulo": "Volver al futuro", "poster_url": "https://image.tmdb.org/...",
    "duracion_min": 116, "clasificacion": "ATP", "genero": "Ciencia ficción",
    "proxima_funcion": "2026-11-10T20:30:00"
  }
]
```

```http
GET /api/funciones/12/butacas

200 OK
{
  "funcion_id": 12, "sala": "Sala 1", "capacidad": 96, "libres": 81, "vendible": true,
  "butacas": [
    { "id": 1, "fila": "A", "numero": 1, "estado": "libre" },
    { "id": 2, "fila": "A", "numero": 2, "estado": "ocupada" }
  ]
}
```

Una butaca está `ocupada` si tiene una entrada vigente de una compra `confirmada` o `pendiente` sin vencer;
las de compras canceladas o vencidas cuentan como libres. No expone datos de los compradores.
`vendible` es `false` si la función ya empezó. Función inexistente o dada de baja → 404 `NO_ENCONTRADO`.

```http
GET /api/servicios

200 OK
[ { "id": 1, "nombre": "Combo pochoclos grande", "descripcion": "Pochoclos grandes y gaseosa de 500 ml", "precio": 6500.0, "activo": true } ]
```

Solo devuelve los servicios activos (los dados de baja no aparecen), ordenados por nombre.

## Compras (cliente)

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| POST | `/api/compras` | 👤 | Reserva butacas de una función (compra en estado `pendiente` por 10 minutos). |
| PUT | `/api/compras/<id>/servicios` | 👤 | Define los servicios de una compra pendiente y recalcula el total. |
| POST | `/api/compras/<id>/confirmar` | 👤 | Checkout con pago simulado: confirma, genera el QR y envía el email con la factura. |
| GET | `/api/compras/<id>` | 👤 🛠️ | Detalle de una compra propia (el admin puede ver cualquiera); incluye el QR si está confirmada. |
| GET | `/api/compras/por-token?token=` | 🌐 | Detalle de la compra identificada por el token firmado del enlace del email (sin requerir sesión). |
| GET | `/api/compras/por-qr?token=` | 🌐 | Entrada identificada por el token firmado del QR: datos básicos para cualquiera; compra completa para el comprador y el admin. |
| POST | `/api/compras/<id>/cancelar` | 👤 | Cancela una compra propia dentro del plazo permitido. |
| POST | `/api/compras/cancelar-por-token` | 🌐 | Cancela desde el enlace del email (el token firmado identifica la compra). |

```http
POST /api/compras
{ "funcion_id": 12, "butaca_ids": [41, 42] }

201 Created
{ "id": 88, "estado": "pendiente", "vence_en": "2026-11-05T18:40:00", "subtotal_entradas": 10000.00 }

409 Conflict
{ "error": { "codigo": "BUTACA_OCUPADA", "mensaje": "Las butacas D5, D6 ya fueron vendidas." } }
```

La función debe estar activa y no haber comenzado; las butacas deben ser únicas y pertenecer a su sala.

**Volver a elegir butacas:** si el cliente ya tiene una compra `pendiente` de esa misma función (volvió atrás desde
servicios), la reserva nueva la **reemplaza**: la anterior pasa a `vencida` (no `cancelada`, así no cuenta como
cancelación en los dashboards) y libera sus butacas, que el cliente puede volver a elegir. La nueva **hereda el
`vence_en` de la anterior**, para que cambiar de butacas no extienda la reserva. Las reservas de otros clientes y
las del mismo cliente para otras funciones no se tocan.
Los errores de entrada devuelven 400 `DATOS_INVALIDOS`; una función inexistente o ya comenzada devuelve 404.

```http
PUT /api/compras/88/servicios
[ { "servicio_id": 1, "cantidad": 2 } ]

200 OK
{ "id": 88, "total": 23000.00 }
```

**Reemplaza** todos los servicios de la compra por los de la lista (SCRUM-64). La lista vacía `[]` es válida:
quita los servicios ("Continuar sin servicios"). Cada servicio guarda su **precio vigente en ese momento** en
`compra_servicios.precio_unitario`, así un cambio posterior de precio no altera la compra. `total` es la suma de
las entradas activas y los servicios, y queda guardado en la compra.

Errores: 400 `DATOS_INVALIDOS` (el cuerpo no es una lista; más de 50 elementos; `servicio_id` que no es un entero
positivo o repetido; `cantidad` fuera de 1 a 20; servicio inexistente o inactivo) · 404 `NO_ENCONTRADO` ·
403 `SIN_PERMISO` (compra de otro usuario) · 409 `COMPRA_NO_PENDIENTE` · 409 `RESERVA_VENCIDA` (libera las butacas).

En `GET /api/compras/<id>`, cada servicio trae `servicio_id`, `nombre`, `cantidad`, `precio_unitario` y
`subtotal`: con `servicio_id` el paso de servicios precarga lo que el cliente ya eligió.

```http
POST /api/compras/88/confirmar
El `total` se recalcula al confirmar (entradas activas + servicios de la compra) y queda guardado en la compra.

200 OK
{ "id": 88, "estado": "confirmada", "total": 23000.00, "qr_png_base64": "iVBORw0...", "email_enviado": true }
```

`qr_png_base64` es el QR de ingreso: codifica `<FRONTEND_URL>/entrada?token=<token_qr>` (el mismo `token_qr` que valida `POST /api/admin/ingresos/validar`). Al escanearlo con la cámara del celular se abre la página de la entrada (`GET /api/compras/por-qr`): cualquiera ve los datos básicos, el comprador ve su compra completa y el admin, además, puede validar el ingreso.

```http
GET /api/compras/88

200 OK
{
  "id": 88, "estado": "confirmada", "pelicula": "Volver al futuro", "poster_url": "https://image.tmdb.org/...",
  "local": "Paradiso Centro", "sala": "Sala 1", "funcion_id": 12, "funcion": "2026-11-12T20:30:00",
  "butacas": ["D5", "D6"], "butaca_ids": [41, 42],
  "subtotal_entradas": 10000.00,
  "servicios": [ { "nombre": "Combo pochoclos grande", "cantidad": 2, "precio_unitario": 6500.00, "subtotal": 13000.00 } ],
  "total": 23000.00, "email": "ana@email.com", "vence_en": null, "utilizada_en": null, "cancelada_en": null,
  "cancelable": true, "cancelable_hasta": "2026-11-12T18:30:00", "qr_png_base64": "iVBORw0..."
}
```

`estado` es `pendiente`, `confirmada`, `cancelada` o `vencida`; una `pendiente` cuyo `vence_en` ya pasó se informa como `vencida` aunque la base todavía no se haya actualizado. `vence_en` solo tiene valor en las pendientes en plazo y `qr_png_base64` solo en las confirmadas. `cancelable` y `cancelable_hasta` se calculan igual que en el perfil. Errores: 404 `NO_ENCONTRADO` · 403 `SIN_PERMISO` (un cliente pidiendo una compra ajena). `GET /api/compras/por-token` devuelve el mismo detalle.

```http
GET /api/compras/por-qr?token=eyJjb21wcmFfaWQiOjg4fQ.firma

200 OK   (sin sesión, o un cliente que no hizo la compra)
{
  "vista": "publica", "estado": "valida", "pelicula": "Volver al futuro", "poster_url": "https://image.tmdb.org/...",
  "local": "Paradiso Centro", "sala": "Sala 1", "funcion": "2026-11-12T20:30:00", "butacas": ["F7", "F8"]
}

200 OK   (Authorization del cliente que hizo la compra)
{
  "vista": "comprador", "estado": "valida", "pelicula": "Volver al futuro", "...": "mismos datos básicos",
  "id": 88, "cantidad_entradas": 2, "servicios": [{"servicio_id": 3, "nombre": "Pochoclo grande", "cantidad": 1,
  "precio_unitario": 5000.0, "subtotal": 5000.0}], "total": 23000.0, "estado_pago": "pagado",
  "utilizada_en": null, "cancelada_en": null
}
```

Pública a propósito, como las rutas por token del email: la protege la firma del token del QR (un token de
cancelación no sirve acá ni al revés). El `Authorization` es **opcional**: si viene un token de sesión válido, el
backend decide qué devolver; si falta o no sirve, responde la vista pública (nunca 401).

| `vista` | Quién | Qué agrega |
|---|---|---|
| `publica` | Sin sesión, o un cliente que **no** hizo la compra | Solo película, local, sala, función, butacas y estado. Sin datos personales ni de pago. |
| `comprador` | El cliente que hizo la compra | N.º de operación (`id`), `cantidad_entradas`, servicios, `total`, `estado_pago` (`pagado`, `anulado`, `pendiente`), `utilizada_en` y `cancelada_en`. |
| `admin` | Administrador | Lo mismo que el comprador más `titular` (nombre completo). Valida con `POST /api/admin/ingresos/validar`. |

`estado` es `valida`, `utilizada`, `cancelada`, `vencida` (la función ya terminó: inicio + duración de la película)
o `pendiente` (compra sin pagar). La firma alcanza para informar también una compra cancelada, que ya no tiene
`token_qr`. Ninguna vista devuelve el email, el QR ni los datos para cancelar. Errores: 400 `TOKEN_INVALIDO`
(falta o la firma no es válida) · 404 `NO_ENCONTRADO`.

Errores de confirmación: 404 `NO_ENCONTRADO` · 403 `SIN_PERMISO` (compra de otro usuario) · 409 `COMPRA_NO_PENDIENTE` · 409 `RESERVA_VENCIDA` (libera las butacas). Si el envío por la API HTTPS de Mailjet falla o falta su configuración, la compra queda confirmada igual con `"email_enviado": false`. Un valor `true` indica aceptación del proveedor, no entrega en la casilla. La factura incluye un único QR embebido por Content-ID y el enlace firmado de cancelación, sin copia adjunta del QR.

Al cancelar desde el perfil o por token, se intenta enviar el aviso al dueño de la compra **después del commit**. No incluye QR. Un fallo al preparar el aviso o enviarlo no revierte la cancelación, la liberación de butacas ni la invalidación del QR. La respuesta conserva `{"id": 88, "estado": "cancelada"}`; no informa el resultado del correo. Una cancelación rechazada no envía avisos.

Errores de cancelación: 400 `TOKEN_INVALIDO` (en las rutas por token, cuando falta o la firma no es válida) · 404 `NO_ENCONTRADO` · 403 `SIN_PERMISO` (compra de otro usuario) · 409 `FUERA_DE_PLAZO` · 409 `YA_CANCELADA` · 409 `YA_UTILIZADA` · 409 `COMPRA_NO_CONFIRMADA`.

## Perfil (cliente)

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/me/compras` | 👤 🛠️ | Historial de compras (entradas, servicios, total, estado, si es cancelable). |
| GET | `/api/me/peliculas-vistas` | 👤 🛠️ | Películas cuyo QR fue validado en el ingreso. |

El usuario sale del token: no hay parámetros. El historial incluye compras `confirmada` y `cancelada`, más las `pendiente` que todavía no vencieron (para poder pagarlas desde el perfil); las `vencida` nunca se pagaron y no aparecen. `vence_en` solo tiene valor en las pendientes. `token_qr` es `null` si la compra no está confirmada. `cancelable_hasta` es la fecha de la función menos `HORAS_LIMITE_CANCELACION`, y `cancelable` es `true` solo si la compra está confirmada, sin usar y todavía no pasó ese límite.

```http
GET /api/me/compras

200 OK
[
  {
    "id": 88, "estado": "confirmada", "total": 23000.0,
    "creada_en": "2026-11-05T18:30:00", "vence_en": null, "confirmada_en": "2026-11-05T18:33:10",
    "cancelada_en": null, "utilizada_en": null,
    "funcion": {
      "id": 12, "fecha_hora": "2026-11-10T20:30:00", "pelicula_id": 3, "pelicula": "Volver al futuro",
      "poster_url": "https://image.tmdb.org/...", "sala": "Sala 1", "local": "Paradiso Centro"
    },
    "butacas": ["D5", "D6"],
    "servicios": [ { "nombre": "Combo pochoclos grande", "cantidad": 2, "precio_unitario": 6500.0 } ],
    "token_qr": "eyJjb21wcmFfaWQiOjg4fQ...",
    "cancelable": true, "cancelable_hasta": "2026-11-10T18:30:00"
  }
]
```

```http
GET /api/me/peliculas-vistas

200 OK
[
  {
    "pelicula_id": 3, "titulo": "Volver al futuro", "poster_url": "https://image.tmdb.org/...",
    "genero": "Ciencia ficción", "duracion_min": 116, "clasificacion": "ATP", "fecha_hora": "2026-11-10T20:30:00",
    "sala": "Sala 1", "local": "Paradiso Centro", "utilizada_en": "2026-11-10T20:21:00"
  }
]
```

Errores: 401 sin token o token vencido. Un usuario sin compras recibe `[]`.

## Backoffice (administrador)

### Películas

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/admin/tmdb/buscar?q=` | 🛠️ | Busca películas en TMDB. |
| GET | `/api/admin/peliculas` | 🛠️ | Lista de películas cargadas. |
| POST | `/api/admin/peliculas` | 🛠️ | Importa una película de TMDB con su período de disponibilidad. |
| GET | `/api/admin/peliculas/<id>` | 🛠️ | Detalle de una película. |
| PATCH | `/api/admin/peliculas/<id>` | 🛠️ | Actualiza los campos enviados; los no enviados quedan sin cambios. |
| DELETE | `/api/admin/peliculas/<id>` | 🛠️ | Baja (lógica si tiene funciones). |

```http
POST /api/admin/peliculas
{ "tmdb_id": 105, "disponible_desde": "2026-11-01T00:00:00", "disponible_hasta": "2026-12-15T23:59:59" }

201 Created
{ "id": 3, "titulo": "Volver al futuro", "duracion_min": 116, "genero": "Ciencia ficción" }
```

Errores de TMDB e importación: 502 `TMDB_NO_DISPONIBLE` (falta `TMDB_API_KEY`, no se pudo consultar TMDB o devolvió
un error) · 404 `TMDB_NO_ENCONTRADA` (el `tmdb_id` no existe en TMDB) · 409 `PELICULA_DUPLICADA` (ya fue importada) ·
409 `PELICULA_INCOMPLETA` (TMDB no tiene duración o género). Todos los endpoints de esta sección devuelven 401
`NO_AUTENTICADO` sin token y 403 `SIN_PERMISO` si el rol no es admin.

```http
PATCH /api/admin/peliculas/3
{ "disponible_hasta": "2027-01-31T00:00:00" }

200 OK
{ "id": 3, "titulo": "Volver al futuro", "disponible_hasta": "2027-01-31T00:00:00" }
```

### Locales y salas

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/admin/locales` | 🛠️ | Lista de locales. |
| POST | `/api/admin/locales` | 🛠️ | Crea un local. |
| PUT | `/api/admin/locales/<id>` | 🛠️ | Modifica un local. |
| DELETE | `/api/admin/locales/<id>` | 🛠️ | Elimina un local sin salas activas ni funciones (409 `LOCAL_CON_SALAS` / `LOCAL_CON_HISTORIAL`). |
| GET | `/api/admin/salas?local_id=` | 🛠️ | Lista de salas activas, opcionalmente de un local (`local_id` inválido → 400). |
| POST | `/api/admin/salas` | 🛠️ | Crea una sala y genera sus butacas. |
| GET | `/api/admin/salas/<id>` | 🛠️ | Detalle de la sala con su grilla de butacas. |
| PUT | `/api/admin/salas/<id>` | 🛠️ | Modifica una sala; achicarla no se permite con funciones futuras ni con entradas vendidas en las butacas que se quitan. |
| DELETE | `/api/admin/salas/<id>` | 🛠️ | Baja lógica (no si tiene funciones futuras). |

Errores: 400 `DATOS_INVALIDOS` · 404 `NO_ENCONTRADO` · 409 `LOCAL_DUPLICADO` (mismo nombre o dirección) ·
409 `LOCAL_CON_SALAS` / `LOCAL_CON_HISTORIAL` (`DELETE` de un local) · 409 `SALA_DUPLICADA` (mismo nombre en el
local) · 409 `SALA_CON_FUNCIONES` (reducir o dar de baja una sala con funciones futuras) · 409
`BUTACAS_CON_ENTRADAS` (achicar una sala que tiene entradas vendidas en las butacas que se quitarían).

```http
POST /api/admin/salas
{ "local_id": 1, "nombre": "Sala 3", "filas": 8, "columnas": 12 }

201 Created
{ "id": 6, "nombre": "Sala 3", "capacidad": 96 }
```

```http
GET /api/admin/salas/6

200 OK
{ "id": 6, "local_id": 1, "local": "Paradiso Centro", "nombre": "Sala 3", "filas": 8, "columnas": 12,
  "capacidad": 96, "butacas": [{ "id": 301, "fila": "A", "numero": 1 }, ...] }
```

### Funciones

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/admin/funciones?local_id=&desde=&hasta=` | 🛠️ | Lista de funciones. |
| POST | `/api/admin/funciones` | 🛠️ | Programa una función (valida superposición y período). |
| PUT | `/api/admin/funciones/<id>` | 🛠️ | Modifica una función sin entradas vendidas. |
| DELETE | `/api/admin/funciones/<id>` | 🛠️ | Da de baja una función sin entradas vendidas. |

Errores: 400 `DATOS_INVALIDOS` · 404 `NO_ENCONTRADO` · 409 `FUNCION_SUPERPUESTA` (la sala ya tiene otra función en ese
horario) · 409 `FUNCION_CON_ENTRADAS` (`PUT` que cambia sala u horario, o `DELETE`, con entradas registradas).

```http
POST /api/admin/funciones
{ "pelicula_id": 3, "sala_id": 1, "fecha_hora": "2026-11-10T20:30:00", "precio": 5000 }

409 Conflict
{ "error": { "codigo": "FUNCION_SUPERPUESTA", "mensaje": "La Sala 1 ya tiene una función de 19:00 a 21:10." } }
```

### Servicios

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/admin/servicios` | 🛠️ | Lista de servicios (activos e inactivos). |
| POST | `/api/admin/servicios` | 🛠️ | Crea un servicio. |
| PUT | `/api/admin/servicios/<id>` | 🛠️ | Modifica un servicio. |
| DELETE | `/api/admin/servicios/<id>` | 🛠️ | Baja lógica. |
| POST | `/api/admin/servicios/<id>/reactivar` | 🛠️ | Reactiva un servicio dado de baja (`activo = true`). |

```http
POST /api/admin/servicios
{ "nombre": "Combo pochoclos grande", "descripcion": "Pochoclos grandes y gaseosa de 500 ml", "precio": 6500 }

201 Created
{ "id": 1, "nombre": "Combo pochoclos grande", "descripcion": "Pochoclos grandes y gaseosa de 500 ml",
  "precio": 6500.0, "activo": true }
```

```http
GET /api/admin/servicios

200 OK
[
  { "id": 4, "nombre": "Acceso VIP", "descripcion": "Butaca reclinable y servicio en sala", "precio": 8000.0, "activo": false },
  { "id": 1, "nombre": "Combo pochoclos grande", "descripcion": "Pochoclos grandes y gaseosa de 500 ml", "precio": 6500.0, "activo": true }
]
```

```http
PUT /api/admin/servicios/1
{ "nombre": "Combo pochoclos grande", "descripcion": null, "precio": 7000.5 }

200 OK
{ "id": 1, "nombre": "Combo pochoclos grande", "descripcion": null, "precio": 7000.5, "activo": true }
```

```http
DELETE /api/admin/servicios/1

204 No Content
```

```http
POST /api/admin/servicios/1/reactivar

204 No Content
```

Reactivar un servicio que ya está activo no cambia nada y también devuelve 204; si el servicio no existe, 404 `NO_ENCONTRADO`.

```http
POST /api/admin/servicios
{ "nombre": "Gaseosa", "precio": 2500 }

409 Conflict
{ "error": { "codigo": "SERVICIO_DUPLICADO", "mensaje": "Ya existe un servicio con ese nombre." } }
```

Reglas: `nombre` es obligatorio (texto no vacío de hasta 100 caracteres; los espacios de los extremos se recortan, no
se rechazan) y único sin distinguir mayúsculas (collation `utf8mb4_unicode_ci`: `"gaseosa"` choca con `"Gaseosa"` → 409).
`descripcion` es opcional (hasta 255 caracteres; si falta, es `null` o queda vacía se guarda `null`). `precio` es un
número mayor a 0 con hasta dos decimales y menor a 100.000.000 (no se aceptan textos ni `true`/`false`); se devuelve
como número (`6500.0`). El `PUT` reemplaza nombre, descripción y precio, y no cambia `activo`. La baja es lógica
(`activo = false`): el servicio deja de aparecer en `GET /api/servicios`, pero sigue en el listado del admin y las
compras que ya lo incluían no cambian. El `DELETE` es idempotente: responde 204 también si el servicio ya estaba inactivo.

Errores: 400 `DATOS_INVALIDOS` (cuerpo que no es objeto, nombre vacío o largo, descripción inválida, precio inválido)
· 401 sin token · 403 `SIN_PERMISO` si no es admin · 404 `NO_ENCONTRADO` (`PUT`/`DELETE` de un servicio
inexistente) · 409 `SERVICIO_DUPLICADO` (nombre repetido, también al modificar).

### Validación de ingreso

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/admin/ingresos?funcion_id=&limite=` | 🛠️ | Últimos intentos de validación registrados (`limite` entre 1 y 100, por defecto 20; ordenado por fecha descendente). |
| POST | `/api/admin/ingresos/validar` | 🛠️ | Valida el QR para una función, registra el intento y lo marca como utilizado si es válido. |

```http
GET /api/admin/ingresos?funcion_id=12&limite=20

200 OK
[
  {
    "id": 5, "compra_id": 88, "funcion_id": 12, "hora": "2026-11-10T20:21:00",
    "pelicula": "Volver al futuro", "butacas": "D5, D6", "resultado": "valida"
  }
]
```

```http
POST /api/admin/ingresos/validar
{ "token_qr": "eyJjb21wcmFfaWQiOjg4fQ...", "funcion_id": 12 }

200 OK
{
  "valido": true, "compra_id": 88, "butacas": ["D5", "D6"], "pelicula": "Volver al futuro",
  "funcion": "2026-11-10T20:30:00", "local": "Paradiso Centro", "sala": "Sala 1", "titular": "Ana Pérez"
}

409 Conflict
{ "error": { "codigo": "YA_UTILIZADA", "mensaje": "Este QR ya se usó el 10/11 a las 20:21." } }
```

Motivos de rechazo (verificados en este orden): `QR_INVALIDO` (firma inválida o compra inexistente) · `CANCELADA` (aunque al cancelar se borre el token guardado) · `QR_INVALIDO` (el token no es el vigente de la compra) · `YA_UTILIZADA` · `OTRA_FUNCION` · `FUERA_DE_FECHA`.

### Dashboards

Todos aceptan los filtros opcionales `desde`, `hasta` y `local_id`.

En todos, `desde` y `hasta` tienen formato
`YYYY-MM-DDTHH:MM:SS` y se aplican a la **fecha y hora de la función**, con ambos
extremos incluidos. `local_id` es un entero positivo de hasta 18 dígitos y filtra
por el local de la sala. Omitir un filtro lo deja sin restricción; enviarlo vacío o inválido, o
enviar `desde` posterior a `hasta`, devuelve 400 `DATOS_INVALIDOS`. Un local sin
compras (o inexistente) devuelve resultados vacíos, no 404. Solo se permite el
rol admin: sin token devuelve 401 y con otro rol, 403 `SIN_PERMISO`.

**Formato común de las series (SCRUM-109).** Cada fila de cada lista, además de sus
campos propios, trae `etiqueta` (texto), `valor` (entero) y `porcentaje` (número con
dos decimales), para que el backoffice dibuje todas las barras con la misma macro:

| Serie | `etiqueta` | `valor` | `porcentaje` |
|---|---|---|---|
| Ocupación `por_pelicula` | título | `vendidas` | `vendidas / capacidad` (igual a `ocupacion`) |
| Ocupación `por_funcion` | `"<película> (<local>, <sala>)"` | `vendidas` | `vendidas / capacidad` (igual a `ocupacion`) |
| Ventas por género | género | `entradas` | participación sobre el total de entradas de la respuesta |
| Franjas horarias | `"20 a 22 h"` | `entradas` | participación sobre el total de entradas de la respuesta |
| Cancelaciones `por_pelicula` / `por_periodo` | título / `periodo` | `canceladas` | `canceladas / compras` |

Los porcentajes se calculan como `100 * parte / total`, redondeados a dos decimales
(la mitad hacia arriba) y, si el total es 0, valen `0.0` en lugar de fallar.

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/admin/dashboards/resumen` | 🛠️ | Indicadores del período y variación contra el período anterior. |
| GET | `/api/admin/dashboards/ocupacion` | 🛠️ | Ocupación por función y por película (vendidas / capacidad). |
| GET | `/api/admin/dashboards/ventas-genero` | 🛠️ | Entradas y monto vendido por género. |
| GET | `/api/admin/dashboards/franjas-horarias` | 🛠️ | Entradas vendidas por franja horaria. |
| GET | `/api/admin/dashboards/cancelaciones` | 🛠️ | Cantidad y porcentaje de cancelaciones por película y período. |

#### Resumen de indicadores (SCRUM-124)

Devuelve los cuatro indicadores de las tarjetas. Cada uno trae `valor` (período
elegido), `anterior` (período anterior) y `variacion`.

| Indicador | `valor` | `variacion` |
|---|---|---|
| `entradas` | Entradas activas de compras confirmadas | % |
| `ingresos` | Suma de `compras.total` de compras confirmadas (entradas y servicios) | % |
| `ocupacion` | `100 * vendidas / capacidad` de todas las funciones activas del período | Puntos |
| `cancelaciones` | `100 * canceladas / (confirmadas + canceladas)` | Puntos |

El **período anterior** dura lo mismo que el elegido y termina un segundo antes
de `desde`: `desde=2026-11-03T00:00:00` y `hasta=2026-11-09T23:59:59` se comparan
con 2026-10-27T00:00:00 a 2026-11-02T23:59:59. Los filtros se aplican igual en
los dos períodos, también `local_id`.

`ingresos` incluye servicios, por eso puede superar la suma de `monto` de
`ventas-genero`, que cuenta solo entradas.

Sin ventas, `entradas` e `ingresos` valen 0. Sin funciones, `ocupacion` es `null`;
sin compras confirmadas ni canceladas, `cancelaciones` es `null`. `variacion` es
`null` si no hay con qué comparar: falta `desde` o `hasta`, el indicador es `null`
en alguno de los dos períodos, o el período anterior vale 0 en una variación
porcentual. Si falta `desde` o `hasta`, `anterior` también es `null`.

```http
GET /api/admin/dashboards/resumen?desde=2026-11-03T00:00:00&hasta=2026-11-09T23:59:59

200 OK
{
  "entradas": { "valor": 5, "anterior": 3, "variacion": 66.67 },
  "ingresos": { "valor": 39000.0, "anterior": 16500.0, "variacion": 136.36 },
  "ocupacion": { "valor": 0.42, "anterior": 0.3, "variacion": 0.12 },
  "cancelaciones": { "valor": 25.0, "anterior": 50.0, "variacion": -25.0 }
}
```

#### Ocupación (SCRUM-75)

Devuelve dos agrupaciones: `por_pelicula` y `por_funcion`. `vendidas` cuenta las
**entradas activas de compras confirmadas**; `capacidad` es `filas * columnas` de
la sala (en `por_pelicula`, la suma de todas sus funciones); `ocupacion` es
`100 * vendidas / capacidad`, redondeado a dos decimales y enviado como número.

Las funciones **sin ventas también aparecen** y suman capacidad. Las funciones
dadas de baja no se cuentan porque no se ofrecieron; sí se conservan las de
películas y salas dadas de baja. Ambas listas se ordenan por `ocupacion`
descendente; a igual ocupación, por `pelicula_id` en `por_pelicula` y
cronológicamente en `por_funcion`.

```http
GET /api/admin/dashboards/ocupacion?local_id=2

200 OK
{
  "por_pelicula": [
    { "pelicula_id": 6, "pelicula": "Toy Story", "vendidas": 1, "capacidad": 420, "ocupacion": 0.24,
      "etiqueta": "Toy Story", "valor": 1, "porcentaje": 0.24 }
  ],
  "por_funcion": [
    { "funcion_id": 41, "pelicula": "Toy Story", "local": "Belgrano", "sala": "Sala 1",
      "fecha_hora": "2026-11-06T17:30:00", "vendidas": 1, "capacidad": 140, "ocupacion": 0.71,
      "etiqueta": "Toy Story (Belgrano, Sala 1)", "valor": 1, "porcentaje": 0.71 }
  ]
}
```

Sin funciones en el período devuelve `{ "por_pelicula": [], "por_funcion": [] }`.

#### Ventas por género (SCRUM-75)

Cuenta **entradas activas de compras confirmadas**. Como `peliculas.genero` puede
tener varios géneros separados por coma, cada venta se asigna al **primero**: así
la suma de las filas coincide con el total vendido. `monto` suma el precio de las
entradas, sin servicios. Solo aparecen géneros con ventas, ordenados por
`entradas` descendente y luego por `genero`.

```http
GET /api/admin/dashboards/ventas-genero

200 OK
[ { "genero": "Animación", "entradas": 3, "monto": 16500.0, "etiqueta": "Animación", "valor": 3, "porcentaje": 60.0 },
  { "genero": "Aventura", "entradas": 2, "monto": 11000.0, "etiqueta": "Aventura", "valor": 2, "porcentaje": 40.0 } ]
```

Estos son los valores de `seed.sql` recién cargado. Sin ventas devuelve `[]`.

#### Franjas horarias (SCRUM-76)

Bloques de dos horas según `HOUR(funciones.fecha_hora)`: `[00:00, 02:00)`,
`[02:00, 04:00)`, …, `[22:00, 24:00)`. Se cuentan **entradas activas de compras
confirmadas**, no compras ni servicios. Solo aparecen franjas con ventas,
ordenadas por `entradas` descendente y, en caso de empate, por `hora_desde`
ascendente. `hora_hasta` puede valer 24 y representa el final del día. No se
excluye el historial por bajas lógicas de películas, salas o funciones.

```http
GET /api/admin/dashboards/franjas-horarias

200 OK
[ { "hora_desde": 20, "hora_hasta": 22, "entradas": 4, "etiqueta": "20 a 22 h", "valor": 4, "porcentaje": 80.0 },
  { "hora_desde": 16, "hora_hasta": 18, "entradas": 1, "etiqueta": "16 a 18 h", "valor": 1, "porcentaje": 20.0 } ]
```

Estos son los valores de `seed.sql` recién cargado. Sin ventas devuelve `[]`.

#### Cancelaciones (SCRUM-76)

Devuelve dos agrupaciones: `por_pelicula` y `por_periodo`. La unidad es la
**compra**, independientemente de cuántas entradas o servicios tenga.
`compras` cuenta compras en estado `confirmada` o `cancelada`; `canceladas`
cuenta las de estado `cancelada`; `porcentaje` es
`100 * canceladas / compras`, redondeado a dos decimales y enviado como número.
Las pendientes y vencidas no forman parte del denominador. Se conserva el
historial de entidades con baja lógica.

El período es el **día de la función**, no el día de creación o cancelación de
la compra, y se representa como ISO a medianoche (`YYYY-MM-DDT00:00:00`). Solo
aparecen películas y días con compras contabilizadas, incluso si tienen cero
cancelaciones. Las películas se ordenan por `canceladas` descendente y luego
por `pelicula_id`; los períodos, cronológicamente.

```http
GET /api/admin/dashboards/cancelaciones

200 OK
{
  "por_pelicula": [
    { "pelicula_id": 7, "pelicula": "Jurassic Park", "compras": 2, "canceladas": 1,
      "etiqueta": "Jurassic Park", "valor": 1, "porcentaje": 50.0 },
    { "pelicula_id": 5, "pelicula": "El viaje de Chihiro", "compras": 1, "canceladas": 0,
      "etiqueta": "El viaje de Chihiro", "valor": 0, "porcentaje": 0.0 },
    { "pelicula_id": 6, "pelicula": "Toy Story", "compras": 1, "canceladas": 0,
      "etiqueta": "Toy Story", "valor": 0, "porcentaje": 0.0 }
  ],
  "por_periodo": [
    { "periodo": "2026-11-06T00:00:00", "compras": 2, "canceladas": 0,
      "etiqueta": "2026-11-06T00:00:00", "valor": 0, "porcentaje": 0.0 },
    { "periodo": "2026-11-08T00:00:00", "compras": 2, "canceladas": 1,
      "etiqueta": "2026-11-08T00:00:00", "valor": 1, "porcentaje": 50.0 }
  ]
}
```

El ejemplo corresponde a `seed.sql` cargado el 7/11/2026: sus fechas son
relativas al día de carga. Sin compras devuelve
`{ "por_pelicula": [], "por_periodo": [] }`.
