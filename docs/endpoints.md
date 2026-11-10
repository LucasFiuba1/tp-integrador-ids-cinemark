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
| 409 | Conflicto con una regla de negocio (butaca ocupada, funciones superpuestas, fuera de plazo…) |
| 500 | Error inesperado |

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
| GET | `/api/auth/me` | 👤 | Datos del usuario logueado. |

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

## Cartelera (público)

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/locales` | 🌐 | Lista de locales. |
| GET | `/api/cartelera?local_id=&fecha=` | 🌐 | Películas con funciones vigentes y su próxima función. `fecha` es `YYYY-MM-DD` y `local_id` un entero positivo (si no, 400 `DATOS_INVALIDOS`). |
| GET | `/api/peliculas/<id>` | 🌐 | Detalle de la película activa y sus funciones futuras por local (404 `NO_ENCONTRADO` si no existe o está dada de baja). |
| GET | `/api/funciones/<id>` | 🌐 | Detalle de una función (película, sala, local, fecha y hora, precio). |
| GET | `/api/funciones/<id>/butacas` | 🌐 | Mapa de butacas con su estado y capacidad. |
| GET | `/api/servicios` | 🌐 | Servicios activos para agregar a una compra. |

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
| GET | `/api/compras/<id>` | 👤 | Detalle de una compra propia (incluye el QR si está confirmada). |
| GET | `/api/compras/por-token?token=` | 🌐 | Detalle de la compra identificada por el token firmado del enlace del email (sin requerir sesión). |
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
Los errores de entrada devuelven 400 `DATOS_INVALIDOS`; una función inexistente o ya comenzada devuelve 404.

```http
PUT /api/compras/88/servicios
[ { "servicio_id": 1, "cantidad": 2 } ]

200 OK
{ "id": 88, "total": 23000.00 }
```

```http
POST /api/compras/88/confirmar
El `total` se recalcula al confirmar (entradas activas + servicios de la compra) y queda guardado en la compra.

200 OK
{ "id": 88, "estado": "confirmada", "total": 23000.00, "qr_png_base64": "iVBORw0...", "email_enviado": true }
```

Errores de confirmación: 404 `NO_ENCONTRADO` · 403 `SIN_PERMISO` (compra de otro usuario) · 409 `COMPRA_NO_PENDIENTE` · 409 `RESERVA_VENCIDA` (libera las butacas). Si el envío por SMTP falla, la compra queda confirmada igual con `"email_enviado": false`.

Errores de cancelación: 400 `TOKEN_INVALIDO` (en las rutas por token, cuando falta o la firma no es válida) · 404 `NO_ENCONTRADO` · 403 `SIN_PERMISO` (compra de otro usuario) · 409 `FUERA_DE_PLAZO` · 409 `YA_CANCELADA` · 409 `YA_UTILIZADA` · 409 `COMPRA_NO_CONFIRMADA`.

## Perfil (cliente)

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/me/compras` | 👤 | Historial de compras (entradas, servicios, total, estado, si es cancelable). |
| GET | `/api/me/peliculas-vistas` | 👤 | Películas cuyo QR fue validado en el ingreso. |

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
| GET | `/api/admin/salas?local_id=` | 🛠️ | Lista de salas. |
| POST | `/api/admin/salas` | 🛠️ | Crea una sala y genera sus butacas. |
| GET | `/api/admin/salas/<id>` | 🛠️ | Detalle de la sala con su grilla de butacas. |
| PUT | `/api/admin/salas/<id>` | 🛠️ | Modifica una sala; achicarla no se permite con funciones futuras ni con entradas vendidas en las butacas que se quitan. |
| DELETE | `/api/admin/salas/<id>` | 🛠️ | Baja lógica (no si tiene funciones futuras). |

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

Motivos de rechazo (verificados en este orden): `QR_INVALIDO` · `CANCELADA` · `YA_UTILIZADA` · `OTRA_FUNCION` · `FUERA_DE_FECHA`.

### Dashboards

Todos aceptan los filtros opcionales `desde`, `hasta` y `local_id`.

En todos, `desde` y `hasta` tienen formato
`YYYY-MM-DDTHH:MM:SS` y se aplican a la **fecha y hora de la función**, con ambos
extremos incluidos. `local_id` es un entero positivo de hasta 18 dígitos y filtra
por el local de la sala. Omitir un filtro lo deja sin restricción; enviarlo vacío o inválido, o
enviar `desde` posterior a `hasta`, devuelve 400 `DATOS_INVALIDOS`. Un local sin
compras (o inexistente) devuelve resultados vacíos, no 404. Solo se permite el
rol admin: sin token devuelve 401 y con otro rol, 403 `SIN_PERMISO`.

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/admin/dashboards/ocupacion` | 🛠️ | Ocupación por función y por película (vendidas / capacidad). |
| GET | `/api/admin/dashboards/ventas-genero` | 🛠️ | Entradas y monto vendido por género. |
| GET | `/api/admin/dashboards/franjas-horarias` | 🛠️ | Entradas vendidas por franja horaria. |
| GET | `/api/admin/dashboards/cancelaciones` | 🛠️ | Cantidad y porcentaje de cancelaciones por película y período. |

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
    { "pelicula_id": 6, "pelicula": "Toy Story", "vendidas": 1, "capacidad": 420, "ocupacion": 0.24 }
  ],
  "por_funcion": [
    { "funcion_id": 41, "pelicula": "Toy Story", "local": "Belgrano", "sala": "Sala 1",
      "fecha_hora": "2026-11-06T17:30:00", "vendidas": 1, "capacidad": 140, "ocupacion": 0.71 }
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
[ { "genero": "Animación", "entradas": 3, "monto": 16500.0 },
  { "genero": "Aventura", "entradas": 2, "monto": 11000.0 } ]
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
[ { "hora_desde": 20, "hora_hasta": 22, "entradas": 4 },
  { "hora_desde": 16, "hora_hasta": 18, "entradas": 1 } ]
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
    { "pelicula_id": 7, "pelicula": "Jurassic Park", "compras": 2, "canceladas": 1, "porcentaje": 50.0 },
    { "pelicula_id": 5, "pelicula": "El viaje de Chihiro", "compras": 1, "canceladas": 0, "porcentaje": 0.0 },
    { "pelicula_id": 6, "pelicula": "Toy Story", "compras": 1, "canceladas": 0, "porcentaje": 0.0 }
  ],
  "por_periodo": [
    { "periodo": "2026-11-06T00:00:00", "compras": 2, "canceladas": 0, "porcentaje": 0.0 },
    { "periodo": "2026-11-08T00:00:00", "compras": 2, "canceladas": 1, "porcentaje": 50.0 }
  ]
}
```

El ejemplo corresponde a `seed.sql` cargado el 7/11/2026: sus fechas son
relativas al día de carga. Sin compras devuelve
`{ "por_pelicula": [], "por_periodo": [] }`.
