# Cine Paradiso: venta de entradas de cine

Proyecto Integrador de Introducción al Desarrollo de Software (Cátedra Lanzillotta, 2.º cuatrimestre 2026), grupo 15.

Aplicación web para comprar entradas de cine (película → función → butacas → servicios → pago → QR por email) y backoffice para administrar la cartelera, las salas y ver estadísticas.

## Estructura

```
src/
  backend/          API REST en Flask (JSON) que se conecta a MySQL
    app.py          create_app(): configuración, manejo de errores y blueprints
    config.py       lectura de variables de entorno
    auth.py         token firmado y decorador @requiere_rol
    abm.py          helpers comunes de los ABM (bajas lógicas, duplicados)
    filtros.py      validación de los filtros de los listados
    tokens.py       tokens firmados del QR y del enlace de cancelación
    db/
      schema.sql    creación de tablas y relaciones
      seed.sql      datos iniciales
    db.py           acceso a MySQL con SQL explícito (sin ORM)
    errores.py      formato único de errores JSON
    routes/         un blueprint por módulo (auth, cartelera, compras, admin, dashboards)
    services/       casos de uso y validaciones por funcionalidad (compras, cartelera, funciones, ingresos,
                    dashboards, correo, qr, tmdb...)
    templates/email/ plantillas del correo de factura y de cancelación
  frontend/         sitio del cliente y backoffice en Flask + Jinja
    app.py          create_app()
    api_client.py   única puerta al backend, usando requests
    routes/         blueprints: público y backoffice
    templates/      base.html, macros y páginas
    static/css/     estilos responsive
  tests/              pruebas automatizadas con pytest
docs/
  entorno.md        variables, claves, MySQL y configuración local
  requisitos.md     resumen del enunciado y checklist de entrega
  informe.md        informe del proyecto (versión PDF: informe.pdf)
  design_system.md  tokens, componentes y macros del sitio
  pruebas_e2e.md    recorridos de prueba de extremo a extremo
  deploy.md         publicación gratuita de las dos apps y la base
  endpoints.md      listado de endpoints con ejemplos
  base_de_datos.md  diagrama entidad-relación y reglas del negocio en la base
init.sh             instala dependencias y prepara la configuración
.env.example        variables de configuración, comentadas y sin secretos (copiar a .env)
.env.test.example   base MySQL de pruebas (copiar a .env.test)
requirements.txt    dependencias con versión fija (requirements-deploy.txt suma gunicorn)
render.yaml         publicación gratuita en Render
CLAUDE.md           reglas del proyecto para trabajar con Claude Code
Dockerfile          imagen única de Python para la API y el sitio
docker-compose.yml  MySQL + API + sitio con un solo comando
```

## Opción rápida: Docker Compose

