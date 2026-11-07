# Despliegue gratuito para demostraciones

El frontend Flask/Jinja y la API Flask se publican como **dos Web Services Free
de Render**. La base se aloja en **una instancia Free de TiDB Cloud Starter**,
compatible con el protocolo MySQL. No se cambia el motor de la aplicación a
PostgreSQL ni se guardan datos en el disco efímero de Render.

## Evitar cargos

- Usar una cuenta/workspace sin tarjeta ni método de pago. Si ya tiene uno,
  revisar sus condiciones de facturación antes de crear recursos.
- Ambos servicios del `render.yaml` tienen `plan: free` explícito. No agregar
  discos, cron jobs ni servicios privados: no están incluidos en este deploy.
- En TiDB elegir **Starter → Free**, nunca **Scalable** ni un trial de otro plan.
  Si solicita una tarjeta, detenerse.
- No activar upgrades automáticos, monitoreo externo para mantener despiertos
  los servicios ni despliegues de previews.
- El blueprint desactiva los despliegues automáticos; los siguientes se lanzan
  manualmente desde el panel.

Las condiciones de los proveedores pueden cambiar. Antes de crear recursos,
confirmar el importe **$0** en ambos paneles. Referencias verificadas el
7 de noviembre de 2026:

- [Render Free: límites y suspensión](https://render.com/docs/free).
- [TiDB Starter: cuota gratuita y throttling](https://www.pingcap.com/tidb-cloud-starter-pricing-details/).
- [Especificación del blueprint](https://render.com/docs/blueprint-spec).

## 1. Base remota vacía

1. Crear una instancia **Free** de TiDB Cloud Starter. En su sección de conexión,
   obtener host, puerto, usuario y contraseña. No guardar estos valores en Git.
2. Crear una base `cine_paradiso` usando la consola SQL del proveedor, si el
   usuario tiene permiso, y cargar `src/backend/db/schema.sql`.
   **El schema contiene operaciones destructivas: usar solo una base nueva,
   vacía y dedicada a esta demostración**, nunca una base con datos existentes.
3. Si el proveedor asigna otro nombre de base, trabajar sobre esa base y adaptar
   las instrucciones `CREATE DATABASE` y `USE` en una copia temporal del SQL.
   Configurar `DB_NAME` con el nombre real. No cambiar los archivos originales
   ni deshabilitar TLS para resolver un error de conexión.
4. El seed es opcional. No cargar datos personales reales. Para una demo pública,
   reemplazar en una copia temporal los hashes de las contraseñas de prueba
   antes de importar `src/backend/db/seed.sql`: las contraseñas originales son
   públicas y permiten entrar al backoffice. Generar los hashes con
   `werkzeug.security.generate_password_hash(..., method="pbkdf2:sha256")`.
5. Comprobar la importación completa y las restricciones SQL. La compatibilidad
   del esquema y del seed debe validarse contra la instancia real, no solo por
   el hecho de que el servicio acepte conexiones MySQL.

No ejecutar `bash init.sh --db` contra la base remota: ese comando está pensado
para desarrollo local y no configura TLS verificado.

## 2. Publicar la API y el sitio

1. Subir a GitHub una rama que incluya `render.yaml` y `requirements-deploy.txt`.
   No subir `.env`, contraseñas ni tokens. No hace falta cambiar `main` o
   `develop` para desplegar una rama de prueba.
2. En Render, crear un **Blueprint** desde ese repositorio y seleccionar esa
   rama. Revisar que los dos servicios figuren como **Free / $0** antes de
   confirmar. Mantener la raíz del repositorio como directorio de trabajo.
3. Completar las variables del backend:
   - `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`: conexión real de
     TiDB, no `localhost` ni credenciales de desarrollo.
   - `DB_SSL=true`: el blueprint ya lo define; verifica certificado y hostname.
   - `TMDB_API_KEY`: clave de TMDB si se usará la importación de películas.
     Puede quedar vacía para una demo que solo use películas ya cargadas.
4. Completar `BACKEND_URL` del frontend con la URL **pública HTTPS** de la API,
   sin `/api` al final. Render puede agregar un sufijo al nombre del servicio;
   copiar la URL real del panel y corregir la variable si hace falta.
5. Render genera `SECRET_KEY` y `FRONTEND_SECRET_KEY`. Mantenerlas estables entre
   deploys para no invalidar sesiones y tokens. No imprimirlas ni versionarlas.
6. Desplegar ambos servicios. Los comandos de build y arranque usan Gunicorn
   y el puerto asignado por Render, sin `flask run --debug`.

Para crearlos manualmente en vez de usar un Blueprint, copiar los comandos y
variables de `render.yaml` en cada Web Service, seleccionar **Free** y generar
claves secretas fuertes. Luego verificar la URL real del backend.

## 3. Verificación real

- `GET https://<api>/api/salud` debe responder `200` con `{"estado":"ok"}`.
  Esta ruta no consulta MySQL: por sí sola **no verifica la base**.
- Abrir el sitio y comprobar que carga la cartelera desde la base remota.
- Probar login y cierre de sesión con un usuario exclusivo de la demo.
- Verificar que `/admin` no sea accesible sin una sesión con rol administrador.
- Esperar a que los servicios se duerman y verificar la primera visita:
  puede tardar alrededor de un minuto. El frontend permite 90 segundos de
  espera por petición al backend; no reintenta automáticamente compras.

Checks locales, que no sustituyen esta verificación remota:

```bash
python -m pytest src/tests -q
```

## Limitaciones del plan gratuito

- Render duerme cada servicio tras 15 minutos de inactividad. Las **750 horas
  mensuales son compartidas por el workspace**, no por cada servicio; mantener
  los dos despiertos todo el mes excede esa cuota. Sin método de pago, los
  excesos de transferencia/builds suspenden servicios o nuevos builds en vez
  de generar cargos. Render también puede suspender por tráfico saliente alto.
- TiDB Free limita almacenamiento y Request Units; al agotar la cuota aplica
  throttling. No convertir la instancia a Scalable para resolverlo sin revisar
  costos y obtener autorización.
- Render Free bloquea SMTP en los puertos 25, 465 y 587. **Los emails de compra
  no quedan operativos con la configuración SMTP habitual**. No afirmar que
  el flujo completo de compra funciona hasta verificar cómo maneja la app esa
  limitación. Un proveedor de email por HTTPS requeriría otra integración.
- Esto es un deploy de demostración, no una garantía de disponibilidad para
  producción. No usarlo para ventas reales.
