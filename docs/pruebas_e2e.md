# Pruebas de punta a punta (SCRUM-81)

Guion manual para recorrer el sistema completo en el sitio publicado. Se ejecuta antes de cada entrega y cada
falla se registra como **Bug** en Jira (proyecto `SCRUM`) antes del 20/11.

- **Sitio:** <https://cine-paradiso-web.onrender.com/> · **API:** <https://cine-paradiso-api.onrender.com/>
- **Cuentas:** un cliente nuevo creado en el paso A1 (con un email al que se tenga acceso, para recibir la
  factura) y el admin de prueba de `src/backend/db/seed.sql`.
- **Antes de empezar:** abrir `/api/salud` y esperar `{"estado": "ok"}`. En el plan gratuito de Render los
  servicios se duermen y la primera respuesta puede tardar hasta un minuto.
- **Capturas:** `docs/e2e/<flujo><paso>.png` (por ejemplo `docs/e2e/A7.png`).

Estados: ✅ pasó · ❌ falló (con el Bug) · ⏳ pendiente.

## Última ejecución: 10/11/2026

Ejecutado con Chromium (Playwright) sobre el sitio publicado. Se recorrieron los pasos que no necesitan sesión;
los que piden iniciar sesión quedan ⏳ hasta la próxima corrida con las cuentas del equipo.

### Flujo A: compra completa, QR y película vista

| Paso | Acción | Resultado esperado | Resultado obtenido | Estado |
|---|---|---|---|---|
| A1 | `/registro`: crear una cuenta con nombre, email y contraseña. | Redirige a la cartelera con la sesión iniciada y el nombre en el header. | | ⏳ |
| A2 | Cerrar sesión e ingresar en `/ingresar` con la cuenta nueva. | Login correcto; con contraseña equivocada, mensaje claro sin perder el email escrito. | | ⏳ |
| A3 | Abrir la cartelera `/`. | Películas en cartel con póster, duración, clasificación y géneros; filtros por local y fecha. | Lista 7 películas con duración, clasificación y géneros, y filtros por local y fecha. Sin pósters: se muestra el degradado con el título (R4 en [responsive](responsive/README.md)). | ❌ R4 |
| A4 | Entrar a una película y elegir una función. | Detalle con sinopsis y funciones por local y fecha; cada función lleva a sus butacas. | `/peliculas/1` muestra el detalle y las funciones; la función lleva a `/funciones/19/butacas`. | ✅ |
| A5 | Ver el mapa de butacas. | Grilla con libres, ocupadas y seleccionadas, y la capacidad de la sala ("butacas libres N de M"). | Grilla A–H × 12 con leyenda y "Butacas libres 96 de 96". | ✅ |
| A6 | Elegir butacas y "Continuar" **sin sesión**. | Pide ingresar antes de reservar. | Redirige a `/ingresar` con "Ingresá para reservar tus butacas." | ✅ |
| A7 | Con sesión, elegir 2 butacas y "Continuar". | Reserva pendiente por 10 minutos; pasa a servicios. | | ⏳ |
| A8 | Agregar servicios (por ejemplo 1 pochoclo y 1 gaseosa). | El total suma entradas y servicios. | | ⏳ |
| A9 | Pago simulado y confirmar. | Pantalla de compra confirmada con el QR y el botón de cancelar. | | ⏳ |
| A10 | Revisar el email del cliente. | Llega la factura con el detalle, el QR (embebido y adjunto) y el enlace de cancelación. | | ⏳ |
| A11 | Admin: `/admin/ingreso`, validar el QR de la compra en su función. | "Ingreso válido"; la compra queda marcada como utilizada. | | ⏳ |
| A12 | Validar el mismo QR otra vez. | Rechazo "ya utilizado". | | ⏳ |
| A13 | Cliente: abrir `/perfil`. | La compra figura en consumos y la película en "películas vistas". | | ⏳ |

### Flujo B: cancelación desde el email

| Paso | Acción | Resultado esperado | Resultado obtenido | Estado |
|---|---|---|---|---|
| B1 | Hacer una compra confirmada para una función a más de 2 horas (pasos A7–A9). | Compra confirmada y email recibido. | | ⏳ |
| B2 | Abrir el enlace "Cancelar compra" del email. | Página de cancelación con el detalle de la compra, sin pedir login. | | ⏳ |
| B3 | Confirmar la cancelación. | Compra cancelada, email de aviso de cancelación y QR invalidado. | | ⏳ |
| B4 | Volver al mapa de butacas de la función. | Las butacas de la compra vuelven a estar libres. | | ⏳ |
| B5 | Admin: `/admin/dashboards`. | La cancelación aparece en el tablero de cancelaciones. | | ⏳ |
| B6 | Validar en la puerta el QR de la compra cancelada. | Rechazo "compra cancelada". | | ⏳ |
| B7 | Abrir `/cancelar/<token inventado>`. | Mensaje claro de enlace inválido, sin traceback. | "No pudimos abrir la compra" (HTTP 400), página amigable. | ✅ |

### Flujo C: administración

| Paso | Acción | Resultado esperado | Resultado obtenido | Estado |
|---|---|---|---|---|
| C1 | Sin sesión, abrir `/admin/`. | Redirige al login. | Redirige a `/ingresar`. | ✅ |
| C2 | Con sesión de cliente, abrir `/admin/`. | No muestra el backoffice. | | ⏳ |
| C3 | Ingresar como admin y abrir `/admin/peliculas`; buscar en TMDB e importar una película. | La película queda importada con póster, sinopsis, duración, género y clasificación. | | ⏳ |
| C4 | `/admin/locales`: crear un local y una sala (por ejemplo 6 × 8). | Sala creada con su capacidad y butacas generadas. | | ⏳ |
| C5 | `/admin/funciones`: programar la película importada en la sala nueva. | Función creada; si se superpone con otra de la misma sala (duración + 15 min), error claro. | | ⏳ |
| C6 | Como cliente, comprar entradas de esa función (A7–A9). | Compra confirmada. | | ⏳ |
| C7 | Admin: `/admin/dashboards`. | Ocupación por función y por película, ventas por género y franjas horarias reflejan la venta. | | ⏳ |

## Cómo registrar una falla

1. Crear un **Bug** en Jira (`SCRUM`) con título `[E2E <paso>] <qué pasó>`, pasos para reproducir, resultado
   esperado/obtenido y la captura.
2. Marcar el paso con ❌ y la clave del Bug en la columna Estado.
3. Cuando el Bug se cierre, volver a correr el paso y actualizar la tabla.
