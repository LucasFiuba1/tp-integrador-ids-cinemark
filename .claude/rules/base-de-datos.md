---
paths:
  - "src/backend/db/**"
  - "src/backend/db.py"
  - "src/backend/services/**/*.py"
---

# Base de datos (MySQL, sin ORM)

- **Prohibido** SQLAlchemy, SQLModel, Peewee o cualquier ORM, y también clases Python que representen tablas.
  Las filas viajan como `dict` (el cursor es `DictCursor`). Tampoco clases de ningún otro tipo: el proyecto no usa
  programación orientada a objetos (ver `CLAUDE.md`).
- Acceso solo por `src/backend/db.py`: `consultar`, `consultar_uno`, `ejecutar`, `transaccion()`.
- Parámetros siempre con `%s` y tupla: `consultar_uno("SELECT ... WHERE id = %s", (id,))`.
  Nunca f-strings, `%` ni `+` con valores del usuario. Concatenar solo constantes del código (como `COLUMNAS`).
- Un único campo `DATETIME` para fecha y hora (`fecha_hora`, `vence_en`, `disponible_desde`…). Nunca `DATE` + `TIME`.
- Concurrencia: reservar butacas dentro de `transaccion()`; ante `pymysql.err.IntegrityError` por la clave única
  de `entradas` devolver 409 `BUTACA_OCUPADA`. Liberar butacas poniendo `entradas.activa = NULL`.
- Bajas lógicas (`activa = FALSE` / `activo = FALSE`) si hay historial; física solo si no hay referencias.
- Dashboards con `JOIN` + `GROUP BY` en SQL, no agregando en Python.
- Cambios de esquema: editar `src/backend/db/schema.sql` (es re-ejecutable: borra y crea) y, si hace falta,
  `seed.sql`; actualizar el diagrama y las tablas de `docs/base_de_datos.md` en el mismo PR.
- Nombres en español y `snake_case`, tablas en plural, FK `<entidad>_id`.
- **No levantar otras instancias de `mysqld`** (en el scratchpad, `/tmp` ni otro puerto). Las pruebas no usan MySQL;
  para probar a mano usar el MySQL local que ya corre (puerto 3306), con una base aparte si hace falta aislamiento.
  Una instancia temporal que sobrevive a la sesión puede escribir su log sin parar y llenar el disco.
