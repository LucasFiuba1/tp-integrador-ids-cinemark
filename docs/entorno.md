# Configuración del entorno (.env)

Esta guía sirve para cada integrante del equipo y para quien publique la aplicación. Para el hosting, seguir también [Deploy gratuito](deploy.md).

## 1. Preparar el entorno local

Desde la raíz del repositorio, con Python y MySQL/MariaDB instalados:

```bash
bash init.sh
source .venv/bin/activate
```

El script instala `requirements.txt` y copia `.env.example` a `.env` **solo si no existe**. No configura MySQL ni obtiene credenciales externas. Revisar que la instalación termine sin errores antes de continuar.

Editar `.env` con un editor local. No copiar el `.env` de otra persona: copiar la **plantilla** y completar los valores propios. El archivo está ignorado por Git; `.env.example` es la única plantilla que se comparte.

La aplicación también acepta variables definidas en el entorno del proceso. `load_dotenv()` no reemplaza las que ya estén exportadas: si un cambio del archivo no se refleja, revisar la configuración del hosting o las variables exportadas en la terminal. Ejecutar siempre desde la raíz del repositorio y reiniciar ambas aplicaciones después de modificar la configuración.

### Si .env es un enlace simbólico

En una instalación puede haberse guardado la configuración en un archivo privado fuera del repositorio, con `.env` como enlace. No hace falta reproducir la ruta personal de esa instalación: cada compañero crea su propio `.env`.

Para reconocer un enlace sin mostrar credenciales:

```bash
ls -l .env
```

Editar el archivo de destino si el editor reemplaza los enlaces al guardar. Dar permiso de lectura/escritura solo al propietario (`chmod 600` sobre el archivo real). No eliminar el destino: rompería la configuración local.

## 2. Variables

Los valores por defecto siguientes son los del código cuando falta una variable. No implican que sean seguros para publicar.

### Backend

| Variable | Para qué sirve | Valor local / requisito |
|---|---|---|
| `SECRET_KEY` | Firma los tokens de autenticación de la API. | Generar una clave propia; el default `dev-solo-para-desarrollo` es inseguro. |
| `DB_HOST` | Servidor MySQL/MariaDB. | `localhost`; en hosting, el host que entregue el proveedor. |
| `DB_PORT` | Puerto de MySQL/MariaDB. | `3306`; número entero. |
| `DB_USER` | Usuario de la base, no usuario del sitio. | La plantilla propone `cine`; el código usa `root` si falta. El usuario debe existir y tener permisos. |
| `DB_PASSWORD` | Contraseña de ese usuario MySQL. | La de tu servidor; el default del código es vacío. No usar la contraseña de login del sitio. |
| `DB_NAME` | Nombre de la base. | `cine_paradiso` en local; en hosting puede tener un prefijo obligatorio. |
| `TMDB_API_KEY` | Consulta y búsqueda de películas en TMDB desde el backend. | API key **v3**, no el token de lectura. Sin clave, la importación devuelve `TMDB_NO_DISPONIBLE`; el seed no necesita consultar TMDB. |
| `MINUTOS_RESERVA` | Minutos hasta que vence una reserva pendiente. | `10`; usar un entero positivo. Se usa al crear la reserva. |
| `HORAS_LIMITE_CANCELACION` | Límite de cancelación antes de una función. | `2`; entero positivo. Se aplica al cancelar desde el perfil o el enlace del email. |

### Frontend

| Variable | Para qué sirve | Valor local / requisito |
|---|---|---|
| `FRONTEND_SECRET_KEY` | Firma la cookie de sesión de Flask: token, rol y nombre del usuario. | Generar otra clave, distinta de `SECRET_KEY`; el default también es inseguro. |
| `BACKEND_URL` | Dirección base a la que el frontend llama desde Python con `requests`. | `http://localhost:5000` en local; en hosting, URL HTTPS real de la API. **Sin `/api` al final**: el cliente agrega las rutas. |

El frontend no se conecta directamente a MySQL ni consulta TMDB. No necesita esas credenciales si se despliega por separado. La cookie está **firmada, no cifrada**: no guardar contraseñas ni claves de servicios en la sesión.

### Correo (Mailjet por HTTPS)

| Variable | Para qué sirve | Valor |
|---|---|---|
| `MAILJET_API_KEY` | API key de Mailjet (usuario de la autenticación HTTPS). | Vacía por defecto: no se intenta enviar. |
| `MAILJET_SECRET_KEY` | Secret key de Mailjet (contraseña de la autenticación HTTPS). | Vacía por defecto; guardar ambas claves solo en el backend privado. |
| `MAIL_FROM` | Dirección que figura como remitente. | Debe estar verificada y autorizada en Mailjet; vacía por defecto, sin remitente automático. |
| `FRONTEND_URL` | Dirección pública del sitio del cliente (sin `/` al final). | `http://localhost:5001` en local; se usa para el enlace "Cancelar compra" del email y para la URL `/entrada?token=...` que codifica el QR. |

