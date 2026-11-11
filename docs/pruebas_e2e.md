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

Primero se recorrieron sin sesión, con Chromium (Playwright), los pasos que no la necesitan. Después, en el
navegador integrado, un integrante inició sesión con su cuenta de cliente y se recorrieron los flujos A y B con la
compra de prueba **#90001** (función 19, butaca A1, combo y gaseosa). El pago simulado lo completó el integrante.

Los pasos de admin quedan ⏳: la base publicada no acepta la contraseña del admin de `seed.sql` (ver E3).

### Hallazgos de esta corrida

| # | Hallazgo | Estado |
|---|---|---|
| E1 | Al confirmar la compra no llega el email con la factura y el QR: la pantalla muestra "No pudimos enviar el email a …". El plan gratuito de Render bloquea la salida SMTP (puertos 25/465/587, ver [deploy](deploy.md)). Sin email tampoco se puede probar la cancelación desde el enlace del correo. | ❌ Abierto: hay que mandar el correo por una API HTTP (por ejemplo, un proveedor con plan gratuito) o publicar en un hosting que permita SMTP. |
| E2 | La pantalla de compra confirmada no tenía botón para cancelar (el enunciado pide "checkout con … botón cancelar"); solo un texto que mandaba al email o al perfil. | ✅ Arreglado en esta rama: botón "Cancelar compra" mientras `cancelable` sea verdadero. |
| E3 | El admin de `seed.sql` no puede ingresar en la base publicada: la base se cargó con otros datos o se cambió la contraseña. | ❌ Abierto: recargar el admin del seed en la base publicada o compartir la cuenta con el equipo. |
| R4 | Las películas publicadas no tienen póster (ver [responsive](responsive/README.md)). | ❌ Abierto: falta recargar los `poster_url` del seed en la base publicada. |

### Flujo A: compra completa, QR y película vista

| Paso | Acción | Resultado esperado | Resultado obtenido | Estado |
|---|---|---|---|---|
| A1 | `/registro`: crear una cuenta con nombre, email y contraseña. | Redirige a la cartelera con la sesión iniciada y el nombre en el header. | No ejecutado: se usó una cuenta de cliente que ya existía. | ⏳ |
| A2 | Cerrar sesión e ingresar en `/ingresar` con la cuenta nueva. | Login correcto; con contraseña equivocada, mensaje claro sin perder el email escrito. | El integrante ingresó con su cuenta de cliente; el header muestra "¡Hola, Lucas!". | ✅ |
| A3 | Abrir la cartelera `/`. | Películas en cartel con póster, duración, clasificación y géneros; filtros por local y fecha. | Lista 7 películas con duración, clasificación y géneros, y filtros por local y fecha. Sin pósters: se muestra el degradado con el título (R4 en [responsive](responsive/README.md)). | ❌ R4 |
| A4 | Entrar a una película y elegir una función. | Detalle con sinopsis y funciones por local y fecha; cada función lleva a sus butacas. | `/peliculas/1` muestra el detalle y las funciones; la función lleva a `/funciones/19/butacas`. | ✅ |
| A5 | Ver el mapa de butacas. | Grilla con libres, ocupadas y seleccionadas, y la capacidad de la sala ("butacas libres N de M"). | Grilla A–H × 12 con leyenda y "Butacas libres 96 de 96". | ✅ |
| A6 | Elegir butacas y "Continuar" **sin sesión**. | Pide ingresar antes de reservar. | Redirige a `/ingresar` con "Ingresá para reservar tus butacas." | ✅ |
| A7 | Con sesión, elegir 2 butacas y "Continuar". | Reserva pendiente por 10 minutos; pasa a servicios. | Butaca A1 reservada: "Reservamos tus butacas hasta las 22:28" (10 minutos) y pasa a servicios. El header de esta pantalla seguía vacío en el sitio publicado (R1, arreglado en esta rama). | ✅ |
| A8 | Agregar servicios (por ejemplo 1 pochoclo y 1 gaseosa). | El total suma entradas y servicios. | Combo pochoclos grande × 1 ($6.500) y gaseosa × 1 ($2.500): total $14.500 = $5.500 + $6.500 + $2.500. | ✅ |
| A9 | Pago simulado y confirmar. | Pantalla de compra confirmada con el QR y el botón de cancelar. | Compra #90001 confirmada, con el QR (PNG de 360 px) y el detalle. No había botón para cancelar (E2, arreglado en esta rama). | ✅ (E2) |
| A10 | Revisar el email del cliente. | Llega la factura con el detalle, el QR (embebido y adjunto) y el enlace de cancelación. | No llega: "No pudimos enviar el email a …" (E1). | ❌ E1 |
| A11 | Admin: `/admin/ingreso`, validar el QR de la compra en su función. | "Ingreso válido"; la compra queda marcada como utilizada. | Bloqueado: sin acceso de admin (E3) y sin una función de hoy para validar. | ⏳ |
| A12 | Validar el mismo QR otra vez. | Rechazo "ya utilizado". | Bloqueado: sin acceso de admin (E3) y sin una función de hoy para validar. | ⏳ |
| A13 | Cliente: abrir `/perfil`. | La compra figura en consumos y la película en "películas vistas". | Bloqueado: sin acceso de admin (E3) y sin una función de hoy para validar. | ⏳ |

