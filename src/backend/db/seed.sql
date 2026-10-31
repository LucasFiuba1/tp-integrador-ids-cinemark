-- Cine Paradiso: datos iniciales mínimos.
-- Ejecutar después de schema.sql: mysql -u <usuario> -p < src/backend/db/seed.sql
-- La carga completa de prueba (películas, funciones, compras) se completa en el Hito 2 (SCRUM-37).
USE cine_paradiso;

-- Administrador inicial. Email: admin@cineparadiso.com / Contraseña: admin1234 (cambiar en producción)
-- Hash pbkdf2:sha256 (no scrypt): el Python de macOS no trae hashlib.scrypt.
INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES
('Administrador', 'admin@cineparadiso.com',
 'pbkdf2:sha256:1000000$Qy0iQ4Ie6vonin9r$14235bb09ae665dc0d551c0a54f3a155b5c8f50ea03bd7c91bb7400dedf3e927',
 'admin');

-- Los 3 locales del enunciado.
INSERT INTO locales (nombre, direccion) VALUES
('Paradiso Centro',   'Av. Corrientes 1234, CABA'),
('Paradiso Belgrano', 'Av. Cabildo 2050, CABA'),
('Paradiso Palermo',  'Av. Santa Fe 3300, CABA');

-- Salas de capacidades distintas.
INSERT INTO salas (local_id, nombre, filas, columnas) VALUES
(1, 'Sala 1', 8, 12),
(1, 'Sala 2', 6, 10),
(2, 'Sala 1', 10, 14),
(3, 'Sala 1', 7, 10),
(3, 'Sala VIP', 4, 8);

-- Butacas: una por cada fila (A, B, C...) y número de cada sala.
INSERT INTO butacas (sala_id, fila, numero)
WITH RECURSIVE numeros (n) AS (
    SELECT 1 UNION ALL SELECT n + 1 FROM numeros WHERE n < 26
)
SELECT s.id, CHAR(64 + f.n USING utf8mb4), c.n
FROM salas s
JOIN numeros f ON f.n <= s.filas
JOIN numeros c ON c.n <= s.columnas;

-- Servicios disponibles para todas las salas.
INSERT INTO servicios (nombre, descripcion, precio) VALUES
('Combo pochoclos grande', 'Pochoclos grandes y gaseosa de 500 ml', 6500.00),
('Gaseosa', 'Gaseosa de 500 ml', 2500.00),
('Estacionamiento', 'Estacionamiento durante la función', 3000.00),
('Acceso VIP', 'Butaca reclinable y servicio en sala', 8000.00);