Solo requiere [Docker](https://docs.docker.com/get-docker/) (Docker Desktop en macOS y Windows); no hace falta
instalar Python ni MySQL.

```bash
cp .env.example .env        # opcional: claves propias, TMDB_API_KEY y MAILJET_*
docker compose up --build   # sitio en http://localhost:5001, API en http://localhost:5000/api/salud
```

- La primera vez crea la base en un contenedor MySQL 8.4 y carga `schema.sql` y `seed.sql`. Los datos
  quedan en un volumen: `docker compose down` los conserva y `docker compose down -v` los borra
  (al volver a levantar se recarga el seed, por ejemplo para tener funciones futuras de nuevo).
- Los datos de conexión a la base los fija `docker-compose.yml` y pisan los del `.env`. Desde la
  máquina, la base queda en `localhost:3307` (usuario `cine` / `cine`).
- Para escanear el QR con el celular, poner en `.env` `FRONTEND_URL=http://<IP-de-la-compu>:5001`.
- Los cambios en el código requieren `docker compose up --build` (no hay recarga automática).

Sin Docker, seguir los pasos de abajo.

## Requisitos

- Python 3.12 o superior (la versión que usa el `Dockerfile`)
- MySQL 8 (o MariaDB 10.5+), con el cliente `mysql` en el PATH si se usa `bash init.sh --db`
- Git y Bash (en Windows, Git Bash o WSL)
- Opcional: una API key v3 de [TMDB](https://www.themoviedb.org/) para importar películas y una cuenta Mailjet
  (plan Free) para el correo de la compra (ver [TMDB y Mailjet](#configurar-tmdb-y-mailjet))

## Instalación

1. Clonar el repositorio y entrar en la carpeta:

   ```bash
   git clone https://github.com/LucasFiuba1/tp-integrador-ids-cinemark.git
   cd tp-integrador-ids-cinemark
   ```

2. Crear el entorno virtual, instalar las dependencias de `requirements.txt` y generar el `.env`:

   ```bash
   bash init.sh          # crea .venv, instala dependencias y copia .env.example a .env
   ```

3. Completar `.env`. Hacen falta dos claves distintas (`SECRET_KEY` y `FRONTEND_SECRET_KEY`); generar cada una con:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

   También revisar `DB_*` (usuario y contraseña de MySQL) y, si se van a usar, `TMDB_API_KEY` y `MAILJET_*`.

4. Crear en MySQL el usuario de la aplicación (`DB_USER` / `DB_PASSWORD`). La plantilla no lo crea. Con
   todos los permisos sobre `cine_paradiso` alcanza para que `schema.sql` cree la base y las tablas:

   ```sql
   CREATE USER 'cine'@'localhost' IDENTIFIED BY 'cine';
   GRANT ALL PRIVILEGES ON cine_paradiso.* TO 'cine'@'localhost';
   ```

5. Cargar la base con `src/backend/db/schema.sql` (crea `cine_paradiso` y las tablas) y
   `src/backend/db/seed.sql` (datos de prueba):

   ```bash
   bash init.sh --db     # SOLO base local descartable: borra tablas y carga datos de prueba
   ```

   Equivale a correr a mano `mysql -u <usuario> -p < src/backend/db/schema.sql` y después lo mismo con `seed.sql`.

6. Levantar las aplicaciones (ver [Ejecución](#ejecución)).

Seguir [Configuración del entorno](docs/entorno.md) para generar `SECRET_KEY` y
`FRONTEND_SECRET_KEY`, crear el usuario MySQL y completar todas las variables.
Cada integrante usa su propio `.env`; no compartir credenciales ni subirlas a Git.
**El schema borra las tablas** y fija el nombre `cine_paradiso`: no usar `--db` en
una base con datos que se deban conservar ni en hosting.

## Ejecución

En dos terminales, desde la raíz del repo (en Windows con PowerShell usar `.\.venv\Scripts\Activate.ps1`, o en Git Bash `source .venv/Scripts/activate`):

```bash
source .venv/bin/activate
flask --app src.backend.app run --port 5000 --debug     # API en http://localhost:5000
```

```bash
source .venv/bin/activate
flask --app src.frontend.app run --port 5001 --debug    # Sitio en http://localhost:5001
```

Verificación rápida: `http://localhost:5000/api/salud` devuelve `{"estado": "ok"}` y la portada del sitio muestra la cartelera sin avisos de conexión.

### Verificación de extremo a extremo (compra y validación de QR)

1. Abrir `http://localhost:5001/ingresar` e iniciar sesión como cliente (`ana@mail.com` / `cliente1234`).
2. Elegir una película de la cartelera, seleccionar una función futura, marcar al menos una butaca libre y continuar hasta confirmar el pago simulado para obtener el código QR y la factura (también llega por email si Mailjet está configurado).
3. Cerrar sesión, ingresar como administrador (`admin@cineparadiso.com` / `admin1234`), ir a `/admin/validar` y validar el código QR de la entrada para la función reservada.

Usuarios de prueba que carga `seed.sql`:

- Administrador: `admin@cineparadiso.com` / `admin1234`
- Clientes: `ana@mail.com` y `juan@mail.com` / `cliente1234`

El seed también carga 8 películas, funciones de anteayer a dentro de 6 días en todas las salas (14:00, 17:30 y
21:00) y 4 compras de ejemplo (dos con el QR ya validado y una cancelada). Las fechas son relativas al día de la
carga: para tener funciones futuras de nuevo, volver a correr `bash init.sh --db`.

Esto reinicia **todos los datos**; solo corresponde a una base local descartable.
Para publicar, seguir [Deploy gratuito](docs/deploy.md): servidor WSGI, HTTPS,
credenciales privadas y carga de la base sin usar el servidor de desarrollo.
Los emails de compra y cancelación se envían por la API HTTPS de Mailjet. La factura
incluye un único QR dentro del mensaje y el enlace de cancelación, sin copia adjunta.
Si faltan las claves o el envío falla, la compra queda confirmada igual (`email_enviado: false`)
y el motivo queda en el log. Las pruebas locales simulan el proveedor; no certifican la entrega real.

## Configurar TMDB y Mailjet

Ninguna de las dos es necesaria para levantar el proyecto con los datos del seed; sí para importar películas
nuevas (TMDB) y para recibir el correo de la compra (Mailjet). Se configuran en `.env`; el detalle y los errores
frecuentes están en [Configuración del entorno](docs/entorno.md).

**TMDB** (películas del backoffice):

1. Crear una cuenta en [themoviedb.org](https://www.themoviedb.org/) y pedir una API key en **Settings → API**.
2. Copiar la **API key (v3 auth)** a `TMDB_API_KEY`. No sirve el "API Read Access Token".
3. Reiniciar el backend. Sin clave, la importación devuelve `502 TMDB_NO_DISPONIBLE`.

**Mailjet** (factura con QR y aviso de cancelación, por HTTPS):

1. Crear una cuenta en [Mailjet](https://www.mailjet.com/) con el plan **Free** (sin tarjeta ni trial).
2. Verificar en Mailjet la dirección que se usará como `MAIL_FROM`.
3. Copiar la API key y la Secret key de [API Key Management](https://app.mailjet.com/account/api_keys) a
   `MAILJET_API_KEY` y `MAILJET_SECRET_KEY`. `FRONTEND_URL` arma el enlace "Cancelar compra" del email y el QR:
   para escanearlo con el celular, usar `http://<IP-de-la-compu>:5001`.

El paso a paso completo está en [Correo](docs/entorno.md#correo-mailjet-por-https).

No subir nunca el `.env` ni pegar claves en commits, issues o capturas: `.env` está en el `.gitignore`.

## Pruebas

Desde la raíz, con el entorno virtual activado:

```bash
python -m pytest src/tests -v
```

Las pruebas usan pytest y `unittest.mock`, sin clases ni servicios externos.
Las utilidades comunes están en `src/tests/utilidades.py` y las fixtures en
`src/tests/conftest.py`: `app_backend`, `cliente_backend`, `cabeceras_admin`
y `cabeceras_cliente` permiten probar endpoints con tokens firmados por rol.
`usuario` y `cabeceras` conservan el usuario admin de las pruebas existentes.

Para simular la base de un service, indicar el módulo donde se usan las
operaciones (los imports directos también necesitan parchearse):

```python
from src.tests.utilidades import afirmar_error_json, simular_bd

def test_pelicula_inexistente(cliente_backend, cabeceras_admin):
    with simular_bd(destinos=("src.backend.services.peliculas",)) as bd:
        bd.consultar_uno.return_value = None
        respuesta = cliente_backend.patch(
            "/api/admin/peliculas/99", json={"titulo": "Nuevo"}, headers=cabeceras_admin,
        )
    afirmar_error_json(respuesta, 404, "NO_ENCONTRADO")
```

La simulación ofrece mocks de `consultar`, `consultar_uno`, `ejecutar`,
`transaccion` y su cursor; al salir del `with` restaura los originales.
La autenticación se simula por separado con las fixtures de usuarios:
no incluir `src.backend.auth` entre los destinos del service.

### Pruebas contra MySQL real (opcionales)

Algunas reglas solo se pueden comprobar con una base de verdad: la doble venta con pedidos simultáneos,
los bloqueos, los índices únicos y las consultas de dashboards. Esas pruebas (`src/tests/*_mysql.py`) usan
una **base de pruebas separada** que se borra y se vuelve a crear con `schema.sql` + `seed.sql` en cada corrida
(SCRUM-78). Sin configurarla se saltean y el resto de la suite corre igual.

```bash
cp .env.test.example .env.test   # completar host, puerto, usuario y clave de un MySQL local
```
```bash
python -m pytest src/tests -v
```

El nombre de la base (`PRUEBAS_DB_NAME`, por defecto `cine_paradiso_test`) tiene que terminar en `_test` y
ser distinto del `DB_NAME` del `.env`: así nunca se borra la base de trabajo. No usar la base de producción.
También se puede configurar por variables de entorno (`PRUEBAS_DB_PORT=3306 python -m pytest ...`).

Fixtures de `conftest.py` para estas pruebas: `mysql_pruebas` (config de la base ya recreada),
`app_mysql` y `cliente_http` (app real contra esa base), `token_admin`, `token_cliente` y `token_otro_cliente`
(login real con los usuarios del seed), `fabrica_funciones` y `funcion_con_butacas` (funciones con commit real
que se borran al terminar). Los helpers están en `src/tests/mysql_pruebas.py`.

| Archivo | Qué prueba |
|---|---|
| `test_base_pruebas_mysql.py` | Ejemplo: salud, login y fixtures |
| `test_reglas_criticas_mysql.py` | Doble venta con hilos simultáneos, superposición, cancelación en el límite del plazo y QR (SCRUM-79) |
| `test_butacas_mysql.py` | Bloqueo y liberación de varias butacas |
| `test_dashboards_mysql.py` | Consultas de dashboards contra el seed ([valores esperados](docs/endpoints.md#dashboards)) |

## Reglas del proyecto

- El frontend se comunica con el backend **solo desde Python con `requests`**. Prohibido usar `fetch`, `axios` o `XMLHttpRequest` en el navegador.
- **Sin ORM**: todas las consultas son SQL explícito y parametrizado (`src/backend/db.py`).
- **Sin programación orientada a objetos**: ni en la app ni en las pruebas (`class`, `self`, herencia, `@dataclass`); solo funciones, `dict` y listas.
- Las rutas manejan HTTP; los casos de uso van en `src/backend/services/`, en módulos por funcionalidad (por ejemplo, `compras.py`). Las operaciones atómicas usan una misma `transaccion()`.
- Fechas y horas en un único campo `DATETIME`.
- Sin variables globales ni código repetido: usar `create_app()`, macros de Jinja y los helpers comunes.

## Flujo de trabajo

- `main`: versiones entregables. `develop`: integración.
- Una rama por tarea desde `develop`: `SCRUM-XXX/descripcion`.
- Commits con la clave de la tarea: `SCRUM-XXX: descripcion` (mismo formato para el título de los PRs).
- Merge a `develop` por Pull Request con la revisión de otra persona.

## Documentación

- [Despliegue gratuito para demostraciones](docs/despliegue.md)
- [Configuración del entorno (.env)](docs/entorno.md)
- [Deploy gratuito, verificación y backups](docs/deploy.md)
- [Endpoints de la API](docs/endpoints.md)
- [Modelo de datos](docs/base_de_datos.md)
- [Alcance, hipótesis y supuestos (Confluence)](https://tp-ids-final.atlassian.net/wiki/spaces/~7120200d86d4e20fe64bbfa6c0b78ff3290878/pages/2621441)
- [Backlog (Jira)](https://tp-ids-final.atlassian.net/jira/software/projects/SCRUM/boards/1)

## Integrantes

| Integrante |
|---|
| Lucas Cirillo Berardi |
| Santiago Fernandez Bain |
| Juan Pablo Bruzone |
| Joaquín Nicolás Zavala Eguez |
| Martín Simajowich |
