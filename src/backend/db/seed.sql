-- Cine Paradiso: datos de prueba (SCRUM-37).
-- Ejecutar después de schema.sql: mysql -u <usuario> -p < src/backend/db/seed.sql (o bash init.sh --db).
-- Las fechas son relativas al día en que se carga (CURDATE()), así siempre hay funciones pasadas y futuras.
USE cine_paradiso;

-- Usuarios de prueba (cambiar en producción). Hash pbkdf2:sha256 (no scrypt): el Python de macOS no trae
-- hashlib.scrypt.
--   Administrador: admin@cineparadiso.com / admin1234
--   Clientes:      ana@mail.com y juan@mail.com / cliente1234
INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES
('Administrador', 'admin@cineparadiso.com',
 'pbkdf2:sha256:1000000$Qy0iQ4Ie6vonin9r$14235bb09ae665dc0d551c0a54f3a155b5c8f50ea03bd7c91bb7400dedf3e927',
 'admin'),
('Ana Pérez', 'ana@mail.com',
 'pbkdf2:sha256:1000000$lXZJccIPnBkN2V4o$43dc7e6c0f9bbcc6785c98b724ddd35debbe0cbb79cd9e11407cee8467b3c012',
 'cliente'),
('Juan Gómez', 'juan@mail.com',
 'pbkdf2:sha256:1000000$lXZJccIPnBkN2V4o$43dc7e6c0f9bbcc6785c98b724ddd35debbe0cbb79cd9e11407cee8467b3c012',
 'cliente');

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

-- Clásicos que vuelven a la sala, con su tmdb_id real (desde el backoffice se pueden importar más con póster).
-- Las 7 primeras están en cartel durante 60 días alrededor de hoy; Casablanca se estrena en 10 días y todavía
-- no tiene funciones.
INSERT INTO peliculas (tmdb_id, titulo, sinopsis, poster_url, duracion_min, clasificacion, genero,
                       disponible_desde, disponible_hasta) VALUES
(105, 'Volver al futuro',
 'Un adolescente viaja por accidente a 1955 en un auto convertido en máquina del tiempo y tiene que lograr que sus padres se enamoren para poder volver.',
 NULL, 116, 'ATP', 'Aventura, Comedia, Ciencia ficción',
 TIMESTAMP(CURDATE()) - INTERVAL 30 DAY, TIMESTAMP(CURDATE()) + INTERVAL 30 DAY + INTERVAL '23:59:59' HOUR_SECOND),
(238, 'El padrino',
 'El patriarca de una familia de la mafia neoyorquina le cede el poder a su hijo menor, que nunca quiso ser parte del negocio.',
 NULL, 175, '+16', 'Drama, Crimen',
 TIMESTAMP(CURDATE()) - INTERVAL 30 DAY, TIMESTAMP(CURDATE()) + INTERVAL 30 DAY + INTERVAL '23:59:59' HOUR_SECOND),
(680, 'Tiempos violentos',
 'Las historias de dos sicarios, un boxeador, un gánster y su esposa se cruzan en Los Ángeles.',
 NULL, 154, '+18', 'Thriller, Crimen',
 TIMESTAMP(CURDATE()) - INTERVAL 30 DAY, TIMESTAMP(CURDATE()) + INTERVAL 30 DAY + INTERVAL '23:59:59' HOUR_SECOND),
(11216, 'Cinema Paradiso',
 'Un director de cine vuelve a su pueblo siciliano y recuerda su infancia junto al proyeccionista de la sala.',
 NULL, 155, '+13', 'Drama, Romance',
 TIMESTAMP(CURDATE()) - INTERVAL 30 DAY, TIMESTAMP(CURDATE()) + INTERVAL 30 DAY + INTERVAL '23:59:59' HOUR_SECOND),
