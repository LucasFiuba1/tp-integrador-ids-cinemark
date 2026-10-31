# Design system

Base visual del sitio y del backoffice, tomada de los mockups de
[Figma](https://www.figma.com/design/3zp9Q3xZzZjXT6pe4ToVkQ/Cine-Paradiso---Mockups) (frame **Componentes** `23:146`).
Los valores viven como variables CSS en [`src/frontend/static/css/tokens.css`](../src/frontend/static/css/tokens.css),
que `base.html` carga antes que `estilos.css`.

**Regla:** los componentes y pantallas usan solo estos tokens (`var(--...)`). Nada de colores hex ni medidas sueltas;
si hace falta un valor nuevo, se agrega primero acá y en `tokens.css`. La prueba `src/tests/test_estilos.py` lo controla
sobre `estilos.css`.

## Colores

| Token | Valor | Uso |
|---|---|---|
| `--color-fondo` | `#14120f` | Fondo de página, header y footer. |
| `--color-panel` | `#1f1c19` | Tarjetas, paneles, resumen de compra, sidebar del backoffice. |
| `--color-superficie` | `#2b2723` | Campos, ítem activo del menú, butaca libre, pista de las barras. |
| `--color-superficie-alta` | `#3a3631` | Butaca ocupada, barras neutras de los gráficos. |
| `--color-borde` | `#3a3631` | Divisores y bordes de paneles y campos. |
| `--color-texto` | `#ffffff` | Texto principal; fondo del botón blanco. |
| `--color-texto-secundario` | `#b4aca2` | Bajadas, datos secundarios, links del footer. |
| `--color-texto-tenue` | `#a19a91` | Etiquetas de campos, placeholders, borde de butaca libre. |
| `--color-texto-invertido` | `#14120f` | Texto sobre fondos claros (botón blanco). |
| `--color-primario` | `#e0332a` | Botón rojo, butaca seleccionada, badge "Estreno", barra destacada, temporizador. |
| `--color-primario-hover` | `#c42c24` | Hover del botón rojo. |
| `--color-exito` | `#3fb27f` | Compra confirmada, variaciones positivas en dashboards. |
| `--color-error` | = primario | Bordes de campos con error, variaciones negativas. |
| `--color-error-texto` | `#ff6b61` | Mensajes de error en texto chico (contraste 6:1 sobre `--color-panel`; el primario da 3,8:1). |
| `--color-foco` | `#ffffff` | Contorno de foco visible (accesibilidad). |

Butacas: libre (`--color-superficie` con borde `--color-texto-tenue`), seleccionada (`--color-primario`),
ocupada (`--color-superficie-alta`, sin borde). Además del color, distinguirlas con un ícono o patrón y el texto de la leyenda.

## Tipografía

| Token | Valor | Uso |
|---|---|---|
| `--fuente-titulos` | Oswald | Títulos, logo, menú, botones, etiquetas. Siempre en mayúscula con `--espaciado-letras`. |
| `--fuente-texto` | Roboto | Texto corrido, datos, tablas. |
| `--texto-xs` | 12 px | Etiquetas en mayúscula, leyendas. |
| `--texto-sm` | 14 px | Menú, botones, footer, tablas. |
| `--texto-md` | 16 px | Texto base. |
| `--texto-lg` | 20 px | Título de tarjeta (`h3`). |
| `--texto-xl` | 24 px | Logo, título de sección (`h2`). |
| `--texto-2xl` | 32 px | Título de página en mobile (`h1`). |
| `--texto-3xl` | 40 px | Título de página y KPI en desktop. |

Pesos: `--peso-normal` (400), `--peso-medio` (500), `--peso-negrita` (700). Interlineado `--interlineado` (1.5) y
`--interlineado-titulos` (1.15). Las fuentes se cargan desde Google Fonts en `base.html`.

## Espaciados, bordes y layout

| Token | Valor |
|---|---|
| `--espacio-1` … `--espacio-8` | 4, 8, 12, 16, 24, 32, 48, 64 px |
| `--radio-sm` | 4 px (botones, campos, badges, butacas) |
| `--radio-md` | 8 px (tarjetas y paneles) |
| `--radio-redondo` | píldoras y avatares |
| `--borde-fino` | `1px solid var(--color-borde)` |
| `--sombra-panel` | sombra de paneles flotantes |
| `--ancho-contenido` | 1152 px (contenido central en desktop 1440) |
| `--alto-header` | 72 px |
| `--ancho-sidebar` | 256 px (backoffice) |
| `--ancho-formulario` | 416 px (tarjeta de ingresar y crear cuenta) |
| `--ancho-ticket` | 640 px (compra confirmada) |
| `--transicion` | 150 ms para hover |

## Breakpoints (mobile-first)

CSS no admite variables dentro de `@media`, así que se usan estos valores literales:

| Nombre | Media query | Referencia en Figma |
|---|---|---|
| mobile | estilos sin media query | frames M (390 px) |
| tablet | `@media (min-width: 48rem)` | 768 px |
| desktop | `@media (min-width: 64rem)` | frames D/B (1440 px) |
| ancho | `@media (min-width: 90rem)` | 1440 px en adelante |

## Componentes del backoffice

Mockups: página **Backoffice** de Figma (B1–B6 desktop, M1–M2 mobile).

Las pantallas de administración extienden `templates/backoffice/base_admin.html` y escriben en `{% block admin %}`.
El layout reemplaza el header y el footer públicos por un sidebar a toda altura (marca + etiqueta "Backoffice",
secciones de `SECCIONES` en `routes/backoffice.py` con la actual marcada con `aria-current="page"`, y abajo el usuario
con "Cerrar sesión"). En mobile es una barra con ☰ que despliega el menú con un checkbox, sin JS. Los mensajes
flash se muestran dentro del panel principal. Las vistas se protegen con `@requiere_admin`.

| Macro (`macros.html`) | Uso |
|---|---|
| `cabecera_pagina(titulo, accion=none, bajada='')` | `h1`, bajada opcional y botón blanco: `accion={"texto": "Importar de TMDB", "url": url_for(...)}`. |
| `tabla(columnas, filas, acciones={}, vacio=...)` | Tabla dentro de un `.panel`. Columnas `{"clave", "titulo", "tipo"}`: `tipo: "estado"` muestra un badge (con `"textos": {valor: leyenda}` opcional) y `"hora"` / `"fecha_hora"` formatean fechas ISO. Acciones `{"editar": endpoint, "baja": endpoint}` que reciben `id`: "Editar" es un link y "Dar de baja" un `<form method="post">` en rojo, que no se ofrece si `fila.activa` es `false`. Sin filas muestra `vacio`. En mobile cada fila se apila con la etiqueta de cada dato. |
| `badge_estado(estado, texto='')` | Palabra en mayúscula con borde: `activa` (verde), `inactiva` (gris, borde punteado), `cancelada` (rojo), `utilizada` (blanco). Se distingue por el texto, no solo por el color; `texto` cambia la leyenda (ej. "En cartelera"). |
| `tarjeta_kpi(titulo, valor, detalle='', tono='')` | Indicador de los dashboards; agrupar en `<div class="kpis">` (2 por fila en mobile, 4 en desktop). `tono` `positivo`/`negativo` colorea el detalle. |
| `barra(etiqueta, valor, maximo=100, sufijo='', destacada=false)` | Fila etiqueta / pista / valor; ancho `valor / maximo` con tope 100 %. Relleno blanco y `destacada` en `--color-primario`. |

Filtros de Jinja (`src/frontend/filtros.py`): `fecha_hora` (`2026-10-24T19:30:00` → `24/10 · 19:30`) y `hora`
(`19:30`). Si el valor no es una fecha ISO lo muestran tal cual.

Clases sueltas: `.panel` (tarjeta oscura para gráficos y formularios, con `h2`), `.accion-texto` / `.accion-peligro`
(acciones sin caja), `.avatar`, `.estado-vacio` y `.visualmente-oculto`.

## Componentes de la compra y comunes

| Macro (`macros.html`) | Uso |
|---|---|
| `pasos_compra(actual)` | Pasos Función → Butacas → Servicios → Pago; los anteriores a `actual` (1 a 4) llevan ✓ en rojo y el actual va en blanco con `aria-current="step"`. |
| `resumen_compra(compra)` | Panel lateral con póster, función, detalle de entradas y servicios, total y vencimiento de la reserva. `compra` tiene la forma de `GET /api/compras/<id>`; se usa con `{% call resumen_compra(compra) %}` y el botón de la pantalla va adentro. |
| `datos(filas, clase='')` | Lista `<dl>` etiqueta → valor en dos columnas; `filas` es una lista de tuplas. La usan validar ingreso, el resumen y el ticket. |
| `casilla(nombre, etiqueta, valor='', error='')` | Checkbox con su texto (aceptar términos), con el mismo manejo de error que `campo`. |
| `boton(..., formulario='')` | `formulario` es el `id` del `<form>` que envía el botón cuando queda fuera de él (resumen del pago). |

## Ejemplo

```css
.tarjeta {
  padding: var(--espacio-4);
  border: var(--borde-fino);
  border-radius: var(--radio-md);
  background: var(--color-panel);
}
.tarjeta h3 { font-size: var(--texto-lg); }
.tarjeta .detalle { color: var(--color-texto-secundario); font-size: var(--texto-sm); }
```
