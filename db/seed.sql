-- Cine Paradiso: datos iniciales mínimos.
-- Ejecutar después de schema.sql: mysql -u <usuario> -p < db/seed.sql
-- La carga completa de prueba (películas, funciones, compras) se completa en el Hito 2 (SCRUM-37).
USE cine_paradiso;

-- Administrador inicial. Email: admin@cineparadiso.com / Contraseña: admin1234 (cambiar en producción)
INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES
('Administrador', 'admin@cineparadiso.com',
 'scrypt:32768:8:1$doHaRPNpm9vdwO4P$bb1cba2d88821535989740ef7b4c09b4e01eeaeff1a37e67a3e1451ff6734d0c2ab9a1d0c40825f37967bb50c95a584e3c4a279968ed294487cfdd2195db3f13',
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
SELECT s.id, CHAR(64 + f.n), c.n
FROM salas s
JOIN numeros f ON f.n <= s.filas
JOIN numeros c ON c.n <= s.columnas;

-- Servicios disponibles para todas las salas.
INSERT INTO servicios (nombre, descripcion, precio) VALUES
('Combo pochoclos grande', 'Pochoclos grandes y gaseosa de 500 ml', 6500.00),
('Gaseosa', 'Gaseosa de 500 ml', 2500.00),
('Estacionamiento', 'Estacionamiento durante la función', 3000.00),
('Acceso VIP', 'Butaca reclinable y servicio en sala', 8000.00);
