# Deploy gratuito: backend, frontend y MySQL

Guía para publicar una **demo académica**, manteniendo las dos aplicaciones Flask separadas. No describe un deploy ya realizado ni garantiza disponibilidad de un proveedor. Revisar [Configuración del entorno](entorno.md) primero.

## 1. Arquitectura y opción de hosting

```text
Navegador ──HTTPS──> frontend Flask/Jinja
                         │
                   requests / HTTPS
                         │
                         v
                    backend Flask ──> MySQL/MariaDB
                         │
                         └──HTTPS──> TMDB
```

Se necesitan **dos sitios WSGI** y una base MySQL/MariaDB persistente. La API no necesita CORS para este flujo: las llamadas salen desde Python, no desde el navegador. `BACKEND_URL` debe ser la dirección de la API, nunca la del frontend.

### Receta principal: alwaysdata Free

La oferta gratuita de [alwaysdata](https://www.alwaysdata.com/en/offers/) está destinada a necesidades personales y anuncia Python, bases de datos y hosting sin plazo de trial. El TP académico es el uso previsto para esta guía; no asumir que permite una explotación comercial.

La documentación permite múltiples sitios en una cuenta, también en Free. La oferta consultada anuncia **1 GB SSD compartido, 256 MB RAM, ¼ CPU y 3 días de backups**. **Antes de cargar el proyecto, confirmar en el panel** la disponibilidad de Python WSGI/MySQL y la cuota efectiva. Código, entorno virtual, base, logs y correo consumen recursos de la cuenta. Consultar las condiciones actuales: pueden cambiar.

- Crear únicamente el plan **Free**, sin activar trials, upgrades ni recursos de pago.
- No agregar una tarjeta ni pagar para desbloquear funciones sin autorización del equipo.
- Usar la dirección gratuita de la cuenta `CUENTA.alwaysdata.net`: Free no permite sitios con dominio propio. No crear varias cuentas gratuitas para repartir los componentes.
- No vender entradas reales ni recibir pagos: el plan no admite uso comercial. Esta receta es para datos ficticios y pago simulado.
- Sin tarjeta/pagos, alwaysdata documenta un [modo restringido](https://help.alwaysdata.com/en/docs/admin-billing/profile/restricted-mode/) con filtros HTTP y limitaciones de envío SMTP. Probar TMDB y las llamadas del frontend a la API. Si una restricción bloquea el TP, detenerse antes de contratar nada.
- El envío SMTP de la aplicación **todavía no está implementado**. No prometer factura/QR por email por el solo hecho de configurar el hosting.

### Por qué no usar directamente otras ofertas gratuitas

| Proveedor | Problema para esta arquitectura |
|---|---|
| PythonAnywhere Free | Una sola web app; las cuentas gratuitas nuevas dejaron de incluir MySQL. La salida de red está limitada. No es una receta equivalente para las dos apps y la base. |
| Render Free | No ofrece MySQL administrado gratuito; su Postgres gratuito expira y no reemplaza este SQL. Los servicios gratuitos duermen y bloquean salida SMTP por 25/465/587. |

No combinar alwaysdata Free como **solo servidor de base** con otro hosting: sus condiciones no permiten usar el pack gratuito únicamente para alojar bases. Tampoco sustituir MySQL por SQLite/Postgres sin adaptar código y pruebas.

## 2. Preparar cuenta, código y Python

En alwaysdata:

1. Crear la cuenta Free y anotar el **nombre de cuenta** y acceso SSH que muestre el panel. No son los usuarios de login del cine.
2. Revisar **Environment → Python** y elegir una versión soportada por `requirements.txt` (preferentemente Python 3.13, verificando las dependencias fijadas).
3. Entrar por SSH y preparar el proyecto bajo el directorio de la cuenta. En los comandos, reemplazar `CUENTA`, `RAMA_PUBLICADA` y los otros marcadores; no pegarlos literalmente.

```bash
mkdir -p "$HOME/apps"
cd "$HOME/apps"
git clone https://github.com/LucasFiuba1/tp-integrador-ids-cinemark.git cinemark
cd cinemark
git checkout RAMA_PUBLICADA
git rev-parse HEAD
PYTHON_VERSION=3.13 python -m venv .venv
source .venv/bin/activate
python --version
python -m pip install --no-cache-dir -r requirements.txt
python -m pip check
python -m pytest src/tests -v
```

Publicar una rama/commit revisado por el equipo, no asumir que la rama de una tarea es entregable. En alwaysdata la documentación indica usar `python`, no `python3`, y `PYTHON_VERSION` selecciona la versión. El virtualenv y los dos sitios WSGI deben usar **la misma versión**.

Si una versión fijada de una dependencia no está disponible o no soporta el Python elegido, **el deploy queda bloqueado**. Resolverlo y probarlo en el repositorio; no sustituir paquetes silenciosamente en el servidor. El proyecto no incluye Gunicorn ni contenedores: esta receta utiliza el uWSGI que ofrece alwaysdata.

## 3. Configurar los secretos

Hay dos alternativas: variables del panel de cada sitio WSGI o un `.env` privado. Preferir el panel si permite separar los secretos por servicio.

- **Backend:** `SECRET_KEY`, todas las `DB_*`, `TMDB_API_KEY`, `MINUTOS_RESERVA`, `HORAS_LIMITE_CANCELACION`; `SMTP_*` cuando exista la implementación.
- **Frontend:** `FRONTEND_SECRET_KEY`, `BACKEND_URL`.
- Generar dos claves **nuevas para este deploy**, como indica [la guía del entorno](entorno.md#3-generar-las-dos-claves-de-la-aplicación). No copiar las de un compañero.
- Usar HTTPS en `BACKEND_URL`, sin `/api` al final. Si la API se publica en `https://CUENTA.alwaysdata.net/api`, la base es `https://CUENTA.alwaysdata.net`: las rutas de la aplicación ya empiezan por `/api`.
- No poner secretos en los archivos WSGI, comandos de arranque, repositorio ni capturas del panel.

Si se utiliza `.env`, crear un directorio privado **fuera del checkout**, por ejemplo `$HOME/private/cinemark`, con permisos `700`, y un archivo de configuración con permisos `600`. Completar allí las variables con un editor y enlazarlo desde la raíz del proyecto:

```bash
mkdir -p "$HOME/private/cinemark"
chmod 700 "$HOME/private/cinemark"
# Crear y completar $HOME/private/cinemark/.env con un editor privado.
chmod 600 "$HOME/private/cinemark/.env"
cd "$HOME/apps/cinemark"
# Solo si todavía no existe .env: no reemplazar una configuración previa.
ln -s "$HOME/private/cinemark/.env" .env
git check-ignore .env
```

`load_dotenv()` encuentra ese `.env`; las variables del panel tienen prioridad. No configurar valores distintos para el mismo servicio en ambas fuentes.

## 4. Crear e importar la base

En **Databases → MySQL**, crear la base y un usuario desde el panel. alwaysdata proporciona nombres prefijados y host del estilo `mysql-CUENTA.alwaysdata.net`; copiar los datos reales a `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` y `DB_NAME`. Crear el usuario y permisos en el panel: no intentar `CREATE DATABASE` desde la aplicación.

**No ejecutar `bash init.sh --db` en hosting.** `schema.sql` contiene `CREATE DATABASE`, `USE cine_paradiso` y `DROP TABLE`; `seed.sql` también fija `USE cine_paradiso`. Cambiar `DB_NAME` en `.env` no modifica esos archivos.

Para la **primera carga en una base vacía**, generar copias temporales fuera del repositorio sin las instrucciones que fijan el nombre de la base. Esta transformación conserva los `DROP TABLE`: sigue siendo destructiva.

```bash
cd "$HOME/apps/cinemark"
mkdir -p "$HOME/private/cinemark"
chmod 700 "$HOME/private/cinemark"
python - <<'PY'
from pathlib import Path

destino = Path.home() / "private" / "cinemark"
for nombre in ("schema.sql", "seed.sql"):
    origen = Path("src/backend/db") / nombre
    lineas = origen.read_text().splitlines(keepends=True)
    contenido = "".join(
        linea for linea in lineas
        if not linea.strip().upper().startswith(("CREATE DATABASE ", "USE "))
    )
    archivo = destino / nombre
    archivo.write_text(contenido)
    archivo.chmod(0o600)
PY
```

Revisar las copias antes de importar. Reemplazar los marcadores con los valores del panel y usar `-p` **sin contraseña al lado**: el cliente la pide de forma privada.

```bash
mysql -h mysql-CUENTA.alwaysdata.net -P 3306 -u USUARIO_DB -p NOMBRE_DB \
  < "$HOME/private/cinemark/schema.sql"
```

O bien importar la copia en la base seleccionada desde phpMyAdmin. No cargar el schema sobre datos que haya que preservar.

### Datos y administrador

La opción más segura para una instalación real es **no cargar el seed**: crea un administrador propio y luego carga locales, salas, películas, funciones y servicios desde el backoffice.

Con el virtualenv activado, la configuración del backend disponible en la terminal y la base inicializada, ejecutar desde la raíz del repo:

```bash
python - <<'PY'
from getpass import getpass
from werkzeug.security import generate_password_hash
from src.backend.app import create_app
from src.backend.db import transaccion

email = input("Email del administrador: ").strip()
nombre = input("Nombre: ").strip()
password = getpass("Contraseña nueva (mínimo 12 caracteres): ")
if not email or not nombre or len(password) < 12:
    raise SystemExit("Datos incompletos o contraseña demasiado corta.")
if password != getpass("Repetir contraseña: "):
    raise SystemExit("Las contraseñas no coinciden.")
with create_app().app_context():
    with transaccion() as cursor:
        cursor.execute(
            "INSERT INTO usuarios (nombre, email, password_hash, rol) "
            "VALUES (%s, %s, %s, 'admin')",
            (nombre, email, generate_password_hash(password, method="pbkdf2:sha256")),
        )
print("Administrador creado.")
PY
```

El registro público crea clientes, no administradores. No usar una contraseña compartida por todo el grupo para un sitio público. Si las variables están solo en el panel WSGI, **no se transmiten automáticamente a la terminal SSH**: usar también un archivo privado para esta operación o el mecanismo seguro de variables del proveedor, sin incluir credenciales en el comando.

Para una **demo con datos ficticios**, importar el seed temporal después del schema:

```bash
mysql -h mysql-CUENTA.alwaysdata.net -P 3306 -u USUARIO_DB -p NOMBRE_DB \
  < "$HOME/private/cinemark/seed.sql"
```

Antes de hacerla pública, cambiar las contraseñas de **las tres cuentas** conocidas del seed; no alcanza con cambiar solo la del admin. Este ejemplo conserva sus relaciones con las compras de prueba:

```bash
python - <<'PY'
from getpass import getpass
from werkzeug.security import generate_password_hash
from src.backend.app import create_app
from src.backend.db import transaccion

with create_app().app_context():
    with transaccion() as cursor:
        for email in ("admin@cineparadiso.com", "ana@mail.com", "juan@mail.com"):
            password = getpass(f"Nueva contraseña para {email} (mínimo 12): ")
            if len(password) < 12 or password != getpass("Repetir contraseña: "):
                raise SystemExit("Contraseña inválida; se revierte toda la operación.")
            cursor.execute(
                "UPDATE usuarios SET password_hash = %s WHERE email = %s",
                (generate_password_hash(password, method="pbkdf2:sha256"), email),
            )
            if cursor.rowcount != 1:
                raise SystemExit("No se encontró una cuenta del seed; se revierte la operación.")
print("Contraseñas del seed reemplazadas.")
PY
```

No anunciar que los QR de ejemplo funcionan: el seed usa marcadores, no tokens generados por el backend del deploy. Las funciones del seed son relativas al día de carga; pasado el período, crear otras desde el backoffice. **No recargar el schema para renovar la cartelera**.

## 5. Configurar los dos sitios WSGI

Crear archivos de entrada **fuera del repositorio**, en `$HOME/private/cinemark`. No usar `flask run`, `--debug` ni el servidor de desarrollo para tráfico público.

Contenido de `backend_wsgi.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "apps" / "cinemark"))

from src.backend.app import create_app

application = create_app()
clave = application.config["SECRET_KEY"]
if not clave or len(clave) < 32 or clave.startswith(("dev-", "cambiar-")):
    raise RuntimeError("Configurar una SECRET_KEY segura para el backend.")
application.config.update(DEBUG=False, TESTING=False)
```

Contenido de `frontend_wsgi.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "apps" / "cinemark"))

from src.frontend.app import create_app

application = create_app()
clave = application.config["SECRET_KEY"]
if not clave or len(clave) < 32 or clave.startswith(("dev-", "cambiar-")):
    raise RuntimeError("Configurar una FRONTEND_SECRET_KEY segura.")
if not application.config["BACKEND_URL"].startswith("https://"):
    raise RuntimeError("Configurar BACKEND_URL con la URL HTTPS de la API.")
application.config.update(
    DEBUG=False,
    TESTING=False,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
```

Las opciones de cookies se aplican en el wrapper; escribir `SESSION_COOKIE_SECURE` en `.env` **no basta**, porque el `config.py` actual no lee esa variable. La cookie segura requiere acceder por HTTPS.

En **Web → Sites**, agregar dos sitios de tipo **Python WSGI**:

| Campo | Backend | Frontend |
|---|---|---|
| Ruta del archivo WSGI | `/home/CUENTA/private/cinemark/backend_wsgi.py` | `/home/CUENTA/private/cinemark/frontend_wsgi.py` |
| Directorio de trabajo | `/home/CUENTA/apps/cinemark` | `/home/CUENTA/apps/cinemark` |
| Directorio del virtualenv | `/home/CUENTA/apps/cinemark/.venv` | Igual |
| Versión Python | La utilizada al crear `.venv` | Igual |
| Variables | Las del backend | Las del frontend |
| Dirección | URL que enrute `/api` al backend | URL que enrute `/` al frontend |

Para no comprar dominio, usar el subdominio gratuito `CUENTA.alwaysdata.net`: configurar las direcciones `CUENTA.alwaysdata.net/api` para el backend y `CUENTA.alwaysdata.net` para el frontend, **conservando `/api` en el path que recibe Flask**. No asumir que otros subdominios están incluidos. Confirmar la sintaxis de direcciones/prioridad del panel en la [documentación de sitios](https://help.alwaysdata.com/en/docs/web-hosting/sites/). Este enrutamiento debe comprobarse en la cuenta real antes de considerar terminado el deploy.

Al configurar una ruta `/api`, evitar un proxy que quite ese prefijo: los blueprints de Flask esperan `/api/...`. Si el enrutamiento del hosting lo elimina, ajustar la configuración del sitio/proxy antes de continuar; no modificar `BACKEND_URL` agregándole un segundo `/api`.

Habilitar/verificar HTTPS y redirección de HTTP a HTTPS para las direcciones elegidas; aprovechar el certificado gratuito del hosting. Los dos procesos deben poder importar `src` desde el directorio de trabajo. Reiniciar ambos sitios desde el panel después de guardar la configuración. Consultar el log del sitio ante errores de importación o arranque.

## 6. Verificar antes de compartir el enlace

Desde una terminal, reemplazando la URL:

```bash
curl --fail --show-error https://CUENTA.alwaysdata.net/api/salud
curl --fail --show-error https://CUENTA.alwaysdata.net/api/cartelera
```

La salud debe responder `{"estado":"ok"}`, pero **no valida conexión a MySQL, TMDB ni emails**. La cartelera permite comprobar acceso a la base, aunque esté vacía.

- Abrir el frontend por HTTPS y verificar estilos, imágenes y páginas de error.
- Registrar un cliente ficticio, iniciar/cerrar sesión y probar que no entra al backoffice.
- Entrar con el administrador privado y comprobar gestión de datos y búsqueda de películas en TMDB.
- Comprobar el flujo de reserva implementado y los permisos. No anunciar pago/email/cancelación completos si no están implementados y probados.
- Consultar logs de ambos sitios: sin tracebacks ni credenciales. En alwaysdata los de uWSGI están bajo `/home/CUENTA/admin/logs/uwsgi/` y se consultan también desde el panel.
- Confirmar que los placeholders no quedaron activos, `DEBUG` está apagado, las cookies del frontend son `Secure`/`HttpOnly`/`SameSite=Lax` y las claves son persistentes.
- Verificar fecha/hora de Python y `SELECT NOW(), @@session.time_zone;` en MySQL. El código usa `DATETIME` sin zona y compara horas desde Python y SQL: definir una convención única antes de cargar funciones. **No asumir que poner `TZ` en el sitio corrige la zona de MySQL.** Si no coinciden, resolver la configuración de ambos o adaptar el código antes de probar vencimientos/cancelaciones.
- La suite normal usa mocks: pasarla no reemplaza estas comprobaciones contra el hosting.

## 7. Actualizar, hacer backup y volver atrás

Guardar el commit publicado (`git rev-parse HEAD`) y hacer un backup **antes** de cambios de esquema/datos. El proyecto no tiene migraciones automáticas.

Ejemplo de backup desde SSH, con nombre de archivo único:

```bash
umask 077
mysqldump -h mysql-CUENTA.alwaysdata.net -P 3306 -u USUARIO_DB -p \
  --single-transaction --no-tablespaces NOMBRE_DB \
  > "$HOME/private/cinemark/backup-$(date +%Y%m%d-%H%M%S).sql"
```

Usar el cliente de dump compatible con la versión MySQL/MariaDB del proveedor, o exportar desde phpMyAdmin si ese comando/opción no está disponible. Descargar una copia privada fuera del hosting; su retención gratuita puede ser corta. Vigilar cuota de disco y eliminar backups viejos solo después de comprobar la copia.

Para actualizar código sin tocar datos:

```bash
cd "$HOME/apps/cinemark"
git status --short
git fetch origin
git checkout COMMIT_REVISADO
source .venv/bin/activate
python -m pip install --no-cache-dir -r requirements.txt
python -m pip check
python -m pytest src/tests -v
```

Detenerse si hay cambios locales inesperados; no usar `reset --hard` para resolverlos. Reiniciar backend y frontend desde el panel y repetir la verificación. **No ejecutar `init.sh --db`, schema ni seed durante una actualización normal.** No cambiar las claves al actualizar.

Si falla el nuevo código, volver al commit previo, reinstalar sus dependencias y reiniciar. Si hubo cambios de datos/esquema, volver al código no los revierte: restaurar el backup compatible siguiendo un procedimiento acordado. Probar la restauración antes de depender de ella.

Mantener activa la cuenta: alwaysdata puede suspender Free por no entrar al panel. La documentación indica acceso al menos cada **120 días durante el primer año**, cada seis meses entre uno y cuatro años, y anualmente después. Que alguien visite el sitio no reemplaza entrar al panel; consultar la [política de suspensión](https://help.alwaysdata.com/en/docs/admin-billing/profile/suspension/).

## 8. Límites y pendientes de esta versión

- Esta guía prepara una demo; no certifica que sea apta para manejar clientes reales, cobros ni datos sensibles.
- El correo está pendiente. El proveedor puede restringir SMTP; completar variables no elimina esa restricción. Probar Gmail/STARTTLS cuando se implemente, sin pagar para desbloquearlo automáticamente.
- El alcance declarado incluye QR, pago y cancelaciones, pero no todos los flujos están implementados en esta rama. Verificar el código y las pruebas del commit que se publique.
- Revisar protección CSRF, manejo de proxies, revocación de sesiones, permisos de base y política de backups antes de una publicación productiva. El wrapper no implementa esas funciones.
- No exponer MySQL públicamente más de lo requerido; no usar `root` como usuario de aplicación ni compartir credenciales entre ambientes.
- No hay Dockerfile, Compose ni configuración de despliegue automática en el repositorio. No hay un servicio desplegado o URL de producción verificados por esta documentación.

## Fuentes oficiales

Consultadas para esta guía; confirmar límites y disponibilidad en la cuenta antes de publicar:

- [alwaysdata: ofertas](https://www.alwaysdata.com/en/offers/) y [elección del plan](https://help.alwaysdata.com/en/docs/admin-billing/billing/choose-its-paas/).
- [alwaysdata: configuración Python/WSGI](https://help.alwaysdata.com/en/docs/web-hosting/languages/python/configuration/), [sitios](https://help.alwaysdata.com/en/docs/web-hosting/sites/), [bases de datos](https://help.alwaysdata.com/en/docs/web-hosting/databases/) y [datos de conexión](https://help.alwaysdata.com/en/docs/technical-specifications/login-details/).
- [alwaysdata: modo restringido](https://help.alwaysdata.com/en/docs/admin-billing/profile/restricted-mode/) y [correo SMTP](https://help.alwaysdata.com/en/docs/emails/use-an-email-address/).
- [alwaysdata: restricciones de Free y suspensión por inactividad](https://help.alwaysdata.com/en/docs/admin-billing/profile/suspension/).
- [PythonAnywhere: límites gratuitos](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/).
- [Render: servicios gratuitos](https://render.com/docs/free).
- [TMDB: autenticación](https://developer.themoviedb.org/docs/authentication-application) y [Google: contraseñas de aplicación](https://support.google.com/accounts/answer/185833).
