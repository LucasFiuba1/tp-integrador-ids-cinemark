# Verificación responsive (SCRUM-82)

Revisión del sitio publicado en <https://cine-paradiso-web.onrender.com/> (rama `develop` desplegada en Render)
el **10/11/2026**, con Chromium (Playwright) emulando tres anchos:

| Dispositivo | Viewport |
|---|---|
| Celular | 375 × 812 |
| Tablet | 768 × 1024 |
| Escritorio | 1280 × 800 |

En cada pantalla se midió con JavaScript:

- **Scroll horizontal**: `document.documentElement.scrollWidth > clientWidth` y elementos que se salen del
  viewport sin estar dentro de un contenedor con `overflow` (la grilla de butacas sí puede tener scroll propio).
- **Botones táctiles**: links, botones y campos visibles de menos de 32 px de alto (la guía de accesibilidad
  recomienda ~44 px).
- **Legibilidad**: textos de menos de 12 px y campos de formulario con letra menor a 16 px (Safari en iOS hace
  zoom automático al enfocarlos).

Las capturas son de página completa: `<pantalla>-<ancho>.png`.

## Resultado por pantalla

| Pantalla | Ruta | 375 | 768 | 1280 | Observaciones |
|---|---|---|---|---|---|
| Cartelera | `/` | ✅ [captura](inicio-375.png) | ✅ [captura](inicio-768.png) | ✅ [captura](inicio-1280.png) | Sin scroll horizontal. Ver R1/R3 (header) y R4 (pósters). |
| Detalle de película | `/peliculas/1` | ✅ [captura](detalle-pelicula-375.png) | ✅ [captura](detalle-pelicula-768.png) | ✅ [captura](detalle-pelicula-1280.png) | Sin scroll horizontal. |
| Butacas | `/funciones/19/butacas` | ✅ [captura](butacas-375.png) | ✅ [captura](butacas-768.png) | ✅ [captura](butacas-1280.png) | La grilla de 12 columnas entra completa en 375 px. Ver R2 (tamaño de butaca) y R1. |
| Servicios | `/servicios` | ✅ [captura](servicios-375.png) | ✅ [captura](servicios-768.png) | ✅ [captura](servicios-1280.png) | Sin scroll horizontal. |
| Ingresar | `/ingresar` | ✅ [captura](ingresar-375.png) | ✅ [captura](ingresar-768.png) | ✅ [captura](ingresar-1280.png) | Formulario usable a todo el ancho. Ver R1. |
| Registro | `/registro` | ✅ [captura](registro-375.png) | ✅ [captura](registro-768.png) | ✅ [captura](registro-1280.png) | Formulario usable a todo el ancho. Ver R1. |
| Cancelar (token inválido) | `/cancelar/token-invalido` | ✅ [captura](cancelar-token-invalido-375.png) | ✅ [captura](cancelar-token-invalido-768.png) | ✅ [captura](cancelar-token-invalido-1280.png) | Mensaje de error amigable, sin traceback. |

✅ = sin scroll horizontal de página y contenido legible.

**Pendiente (requiere sesión iniciada):** perfil, mis compras, servicios de la compra, pago, compra confirmada,
cancelación desde el perfil y todo el backoffice (`/admin/...`). Sin sesión, esas rutas redirigen a `/ingresar`
(verificado). Se completan junto con el guion de [pruebas de punta a punta](../pruebas_e2e.md) y en un celular
real (Chrome en Android y Safari en iPhone), que este relevamiento no cubre.

## Hallazgos

| # | Severidad | Hallazgo | Dónde |
|---|---|---|---|
| R1 | Media | Los selectores del header ("Elegí local" / "Elegí película") aparecen vacíos con el texto "Todavía no hay locales para elegir" en todas las pantallas que no son cartelera, detalle o servicios. `_contexto_header()` solo se pasa en esas tres rutas de `routes/publico.py`. | `/ingresar`, `/registro`, `/funciones/<id>/butacas`, perfil y compra |
| R2 | Baja | Cada butaca mide ~20 × 20 px en 375 px: se puede tocar, pero queda lejos de los 44 px recomendados y es fácil equivocarse de asiento. | `/funciones/<id>/butacas` |
| R3 | Baja | En celular los selectores del header miden 15–20 px de alto y el botón "VER" 22 px; los dos `select` usan letra menor a 16 px, por lo que Safari iOS hace zoom al tocarlos. | Header en todas las pantallas |
| R4 | Media (datos) | Ninguna película de la cartelera publicada tiene `poster_url` (la API devuelve `null`), así que se ve el degradado con el título en vez del póster que pide el enunciado. Son las películas del seed; las importadas desde TMDB sí traen póster. | `/`, `/peliculas/<id>` |
