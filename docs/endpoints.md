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

Errores: 400 datos inválidos · 409 email ya registrado · 401 credenciales incorrectas.

El nombre debe tener hasta 100 caracteres, el email hasta 150 y la contraseña entre 8 y 128 caracteres.
La contraseña se guarda con hash `pbkdf2:sha256`; nunca se devuelve en las respuestas.

```http
GET /api/auth/me
Authorization: Bearer <token>

200 OK
{ "id": 7, "nombre": "Ana Pérez", "rol": "cliente" }
```

Errores de `/me`: 401 sin token, token inválido o vencido · 403 si el rol no está habilitado.

## Cartelera (público)

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/locales` | 🌐 | Lista de locales. |
| GET | `/api/cartelera?local_id=&fecha=` | 🌐 | Películas con funciones vigentes. |
| GET | `/api/peliculas/<id>` | 🌐 | Detalle de la película y sus funciones futuras por local. |
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

## Compras (cliente)

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| POST | `/api/compras` | 👤 | Reserva butacas de una función (compra en estado `pendiente` por 10 minutos). |
| PUT | `/api/compras/<id>/servicios` | 👤 | Define los servicios de una compra pendiente y recalcula el total. |
| POST | `/api/compras/<id>/confirmar` | 👤 | Checkout con pago simulado: confirma, genera el QR y envía el email con la factura. |
| GET | `/api/compras/<id>` | 👤 | Detalle de una compra propia (incluye el QR si está confirmada). |
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

200 OK
{ "id": 88, "estado": "confirmada", "total": 23000.00, "qr_png_base64": "iVBORw0...", "email_enviado": true }
```

Errores de cancelación: 409 `FUERA_DE_PLAZO` · 409 `YA_CANCELADA` · 409 `YA_UTILIZADA` · 403 compra de otro usuario.

## Perfil (cliente)

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/me/compras` | 👤 | Historial de compras (entradas, servicios, total, estado, si es cancelable). |
| GET | `/api/me/peliculas-vistas` | 👤 | Películas cuyo QR fue validado en el ingreso. |

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
| DELETE | `/api/admin/locales/<id>` | 🛠️ | Elimina un local sin salas. |
| GET | `/api/admin/salas?local_id=` | 🛠️ | Lista de salas. |
| POST | `/api/admin/salas` | 🛠️ | Crea una sala y genera sus butacas. |
| GET | `/api/admin/salas/<id>` | 🛠️ | Detalle de la sala con su grilla de butacas. |
| PUT | `/api/admin/salas/<id>` | 🛠️ | Modifica una sala (no si tiene funciones futuras). |
| DELETE | `/api/admin/salas/<id>` | 🛠️ | Baja lógica (no si tiene funciones futuras). |

```http
POST /api/admin/salas
{ "local_id": 1, "nombre": "Sala 3", "filas": 8, "columnas": 12 }

201 Created
{ "id": 6, "nombre": "Sala 3", "capacidad": 96 }
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

### Validación de ingreso

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| POST | `/api/admin/ingresos/validar` | 🛠️ | Valida el QR para una función y lo marca como utilizado. |

```http
POST /api/admin/ingresos/validar
{ "token_qr": "eyJjb21wcmFfaWQiOjg4fQ...", "funcion_id": 12 }

200 OK
{ "valido": true, "compra_id": 88, "butacas": ["D5", "D6"], "pelicula": "Volver al futuro" }

409 Conflict
{ "error": { "codigo": "YA_UTILIZADA", "mensaje": "Este QR ya se usó el 10/11 a las 20:21." } }
```

Motivos de rechazo: `QR_INVALIDO` · `CANCELADA` · `YA_UTILIZADA` · `OTRA_FUNCION` · `FUERA_DE_FECHA`.

### Dashboards

Todos aceptan los filtros opcionales `desde`, `hasta` y `local_id`.

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/admin/dashboards/ocupacion` | 🛠️ | Ocupación por función y por película (vendidas / capacidad). |
| GET | `/api/admin/dashboards/ventas-genero` | 🛠️ | Entradas y monto vendido por género. |
| GET | `/api/admin/dashboards/franjas-horarias` | 🛠️ | Entradas vendidas por franja horaria. |
| GET | `/api/admin/dashboards/cancelaciones` | 🛠️ | Cantidad y porcentaje de cancelaciones por película y período. |

```http
GET /api/admin/dashboards/ventas-genero?desde=2026-11-01T00:00:00

200 OK
[ { "genero": "Ciencia ficción", "entradas": 340, "monto": 1700000.00 },
  { "genero": "Drama", "entradas": 210, "monto": 1050000.00 } ]
```