El backend usa `POST https://api.mailjet.com/v3.1/send` con un tiempo máximo de
espera de 10 segundos, sin reintentos automáticos ni redirecciones. No necesita
SMTP, que Render Free bloquea. Las variables `SMTP_*` y `BREVO_API_KEY` ya no se usan.
Se reemplazó Brevo porque su API transaccional no documenta soporte para imágenes
embebidas por Content-ID. Mailjet permite incluir el QR en el mensaje sin alojarlo
en una URL pública.

**Activar el correo:**

1. Crear una cuenta en [Mailjet](https://www.mailjet.com/) y seleccionar únicamente
   el plan **Free**, sin tarjeta, trial ni upgrades. Su documentación anuncia
   200 emails diarios y 6000 por mes; confirmar la cuota y el importe $0 en la cuenta antes de usarla.
2. En la configuración de remitentes, agregar la dirección que se usará como
   `MAIL_FROM` y completar su verificación. Revisar también que la cuenta tenga
   autorizado el envío transaccional. La verificación previa en Brevo no se traslada
   a Mailjet. El proveedor puede exigir autenticación del dominio por sus reglas
   o por DMARC; verificar una casilla no garantiza que cualquier
   dirección pueda usarse como remitente.
3. Obtener **API key y Secret key** en
   [API Key Management](https://app.mailjet.com/account/api_keys). Guardarlas en
   `MAILJET_API_KEY` y `MAILJET_SECRET_KEY` del `.env` privado o del panel del backend;
   nunca en el frontend, Git, capturas ni logs. La secret key puede mostrarse una sola vez.
4. En Render, cargar `MAILJET_API_KEY`, `MAILJET_SECRET_KEY` y `MAIL_FROM` en el servicio de la API.
   `render.yaml` los declara con `sync: false`, pero no contiene los valores.
   Revisar que `FRONTEND_URL` sea la URL pública real del sitio y reiniciar/desplegar
   el backend con esta versión. Las variables de un servicio existente pueden
   requerir carga manual en el panel.
5. Con una cuenta cliente cuya casilla puedas revisar, confirmar una compra para
   una función a más de `HORAS_LIMITE_CANCELACION` horas. Comprobar en la casilla
    (incluido spam) el detalle, un único QR visible dentro de la tarjeta y el enlace
   de cancelación. Abrir ese enlace, confirmar la cancelación y comprobar el
   segundo email. Verificar también que se liberen las butacas y se invalide el QR.

El QR se incrusta mediante `InlinedAttachments` con `ContentID`, referenciado por
`cid:` en el HTML. No se agrega una copia en `Attachments`, porque algunos clientes
la muestran debajo del mensaje y duplican visualmente el QR. No se usa una URL
pública ni una imagen base64 dentro del HTML. Si el cliente oculta imágenes,
habilitar la visualización del contenido HTML. El aviso de cancelación no incluye QR. Un fallo del
proveedor no revierte una compra confirmada ni una cancelación; en la confirmación
se informa `email_enviado: false`. `email_enviado: true` indica aceptación del
proveedor, **no recepción en la casilla**. Revisar la entrega y los registros de
Mailjet, incluidos rechazos, remitente sin autorización y cuota agotada.

**Pruebas locales:** `python -m pytest src/tests/test_correo.py src/tests/test_cancelar_api.py -q`
usa mocks y no manda correos. Hay una prueba de envío real optativa en
`src/tests/test_correo.py`: con las credenciales configuradas, definir
`MAILJET_PRUEBA_DESTINO` en el entorno y ejecutar únicamente
`test_envio_real_a_casilla_configurada`. Esa prueba envía un mail de ejemplo,
consume cuota y verifica la aceptación de la API, no la llegada ni una compra real.
No habilitarla en CI ni al correr la suite habitual.

Fuentes: [referencia oficial de Send API y adjuntos](https://dev.mailjet.com/_bundle/openapi/openapi-mailjet.yaml),
[validación del remitente](https://dev.mailjet.com/docs/email-api/senders-domains/sender-validation)
y [límites de Free](https://documentation.mailjet.com/hc/en-us/articles/19154256993051-Changes-to-Our-Free-Plan).

## 3. Generar las dos claves de la aplicación

Con el entorno virtual activado, ejecutar **dos veces**:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Guardar el primer resultado como `SECRET_KEY` y el segundo como `FRONTEND_SECRET_KEY`. Cada comando genera una clave con 48 bytes aleatorios (384 bits); no usar nombres, fechas ni contraseñas personales. Hacerlo en una terminal privada, sin compartir los resultados ni guardarlos en el repositorio.

- **Cada compañero, en local:** genera su propio par. No comparte tus claves.
- **Un deploy compartido:** todas las instancias del backend usan una misma `SECRET_KEY`; todas las del frontend, una misma `FRONTEND_SECRET_KEY`. Las dos claves siguen siendo distintas entre sí.
- **Local, pruebas y hosting:** usar pares distintos.
- **Actualizaciones/reinicios:** conservar las claves. No generarlas en cada arranque ni como parte del build.
- **Rotación:** cambiar `SECRET_KEY` invalida los tokens firmados con ella; cambiar `FRONTEND_SECRET_KEY` invalida las sesiones existentes. Avisar al equipo y reiniciar los procesos. Los usuarios deberán iniciar sesión nuevamente.

La validación actual no impide arrancar con los placeholders de la plantilla o con defaults inseguros: es responsabilidad de quien configura reemplazarlos antes de publicar.

## 4. Obtener y configurar TMDB

1. Entrar en [TMDB](https://www.themoviedb.org/), crear una cuenta e ir a **Settings → API**.
2. Solicitar una clave para el proyecto respetando sus términos.
3. Copiar la **API key (v3 auth)** a `TMDB_API_KEY` en el archivo privado o panel del backend.
4. Reiniciar el backend y probar una búsqueda/importación desde el backoffice con una cuenta administradora.

El código autentica con el parámetro `api_key`; no espera el token largo **API Read Access Token**. Para diagnosticar, no publicar URLs que incluyan `api_key`, porque exponen la credencial. Referencia: [autenticación de TMDB](https://developer.themoviedb.org/docs/authentication-application).

Si una clave se filtra, reemplazarla/revocarla en el proveedor: borrarla de un commit posterior no elimina el historial.

## 5. Preparar MySQL local y arrancar

Antes de cargar datos, crear en MySQL un usuario con las credenciales de `DB_USER`/`DB_PASSWORD` y permisos sobre `cine_paradiso`. La plantilla **no crea** el usuario `cine`. Para la carga inicial el script necesita permiso para crear la base y las tablas; después, usar un usuario de aplicación con permisos limitados.

**Atención: `bash init.sh --db` borra y recrea las tablas.** Usarlo únicamente para inicializar o reiniciar una base local descartable. Hacer un backup si hay datos que conservar. El SQL fija `cine_paradiso`: cambiar únicamente `DB_NAME` no cambia el destino de ese script.

```bash
bash init.sh --db
```

Requiere el cliente `mysql` en el PATH. El script carga `.env` con `source`: para que también sea compatible con Bash, usar `NOMBRE=valor` sin espacios alrededor del `=` y encerrar valores con espacios o caracteres especiales entre comillas simples. El script pasa la contraseña a `mysql` como argumento; **no usarlo en hosting**. La guía de deploy utiliza el prompt privado `-p`.

En dos terminales, desde la raíz:

```bash
# Terminal 1
source .venv/bin/activate
flask --app src.backend.app run --port 5000 --debug
```

```bash
# Terminal 2
source .venv/bin/activate
flask --app src.frontend.app run --port 5001 --debug
```

Verificar `http://localhost:5000/api/salud` y abrir `http://localhost:5001`. El endpoint de salud **no comprueba MySQL ni TMDB**: probar también la cartelera, login y búsqueda de películas. Las credenciales del seed del [README](../README.md#ejecución) son solo para pruebas locales.

## 6. Errores frecuentes y cuidado de secretos

| Síntoma | Qué revisar |
|---|---|
| MySQL: `Access denied` | Usuario, contraseña, permisos y servidor. Las credenciales de la plantilla son ejemplos. |
| MySQL: `Unknown database` | Crear/importar la base correcta; confirmar `DB_NAME`. |
| MySQL: conexión rechazada | Servidor encendido, host/puerto, red y restricciones del proveedor. |
| `TMDB_NO_DISPONIBLE` | Clave v3 correcta, reinicio, salida HTTPS y disponibilidad del proveedor. |
| `BACKEND_NO_DISPONIBLE` en el sitio | API activa y `BACKEND_URL` accesible **desde el servidor del frontend**. `localhost` allí no es tu computadora. |
| `ValueError` al arrancar | `DB_PORT` y tiempos deben ser enteros. |
| Cambié .env y nada cambió | Reiniciar; revisar variables exportadas/panel, que tienen prioridad sobre el archivo. |
| Sesión inválida después de actualizar | Claves rotadas o instancias con claves diferentes; unificar por servicio y volver a ingresar. |
| No llega el email | Revisar ambas claves de Mailjet, `MAIL_FROM` autorizado, cuota, logs del backend y del proveedor y carpeta de spam. Ver [Correo](#correo-mailjet-por-https); aceptación no significa entrega. |

No imprimir `.env`, subirlo a Git, enviarlo al grupo ni incluirlo en logs. Comprobar sin mostrar su contenido:

```bash
git check-ignore .env
git status --short
```

Si fue versionado por error, quitarlo del seguimiento y rotar **todas** las credenciales expuestas. No subir backups de la base al repositorio: contienen datos de usuarios y hashes de contraseñas.