(129, 'El viaje de Chihiro',
 'Una nena queda atrapada en un mundo de espíritus y tiene que trabajar en una casa de baños para salvar a sus padres.',
 NULL, 125, 'ATP', 'Animación, Familia, Fantasía',
 TIMESTAMP(CURDATE()) - INTERVAL 30 DAY, TIMESTAMP(CURDATE()) + INTERVAL 30 DAY + INTERVAL '23:59:59' HOUR_SECOND),
(862, 'Toy Story',
 'Los juguetes de un chico cobran vida cuando nadie los ve, y la llegada de un astronauta pone celoso al vaquero favorito.',
 NULL, 81, 'ATP', 'Animación, Aventura, Familia',
 TIMESTAMP(CURDATE()) - INTERVAL 30 DAY, TIMESTAMP(CURDATE()) + INTERVAL 30 DAY + INTERVAL '23:59:59' HOUR_SECOND),
(329, 'Jurassic Park',
 'Un parque temático con dinosaurios clonados se sale de control durante la visita de un grupo de expertos.',
 NULL, 127, '+13', 'Aventura, Ciencia ficción',
 TIMESTAMP(CURDATE()) - INTERVAL 30 DAY, TIMESTAMP(CURDATE()) + INTERVAL 30 DAY + INTERVAL '23:59:59' HOUR_SECOND),
(289, 'Casablanca',
 'En plena guerra, el dueño de un bar en Marruecos reencuentra a la mujer que lo dejó y tiene que decidir si la ayuda a escapar.',
 NULL, 102, 'ATP', 'Drama, Romance',
 TIMESTAMP(CURDATE()) + INTERVAL 10 DAY, TIMESTAMP(CURDATE()) + INTERVAL 60 DAY + INTERVAL '23:59:59' HOUR_SECOND);

-- Funciones: en cada sala, de anteayer a dentro de 6 días, a las 14:00, 17:30 y 21:00. Entre una y otra hay
-- 210 minutos y la película más larga dura 175 + 15 de limpieza, así no se superponen. La película va rotando
-- entre las 7 en cartel (el + 9 evita un MOD negativo con los días pasados). La Sala VIP es más cara.
INSERT INTO funciones (pelicula_id, sala_id, fecha_hora, precio)
WITH RECURSIVE dias (d) AS (
    SELECT -2 UNION ALL SELECT d + 1 FROM dias WHERE d < 6
),
horarios (orden, minutos) AS (
    SELECT 0, 14 * 60 UNION ALL SELECT 1, 17 * 60 + 30 UNION ALL SELECT 2, 21 * 60
)
SELECT 1 + MOD(s.id + dias.d + horarios.orden + 9, 7),
       s.id,
       TIMESTAMP(CURDATE()) + INTERVAL dias.d DAY + INTERVAL horarios.minutos MINUTE,
       IF(s.nombre = 'Sala VIP', 9000.00, 5500.00)
FROM salas s
CROSS JOIN dias
CROSS JOIN horarios
ORDER BY s.id, dias.d, horarios.orden;

-- Compras de ejemplo para el perfil, las películas vistas y los dashboards. No tienen token_qr: el QR firmado
-- lo genera el backend al confirmar (SCRUM-4) con la SECRET_KEY de cada .env.
SET @ayer_1730 = TIMESTAMP(CURDATE()) - INTERVAL 1 DAY + INTERVAL 17 * 60 + 30 MINUTE;
SET @ayer_21 = TIMESTAMP(CURDATE()) - INTERVAL 1 DAY + INTERVAL 21 * 60 MINUTE;
SET @manana_21 = TIMESTAMP(CURDATE()) + INTERVAL 1 DAY + INTERVAL 21 * 60 MINUTE;
SET @funcion_pasada = (SELECT id FROM funciones WHERE sala_id = 1 AND fecha_hora = @ayer_21);
SET @funcion_pasada_belgrano = (SELECT id FROM funciones WHERE sala_id = 3 AND fecha_hora = @ayer_1730);
SET @funcion_futura = (SELECT id FROM funciones WHERE sala_id = 1 AND fecha_hora = @manana_21);