### Flujo B: cancelación desde el email

| Paso | Acción | Resultado esperado | Resultado obtenido | Estado |
|---|---|---|---|---|
| B1 | Hacer una compra confirmada para una función a más de 2 horas (pasos A7–A9). | Compra confirmada y email recibido. | Compra #90001 confirmada (A7–A9); el email no llegó (E1). | ❌ E1 |
| B2 | Abrir el enlace "Cancelar compra" del email. | Página de cancelación con el detalle de la compra, sin pedir login. | Sin email (E1). La misma página se abrió desde el perfil (`/compras/90001/cancelar`): muestra el detalle y avisa que libera la butaca A1 y anula el QR. | ❌ E1 |
| B3 | Confirmar la cancelación. | Compra cancelada, email de aviso de cancelación y QR invalidado. | "Cancelaste la compra #90001. Liberamos las butacas y el QR ya no es válido." La compra pasa a la pestaña Canceladas. No se pudo comprobar el email de aviso (E1). | ✅ |
| B4 | Volver al mapa de butacas de la función. | Las butacas de la compra vuelven a estar libres. | La función 19 vuelve a "96 de 96" butacas libres. | ✅ |
| B5 | Admin: `/admin/dashboards`. | La cancelación aparece en el tablero de cancelaciones. | Bloqueado: sin acceso de admin (E3). | ⏳ |
| B6 | Validar en la puerta el QR de la compra cancelada. | Rechazo "compra cancelada". | Bloqueado: sin acceso de admin (E3). | ⏳ |
| B7 | Abrir `/cancelar/<token inventado>`. | Mensaje claro de enlace inválido, sin traceback. | "No pudimos abrir la compra" (HTTP 400), página amigable. | ✅ |

### Flujo C: administración

| Paso | Acción | Resultado esperado | Resultado obtenido | Estado |
|---|---|---|---|---|
| C1 | Sin sesión, abrir `/admin/`. | Redirige al login. | Redirige a `/ingresar`. | ✅ |
| C2 | Con sesión de cliente, abrir `/admin/`. | No muestra el backoffice. | No se llegó a probar a mano (la sesión ya estaba cerrada). Lo cubre `test_backoffice_con_sesion_de_cliente_no_se_muestra`. | ⏳ |
| C3 | Ingresar como admin y abrir `/admin/peliculas`; buscar en TMDB e importar una película. | La película queda importada con póster, sinopsis, duración, género y clasificación. | Bloqueado: sin acceso de admin (E3). | ⏳ |
| C4 | `/admin/locales`: crear un local y una sala (por ejemplo 6 × 8). | Sala creada con su capacidad y butacas generadas. | Bloqueado: sin acceso de admin (E3). | ⏳ |
| C5 | `/admin/funciones`: programar la película importada en la sala nueva. | Función creada; si se superpone con otra de la misma sala (duración + 15 min), error claro. | Bloqueado: sin acceso de admin (E3). | ⏳ |
| C6 | Como cliente, comprar entradas de esa función (A7–A9). | Compra confirmada. | Bloqueado: sin acceso de admin (E3). | ⏳ |
| C7 | Admin: `/admin/dashboards`. | Ocupación por función y por película, ventas por género y franjas horarias reflejan la venta. | Bloqueado: sin acceso de admin (E3). | ⏳ |

## Cómo registrar una falla

1. Crear un **Bug** en Jira (`SCRUM`) con título `[E2E <paso>] <qué pasó>`, pasos para reproducir, resultado
   esperado/obtenido y la captura.
2. Marcar el paso con ❌ y la clave del Bug en la columna Estado.
3. Cuando el Bug se cierre, volver a correr el paso y actualizar la tabla.
