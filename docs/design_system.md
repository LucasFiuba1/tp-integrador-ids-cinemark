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
| `--color-error` | = primario | Mensajes de error y variaciones negativas. |
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
| `--transicion` | 150 ms para hover |

## Breakpoints (mobile-first)

CSS no admite variables dentro de `@media`, así que se usan estos valores literales:

| Nombre | Media query | Referencia en Figma |
|---|---|---|
| mobile | estilos sin media query | frames M (390 px) |
| tablet | `@media (min-width: 48rem)` | 768 px |
| desktop | `@media (min-width: 64rem)` | frames D/B (1440 px) |
| ancho | `@media (min-width: 90rem)` | 1440 px en adelante |

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
