# Requisitos del Proyecto Integrador (resumen del enunciado)

Resumen de "Proyecto integrador IDS 2026" aplicado a nuestra temática (Cine Paradiso). Sirve como checklist
antes de cada entrega. Alcance e hipótesis acordadas: [Confluence](https://tp-ids-final.atlassian.net/wiki/spaces/~7120200d86d4e20fe64bbfa6c0b78ff3290878/pages/2621441).

## Funcionalidad obligatoria

### Sitio del cliente

- [ ] Usuarios con roles **administrador** y **cliente** (registro, login, logout).
- [ ] Perfil del cliente: consumos (entradas y servicios) y películas vistas.
- [ ] Cartelera: películas en cartel con sinopsis, póster, duración, clasificación y funciones disponibles.
- [ ] Capacidad y disponibilidad de butacas de cada sala.
- [ ] Compra: película → función → butacas (ocupadas y libres) → confirmación al email.
- [ ] Compra de servicios (comida, bebidas, estacionamiento, VIP…).
- [ ] Checkout con envío de factura por email + QR de ingreso + botón cancelar.
- [ ] Una butaca no se vende dos veces en la misma función.
- [ ] Cancelación solo hasta un tiempo antes de la función.

### Backoffice (rol administrador)

- [ ] Cargar películas, imágenes y sinopsis indicando sala, capacidad, local y período de disponibilidad.
- [ ] Catálogo consumido de una API gratuita (usamos TMDB).
- [ ] ABM de servicios (disponibles para todas las salas).
- [ ] Dashboards: ocupación por función y por película, ventas por género, franjas horarias más vendidas, cancelaciones.
- [ ] Validación de QR al ingresar: corresponde a esa función y fecha, no usado ni cancelado; lo marca como usado.

### Deseables (fuera de alcance comprometido)

Reseñas solo para quienes asistieron · PDF de ventas · Docker · hosting gratuito (app y base) · Swagger.

## Requisitos técnicos obligatorios

- [ ] GitHub compartido con el corrector; **todos** los integrantes con commits útiles.
- [ ] Commits asociados a una tarea del tablero (Jira `SCRUM`), mensaje claro.
- [ ] Ramas según lo visto en la materia (`main`, `develop`, `SCRUM-XXX/descripcion`).
- [ ] Tablero Kanban con backlog de producto.
- [ ] MySQL con al menos 3 tablas y script de creación/carga.
- [ ] Fecha y hora en un único campo `DATETIME`.
- [ ] Backend Flask conectado a la base; verbos HTTP correctos; JSON.
- [ ] Frontend Flask que consume el backend respetando REST.
- [ ] **Sin** `fetch`, promesas, `axios`, `XMLHttpRequest` ni equivalentes en el navegador: solo `requests` en Python.
- [ ] **Sin** ORM ni clases que mapeen tablas: SQL explícito.
- [ ] Generación de QR y mecanismo de validación.
- [ ] Responsive (celulares y tablets).
- [ ] `init.sh` que instale las dependencias.
- [ ] Informe: carátula, integrantes, resumen, introducción, solución propuesta, tecnología utilizada, conclusión
      (decisiones de diseño y dificultades).

## Condiciones de aprobación

No: variables globales · ciclos infinitos · código repetido · programa que no funciona o con errores graves · entregar tarde.
Sí: que no rompa ante el usuario · código modularizado · buenas prácticas · funcionalidad completa.

Las dos entregas deben tener **toda** la funcionalidad (no se aceptan entregas parciales). Hora límite 18:00.
Hay defensa oral grupal **e individual**: cada integrante tiene que poder explicar cualquier parte del sistema.

## Hitos

| Hito | Fecha | Entregable |
|---|---|---|
| 1 | 26/10 | Hipótesis, alcance, backlog, mockups, esquema de tablas, listado de endpoints, repositorio |
| 2 | 02/11 | Endpoints desarrollados, tablas SQL, templates según mockups |
| 3 | 09/11 | Integración front + back; login y acceso al backoffice terminados |
| 4 | 18/11 | Primera versión funcional (pre-aprobación) |
| 5 | 25/11 | Primera entrega y defensa |
| 6 | 30/11 | Defensas y consultas |
| 7 | 02/12 | Segunda entrega y defensa (define la nota, sin recuperación) |

Temas de la cursada que se pueden aplicar: Bash, Git (ramas, PRs), Flask + blueprints, SQL y joins, Jinja,
HTML/CSS con Flexbox, Docker y Docker Compose (deseable).
