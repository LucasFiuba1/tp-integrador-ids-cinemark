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

Las capturas de la tabla de arriba son del sitio publicado **antes** de los arreglos. Los arreglos se verificaron con
el frontend de esta rama corriendo en local contra la API publicada, emulando un celular táctil de 375 px:
[cartelera](inicio-375-arreglado.png), [ingresar](ingresar-375-arreglado.png) y [butacas](butacas-375-arreglado.png).

| # | Severidad | Hallazgo | Dónde | Estado |
|---|---|---|---|---|
| R1 | Media | Los selectores del header ("Elegí local" / "Elegí película") aparecían vacíos, con el texto "Todavía no hay locales para elegir", en todas las pantallas salvo cartelera, detalle y servicios: solo esas tres rutas le pasaban los datos al header. | `/ingresar`, `/registro`, `/funciones/<id>/butacas`, perfil y compra | ✅ Arreglado: un context processor de `routes/publico.py` le da al header `contexto_header()`, que el header llama solo si la vista no le pasó los selectores (la cartelera y el detalle no consultan dos veces). |
| R2 | Baja | Cada butaca medía ~20 × 20 px en 375 px: era fácil tocar la de al lado. | `/funciones/<id>/butacas` | ✅ Arreglado: mínimo de 28 px (`--ancho-butaca-minimo`). En salas anchas la grilla se desplaza de costado dentro de su panel (la página no) y arranca alineada a la izquierda (`justify-content: safe center`). |
| R3 | Baja | En celular los selectores del header medían 15–20 px de alto y el botón "VER" 22 px; los `select` usaban letra de 13 px y Safari en iOS hacía zoom al tocarlos. | Header en todas las pantallas | ✅ Arreglado en pantallas táctiles (`pointer: coarse`): selects de 44 px de alto (`--alto-tactil`) con letra de 16 px, y área táctil de 44 px en "VER" sin cambiar cómo se ve. La fila mantiene su alto. |
| R4 | Media (datos) | Ninguna película de la cartelera publicada tiene `poster_url` (la API devuelve `null`), así que se ve el degradado con el título en vez del póster. | `/`, `/peliculas/<id>` | ⏳ Ya resuelto en el código: `seed.sql` trae los pósters de TMDB desde el commit `9406fcc`. Falta cargar esos `poster_url` en la base publicada (no se tocó desde esta rama). |