-- 1. Ana vio una función ayer (QR validado): 2 entradas + 1 combo = 17.500.
INSERT INTO compras (usuario_id, funcion_id, estado, total, creada_en, vence_en, confirmada_en, utilizada_en) VALUES
(2, @funcion_pasada, 'confirmada', 17500.00, @ayer_21 - INTERVAL 2 DAY, @ayer_21 - INTERVAL 2 DAY + INTERVAL 10 MINUTE,
 @ayer_21 - INTERVAL 2 DAY + INTERVAL 4 MINUTE, @ayer_21 - INTERVAL 12 MINUTE);
SET @compra = LAST_INSERT_ID();
INSERT INTO entradas (compra_id, funcion_id, butaca_id, precio)
SELECT @compra, @funcion_pasada, id, 5500.00 FROM butacas WHERE sala_id = 1 AND fila = 'D' AND numero IN (5, 6);
INSERT INTO compra_servicios (compra_id, servicio_id, cantidad, precio_unitario) VALUES (@compra, 1, 1, 6500.00);

-- 2. Juan vio una función ayer en Belgrano (QR validado): 1 entrada + 2 gaseosas = 10.500.
INSERT INTO compras (usuario_id, funcion_id, estado, total, creada_en, vence_en, confirmada_en, utilizada_en) VALUES
(3, @funcion_pasada_belgrano, 'confirmada', 10500.00, @ayer_1730 - INTERVAL 1 DAY,
 @ayer_1730 - INTERVAL 1 DAY + INTERVAL 10 MINUTE, @ayer_1730 - INTERVAL 1 DAY + INTERVAL 3 MINUTE,
 @ayer_1730 - INTERVAL 8 MINUTE);
SET @compra = LAST_INSERT_ID();
INSERT INTO entradas (compra_id, funcion_id, butaca_id, precio)
SELECT @compra, @funcion_pasada_belgrano, id, 5500.00 FROM butacas WHERE sala_id = 3 AND fila = 'F' AND numero = 7;
INSERT INTO compra_servicios (compra_id, servicio_id, cantidad, precio_unitario) VALUES (@compra, 2, 2, 2500.00);

-- 3. Juan compró E7 y E8 para mañana y canceló: sus entradas quedan con activa = NULL y las butacas se liberan.
INSERT INTO compras (usuario_id, funcion_id, estado, total, creada_en, vence_en, confirmada_en, cancelada_en) VALUES
(3, @funcion_futura, 'cancelada', 11000.00, NOW() - INTERVAL 2 DAY, NOW() - INTERVAL 2 DAY + INTERVAL 10 MINUTE,
 NOW() - INTERVAL 2 DAY + INTERVAL 5 MINUTE, NOW() - INTERVAL 1 DAY);
SET @compra = LAST_INSERT_ID();
INSERT INTO entradas (compra_id, funcion_id, butaca_id, precio, activa)
SELECT @compra, @funcion_futura, id, 5500.00, NULL FROM butacas WHERE sala_id = 1 AND fila = 'E' AND numero IN (7, 8);

-- 4. Después, Ana compró esas mismas butacas: el UNIQUE (funcion_id, butaca_id, activa) lo permite porque las de
-- Juan quedaron en NULL. En el mapa de mañana a las 21:00 de la Sala 1 aparecen ocupadas.
INSERT INTO compras (usuario_id, funcion_id, estado, total, creada_en, vence_en, confirmada_en) VALUES
(2, @funcion_futura, 'confirmada', 11000.00, NOW() - INTERVAL 1 HOUR, NOW() - INTERVAL 50 MINUTE,
 NOW() - INTERVAL 55 MINUTE);
SET @compra = LAST_INSERT_ID();
INSERT INTO entradas (compra_id, funcion_id, butaca_id, precio)
SELECT @compra, @funcion_futura, id, 5500.00 FROM butacas WHERE sala_id = 1 AND fila = 'E' AND numero IN (7, 8);
