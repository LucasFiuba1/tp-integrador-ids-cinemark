# Cine Paradiso: venta de entradas de cine

Proyecto Integrador de Introducción al Desarrollo de Software (Cátedra Lanzillotta, 2.º cuatrimestre 2026), grupo 15.

Aplicación web para comprar entradas de cine (película → función → butacas → servicios → pago → QR por email) y backoffice para administrar la cartelera, las salas y ver estadísticas.

## Estructura

```
src/
  backend/          API REST en Flask (JSON) que se conecta a MySQL
    app.py          create_app(): configuración, manejo de errores y blueprints
    config.py       lectura de variables de entorno
    db/
      schema.sql    creación de tablas y relaciones
      seed.sql      datos iniciales
    db.py           acceso a MySQL con SQL explícito (sin ORM)
    errores.py      formato único de errores JSON
    routes/         un blueprint por módulo (auth, cartelera, compras, admin, dashboards)
    services/       lógica de negocio por funcionalidad, a implementar con los casos de uso
  frontend/         sitio del cliente y backoffice en Flask + Jinja
    app.py          create_app()
    api_client.py   única puerta al backend, usando requests
    routes/         blueprints: público y backoffice
    templates/      base.html, macros y páginas
    static/css/     estilos responsive
  tests/              pruebas automatizadas con pytest
docs/
  entorno.md        variables, claves, MySQL y configuración local
  deploy.md         publicación gratuita de las dos apps y la base
  endpoints.md      listado de endpoints con ejemplos
  base_de_datos.md  diagrama entidad-relación y reglas del negocio en la base
init.sh             instala dependencias y prepara la configuración
.env.example        variables de configuración (copiar a .env)
```

## Requisitos

- Python 3.9 o superior
- MySQL 8 (o MariaDB 10.5+)

## Instalación

```bash
bash init.sh          # crea .venv, instala dependencias y genera .env
# Completar .env: claves propias, MySQL y TMDB (ver la guía del entorno)
bash init.sh --db     # SOLO base local descartable: borra tablas y carga datos de prueba
```

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
2. Elegir una película de la cartelera, seleccionar una función futura, marcar al menos una butaca libre y continuar hasta confirmar el pago simulado para obtener el código QR y la factura.
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
SMTP está configurado en la plantilla, pero el envío de correo todavía no está
implementado en esta versión.

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

Para verificar las consultas de dashboards contra el `seed.sql` real (SCRUM-76),
hay pruebas MySQL opcionales. Requieren una base **descartable y aislada** en
`127.0.0.1`, con usuario `root`, contraseña vacía y nombre `cine_paradiso`,
cargada con `schema.sql` y `seed.sql`. No usar una base de trabajo ni producción.

```bash
PRUEBAS_MYSQL_PUERTO=33976 python -m pytest src/tests/test_dashboards_mysql.py -v
```

El puerto debe ser el de esa instancia aislada. Sin la variable, estas pruebas
se omiten y la suite normal sigue sin necesitar MySQL. Los contratos y los
valores esperados del seed están en [Dashboards](docs/endpoints.md#dashboards).

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
