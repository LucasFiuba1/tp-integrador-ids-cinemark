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
| `HORAS_LIMITE_CANCELACION` | Configuración prevista del límite de cancelación antes de una función. | `2`; entero positivo. En esta versión se lee la variable, pero no hay todavía un flujo completo de cancelación que garantice aplicarla. |

### Frontend

| Variable | Para qué sirve | Valor local / requisito |
|---|---|---|
| `FRONTEND_SECRET_KEY` | Firma la cookie de sesión de Flask: token, rol y nombre del usuario. | Generar otra clave, distinta de `SECRET_KEY`; el default también es inseguro. |
| `BACKEND_URL` | Dirección base a la que el frontend llama desde Python con `requests`. | `http://localhost:5000` en local; en hosting, URL HTTPS real de la API. **Sin `/api` al final**: el cliente agrega las rutas. |

El frontend no se conecta directamente a MySQL ni consulta TMDB. No necesita esas credenciales si se despliega por separado. La cookie está **firmada, no cifrada**: no guardar contraseñas ni claves de servicios en la sesión.

### Correo (SMTP)

| Variable | Para qué sirve | Valor |
|---|---|---|
| `SMTP_HOST` | Servidor de salida de correo. | Por ejemplo, `smtp.gmail.com`; default del código: vacío (no envía y deja un aviso en el log). |
| `SMTP_PORT` | Puerto SMTP. | La plantilla usa `587` (STARTTLS si el servidor lo anuncia); con `465` se usa TLS directo (`SMTP_SSL`). |
| `SMTP_USER` | Usuario/cuenta que envía el correo. | Dirección de correo o usuario entregado por el proveedor. |
| `SMTP_PASSWORD` | Credencial SMTP. | En Gmail, contraseña de aplicación, **no** contraseña normal de la cuenta. |
| `MAIL_FROM` | Dirección que figura como remitente (`From`). | Si se deja vacía, usa `SMTP_USER`. |
| `FRONTEND_URL` | Dirección pública del sitio del cliente (sin `/` al final). | `http://localhost:5001` en local; se usa para el enlace "Cancelar compra" del email y para la URL `/admin/ingreso?token=...` que codifica el QR. |

Para Gmail: activar verificación en dos pasos y crear una [contraseña de aplicación](https://myaccount.google.com/apppasswords). No todas las cuentas permiten hacerlo; ver [ayuda de Google](https://support.google.com/accounts/answer/185833). No pegar esa credencial en issues, chats ni capturas.

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
| `ValueError` al arrancar | `DB_PORT`, `SMTP_PORT` y tiempos deben ser enteros. |
| Cambié .env y nada cambió | Reiniciar; revisar variables exportadas/panel, que tienen prioridad sobre el archivo. |
| Sesión inválida después de actualizar | Claves rotadas o instancias con claves diferentes; unificar por servicio y volver a ingresar. |
| No llega el email | El envío todavía no está implementado; completar SMTP no lo habilita. |

No imprimir `.env`, subirlo a Git, enviarlo al grupo ni incluirlo en logs. Comprobar sin mostrar su contenido:

```bash
git check-ignore .env
git status --short
```

Si fue versionado por error, quitarlo del seguimiento y rotar **todas** las credenciales expuestas. No subir backups de la base al repositorio: contienen datos de usuarios y hashes de contraseñas.
