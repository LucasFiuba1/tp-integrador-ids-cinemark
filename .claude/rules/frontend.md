---
paths:
  - "src/frontend/**"
---

# Frontend (Flask + Jinja, sin JS de red)

## Regla excluyente

**Prohibido** en templates, JS o cualquier archivo estático: `fetch`, `axios`, `XMLHttpRequest`, `$.ajax`,
`new Promise`, `async/await` contra el servidor, WebSockets, `htmx` o similares. Desaprueba el TP.

Toda interacción es un `<form method="post">` (o un link `GET`) a una ruta del frontend, que llama al backend con
`api_client.llamar(...)` y responde con `render_template` o `redirect` (patrón POST/Redirect/GET).
JS solo se admite para comportamiento local sin red (por ejemplo marcar visualmente butacas elegidas);
preferir HTML/CSS puro (checkboxes estilizados para las butacas).

## Rutas

- `routes/publico.py`: cliente. `routes/backoffice.py`: admin, prefijo `/admin`.
- Toda llamada al backend dentro de `try/except ErrorBackend`: mostrar `flash(error.mensaje, "error")` y volver
  a la pantalla, nunca un 500. Si `error.status == 401`, limpiar la sesión y redirigir al login.
- La sesión de Flask guarda `token`, `rol` y `nombre` tras el login. Proteger las páginas del backoffice
  verificando `session["rol"] == "admin"` con un decorador común (no repetir el chequeo en cada vista).
- No acceder a la base desde el frontend ni importar nada de `src.backend`.

## Templates

- Todas extienden `base.html` (`{% block titulo %}`, `{% block contenido %}`). Las del backoffice extienden
  `backoffice/base_admin.html` (`{% block admin %}`), con las vistas protegidas por `@requiere_admin` y
  las macros `cabecera_pagina`, `tabla`, `badge_estado`, `tarjeta_kpi` y `barra` (ver `docs/design_system.md`).
- Reusar `macros.html` (`campo`, `boton`) y agregar macros nuevas en vez de copiar HTML
  (tarjeta de película, grilla de butacas, tabla del backoffice, resumen de compra).
- `url_for(...)` para todos los links y `action` de formularios.
- Accesibilidad: `label` en cada campo, `alt` en pósters, contraste suficiente, foco visible.

## Estilos (`static/css/tokens.css` + `static/css/estilos.css`)

- Mobile-first, layout con Flexbox/Grid, media queries hacia arriba (`48rem` tablet, `64rem` desktop, `90rem` ancho).
  Probar a 390 px y 1440 px.
- Usar solo los tokens de `tokens.css` (catálogo en `docs/design_system.md`): colores `--color-*`, fuentes
  `--fuente-titulos` (Oswald, mayúscula) y `--fuente-texto` (Roboto), tamaños `--texto-*`, espacios `--espacio-1..8`,
  radios `--radio-*`. Nada de hex ni medidas sueltas; un valor nuevo se agrega primero en `tokens.css`.
- Butacas: libre (`--color-superficie`), seleccionada (`--color-primario`), ocupada (`--color-superficie-alta`),
  distinguibles también sin color.

## Mockups (Figma `3zp9Q3xZzZjXT6pe4ToVkQ`)

Antes de construir una pantalla, mirar el frame con el MCP de Figma (`get_screenshot` / `get_design_context`
con el `nodeId`). Desktop 1440 px (D/B) y mobile 390 px (M).

| Pantalla | Desktop | Mobile |
|---|---|---|
| Componentes (botones, campos, tarjetas, cabeceras) | `23:146` | |
| Home / cartelera | `23:280` | `26:1187` |
| Detalle de película | `23:542` | `26:1382` |
| Selección de butacas | `23:684` | `26:1480` |
| Servicios | `23:904` | `26:1663` |
| Pago | `23:1047` | `26:1766` |
| Compra confirmada | `26:373` | `26:1846` |
| Ingresar | `26:652` | `26:2112` |
| Crear cuenta | `26:713` | `26:2171` |
| Mi perfil | `26:781` | `26:2237` |
| Email de confirmación (640 px) | `26:950` | |
| Backoffice: Dashboards | `29:1027` | `29:1846` |
| Backoffice: Películas | `29:1175` | |
| Backoffice: Funciones | `29:1341` | |
| Backoffice: Locales y salas | `29:1506` | |
| Backoffice: Servicios | `29:1607` | |
| Backoffice: Validar ingreso | `29:1725` | `29:1940` |

Los mockups son guía visual: traducirlos a HTML semántico + las clases y tokens existentes, sin copiar
posiciones absolutas ni estilos inline generados.
