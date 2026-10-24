# Cine Paradiso: venta de entradas de cine

Proyecto Integrador de Introducción al Desarrollo de Software (Cátedra Lanzillotta, 2.º cuatrimestre 2026), grupo 15.

Aplicación web para comprar entradas de cine (película → función → butacas → servicios → pago → QR por email) y backoffice para administrar la cartelera, las salas y ver estadísticas.

## Estructura

```
src/
  backend/          API REST en Flask (JSON) que se conecta a MySQL
    app.py          create_app(): configuración, manejo de errores y blueprints
    config.py       lectura de variables de entorno
    db.py           acceso a MySQL con SQL explícito (sin ORM)
    errores.py      formato único de errores JSON
    routes/         un blueprint por módulo (auth, cartelera, compras, admin, dashboards)
    services/       lógica de negocio por funcionalidad, a implementar con los casos de uso
    sql/
      schema.sql    creación de tablas y relaciones
      seed.sql      datos iniciales
  frontend/         sitio del cliente y backoffice en Flask + Jinja
    app.py          create_app()
    api_client.py   única puerta al backend, usando requests
    routes/         blueprints: público y backoffice
    templates/      base.html, macros y páginas
    static/css/     estilos responsive
tests/              pruebas automatizadas con unittest
docs/
  endpoints.md      listado de endpoints con ejemplos
  base_de_datos.md  diagrama entidad-relación y reglas del negocio en la base
init.sh             instala dependencias y prepara la configuración
.env.example        variables de configuración (copiar a .env)
```

## Requisitos

- Python 3.10 o superior
- MySQL 8 (o MariaDB 10.5+)

## Instalación

```bash
bash init.sh          # crea .venv, instala dependencias y genera .env
# Completar .env con las credenciales de MySQL
bash init.sh --db     # crea la base cine_paradiso y carga los datos iniciales
```

## Ejecución

En dos terminales, desde la raíz del repo:

```bash
source .venv/bin/activate
flask --app src.backend.app run --port 5000 --debug     # API en http://localhost:5000
```

```bash
source .venv/bin/activate
flask --app src.frontend.app run --port 5001 --debug    # Sitio en http://localhost:5001
```

Verificación rápida: `http://localhost:5000/api/salud` devuelve `{"estado": "ok"}` y la portada del sitio muestra el estado de la API.

Usuario administrador de prueba: `admin@cineparadiso.com` / `admin1234`.

## Pruebas

Desde la raíz, con el entorno virtual activado:

```bash
python -m unittest discover -s tests -v
```

Las pruebas iniciales verifican la API de salud, el formato de errores y la
portada con la API disponible o caída, sin requerir MySQL ni servidores activos.
Al implementar compras, reservas y permisos, agregar sus pruebas en `tests/`.

## Reglas del proyecto

- El frontend se comunica con el backend **solo desde Python con `requests`**. Prohibido usar `fetch`, `axios` o `XMLHttpRequest` en el navegador.
- **Sin ORM**: todas las consultas son SQL explícito y parametrizado (`src/backend/db.py`).
- Las rutas manejan HTTP; los casos de uso van en `src/backend/services/`, en módulos por funcionalidad (por ejemplo, `compras.py`). Las operaciones atómicas usan una misma `transaccion()`.
- Fechas y horas en un único campo `DATETIME`.
- Sin variables globales ni código repetido: usar `create_app()`, macros de Jinja y los helpers comunes.

## Flujo de trabajo

- `main`: versiones entregables. `develop`: integración.
- Una rama por tarea desde `develop`: `feature/SCRUM-XX-descripcion`.
- Commits con la clave de la tarea: `SCRUM-XX: descripción del cambio`.
- Merge a `develop` por Pull Request con la revisión de otra persona.

## Documentación

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
| Francisco Martinez |
| Víctor Daniel Morinigo |
| Nicolas Valenzuela |
| Joaquin Zavala |
| Martin Simajowich |
