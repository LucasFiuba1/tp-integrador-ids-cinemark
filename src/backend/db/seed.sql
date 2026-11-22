-- Cine Paradiso: datos de prueba (SCRUM-37).
-- Ejecutar después de schema.sql: mysql -u <usuario> -p < src/backend/db/seed.sql (o bash init.sh --db).
-- Las fechas son relativas al día en que se carga (CURDATE()), así siempre hay funciones pasadas y futuras.
-- Además hay una cartelera fija desde el 2/12/2026 (segunda entrega): funciones a las 19:00 y 22:30 ese día y
-- todos los días del 3/12 al 9/12.
USE cine_paradiso;

-- Período en cartel: desde hace 30 días y, como mínimo, hasta fin de diciembre de 2026.
SET @en_cartel_desde = TIMESTAMP(CURDATE()) - INTERVAL 30 DAY;
SET @en_cartel_hasta = GREATEST(TIMESTAMP(CURDATE()) + INTERVAL 30 DAY + INTERVAL '23:59:59' HOUR_SECOND,
                                TIMESTAMP('2026-12-31 23:59:59'));
SET @segunda_entrega = TIMESTAMP('2026-12-02');

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

-- Clásicos que vuelven a la sala, con su tmdb_id, póster y duración reales de TMDB (desde el backoffice se
-- pueden importar más). Todas están en cartel desde hace 30 días salvo Casablanca (id 8), que se estrena el 2/12
-- (o en 10 días, si eso es antes). Ninguna dura más de 179 minutos: con 15 de limpieza entran entre horarios
-- separados por 210.
INSERT INTO peliculas (tmdb_id, titulo, sinopsis, poster_url, duracion_min, clasificacion, genero,
                       disponible_desde, disponible_hasta) VALUES
(105, 'Volver al futuro',
 'Un adolescente viaja por accidente a 1955 en un auto convertido en máquina del tiempo y tiene que lograr que sus padres se enamoren para poder volver.',
 'https://image.tmdb.org/t/p/w500/owk40tn1sFJmC7bhamEpmhdZPKa.jpg', 116, 'ATP', 'Aventura, Comedia, Ciencia ficción',
 @en_cartel_desde, @en_cartel_hasta),
(238, 'El padrino',
 'El patriarca de una familia de la mafia neoyorquina le cede el poder a su hijo menor, que nunca quiso ser parte del negocio.',
 'https://image.tmdb.org/t/p/w500/5HlLUsmsv60cZVTzVns9ICZD6zU.jpg', 175, '+16', 'Drama, Crimen',
 @en_cartel_desde, @en_cartel_hasta),
(680, 'Tiempos violentos',
 'Las historias de dos sicarios, un boxeador, un gánster y su esposa se cruzan en Los Ángeles.',
 'https://image.tmdb.org/t/p/w500/hNcQAuquJxTxl2fJFs1R42DrWcf.jpg', 154, '+18', 'Thriller, Crimen',
 @en_cartel_desde, @en_cartel_hasta),
(11216, 'Cinema Paradiso',
 'Un director de cine vuelve a su pueblo siciliano y recuerda su infancia junto al proyeccionista de la sala.',
 'https://image.tmdb.org/t/p/w500/hHwsr3t5n7VVUbPyU8VZswn0jkL.jpg', 155, '+13', 'Drama, Romance',
 @en_cartel_desde, @en_cartel_hasta),
(129, 'El viaje de Chihiro',
 'Una nena queda atrapada en un mundo de espíritus y tiene que trabajar en una casa de baños para salvar a sus padres.',
 'https://image.tmdb.org/t/p/w500/2RcxjDykOssx4SfqshewyI9vfSl.jpg', 122, 'ATP', 'Animación, Familia, Fantasía',
 @en_cartel_desde, @en_cartel_hasta),
(862, 'Toy Story',
 'Los juguetes de un chico cobran vida cuando nadie los ve, y la llegada de un astronauta pone celoso al vaquero favorito.',
 'https://image.tmdb.org/t/p/w500/jvn7wy3RSNEXnFSXLpH2of2LcV6.jpg', 77, 'ATP', 'Animación, Aventura, Familia',
 @en_cartel_desde, @en_cartel_hasta),
(329, 'Jurassic Park',
 'Un parque temático con dinosaurios clonados se sale de control durante la visita de un grupo de expertos.',
 'https://image.tmdb.org/t/p/w500/1r8TWaAExHbFRzyqT3Vcbq1XZQb.jpg', 120, '+13', 'Aventura, Ciencia ficción',
 @en_cartel_desde, @en_cartel_hasta),
(289, 'Casablanca',
 'En plena guerra, el dueño de un bar en Marruecos reencuentra a la mujer que lo dejó y tiene que decidir si la ayuda a escapar.',
 'https://image.tmdb.org/t/p/w500/a7EjycGNSYw6QqJqDooD9eQGZ4r.jpg', 102, 'ATP', 'Drama, Romance',
 LEAST(TIMESTAMP(CURDATE()) + INTERVAL 10 DAY, @segunda_entrega), @en_cartel_hasta),
(603, 'Matrix',
 'Un programador que de noche es hacker descubre que el mundo en el que vive es una simulación y se suma a la rebelión contra las máquinas.',
 'https://image.tmdb.org/t/p/w500/8rT9kG2EYkZpJmYCuTJNnPDEube.jpg', 138, '+13', 'Acción, Ciencia ficción',
 @en_cartel_desde, @en_cartel_hasta),
(13, 'Forrest Gump',
 'Un hombre de buen corazón atraviesa sin proponérselo los grandes momentos de la historia de Estados Unidos mientras sigue enamorado de Jenny.',
 'https://image.tmdb.org/t/p/w500/oiqKEhEfxl9knzWXvWecJKN3aj6.jpg', 142, '+13', 'Comedia, Drama, Romance',
 @en_cartel_desde, @en_cartel_hasta),
(157336, 'Interestelar',
 'Un grupo de astronautas cruza un agujero de gusano en busca de un planeta habitable para una humanidad que se está quedando sin futuro.',
 'https://image.tmdb.org/t/p/w500/d1QKiYtceF3GDtxvTFXFAqwwah9.jpg', 169, '+13', 'Aventura, Drama, Ciencia ficción',
 @en_cartel_desde, @en_cartel_hasta),
(98, 'Gladiador',
 'Un general romano traicionado por el nuevo emperador termina convertido en esclavo y pelea en la arena para vengarse.',
 'https://image.tmdb.org/t/p/w500/90QFOG5zSN4cbrIVs4DL4ePAuA5.jpg', 155, '+13', 'Acción, Drama, Aventura',
 @en_cartel_desde, @en_cartel_hasta),
(120, 'El señor de los anillos: La comunidad del anillo',
 'Un joven hobbit recibe un anillo con un poder oscuro y emprende con ocho compañeros el viaje para destruirlo.',
 'https://image.tmdb.org/t/p/w500/9xtH1RmAzQ0rrMBNUMXstb2s3er.jpg', 179, '+13', 'Aventura, Fantasía, Acción',
 @en_cartel_desde, @en_cartel_hasta),
(354912, 'Coco',
 'Un chico que sueña con ser músico entra a la Tierra de los Muertos y busca a su tatarabuelo para volver con su familia.',
 'https://image.tmdb.org/t/p/w500/vwsFGblLYxWBNjg9pdWN1Mm5YfW.jpg', 105, 'ATP', 'Familia, Animación, Música, Aventura',
 @en_cartel_desde, @en_cartel_hasta),
(14160, 'Up: Una aventura de altura',
 'Un viudo ata miles de globos a su casa para volar a Sudamérica, sin saber que un pequeño explorador viaja en el porche.',
 'https://image.tmdb.org/t/p/w500/1N0LtzUueXrlnpL466jQBJ6iAuj.jpg', 96, 'ATP', 'Animación, Comedia, Familia, Aventura',
 @en_cartel_desde, @en_cartel_hasta),
(496243, 'Parásitos',
 'Una familia pobre se infiltra de a uno como empleados en la casa de una familia rica, hasta que aparece un secreto en el sótano.',
 'https://image.tmdb.org/t/p/w500/4N55tgxDW0RRATyrZHbx0q9HUKv.jpg', 132, '+13', 'Comedia, Suspenso, Drama',
 @en_cartel_desde, @en_cartel_hasta),
(27205, 'El origen',
 'Un ladrón que roba secretos dentro de los sueños acepta un último trabajo: implantar una idea en la mente de un empresario.',
 'https://image.tmdb.org/t/p/w500/tXQvtRWfkUUnWJAn2tN3jERIUG.jpg', 148, '+13', 'Acción, Ciencia ficción, Crimen',
 @en_cartel_desde, @en_cartel_hasta),
(808, 'Shrek',
 'Un ogro que solo quiere estar tranquilo en su pantano acepta rescatar a una princesa, acompañado por un burro que no para de hablar.',
 'https://image.tmdb.org/t/p/w500/jTQONM7jt1yv2lL972TtmWO0UIZ.jpg', 92, 'ATP', 'Animación, Comedia, Fantasía, Aventura, Familia',
 @en_cartel_desde, @en_cartel_hasta),
(12, 'Buscando a Nemo',
 'Un pez payaso muy miedoso cruza el océano para rescatar a su hijo, que terminó en la pecera de un dentista en Sídney.',
 'https://image.tmdb.org/t/p/w500/jPhak722pNGxQIXSEfeWIUqBrO5.jpg', 100, 'ATP', 'Animación, Familia, Aventura',
 @en_cartel_desde, @en_cartel_hasta),
(155, 'Batman: El caballero de la noche',
 'Batman, el comisionado Gordon y el fiscal Harvey Dent enfrentan al Joker, un criminal que quiere hundir a Ciudad Gótica en el caos.',
 'https://image.tmdb.org/t/p/w500/8QDQExnfNFOtabLDKqfDQuHDsIg.jpg', 152, '+13', 'Acción, Suspenso, Crimen',
 @en_cartel_desde, @en_cartel_hasta),
(601, 'E.T., el extraterrestre',
 'Un chico esconde en su casa a un extraterrestre que quedó varado en la Tierra y lo ayuda a volver a su planeta.',
 'https://image.tmdb.org/t/p/w500/ojvKem8WUzRK5PLvO7wTuAFinnz.jpg', 115, 'ATP', 'Aventura, Ciencia ficción, Familia',
 @en_cartel_desde, @en_cartel_hasta),
(2062, 'Ratatouille',
 'Una rata con talento para la cocina se esconde bajo el gorro de un ayudante torpe para cumplir su sueño de ser chef en París.',
 'https://image.tmdb.org/t/p/w500/nGUelOVetiRpY2wTBMHTbrTIGYC.jpg', 111, 'ATP', 'Animación, Comedia, Familia, Fantasía',
 @en_cartel_desde, @en_cartel_hasta);

-- Funciones: en cada sala, de anteayer a dentro de 9 días (sin llegar al 2/12), a las 14:00, 17:30 y 21:00.
-- Entre una y otra hay 210 minutos y la película más larga dura 179 + 15 de limpieza, así no se superponen. La
-- película va rotando entre las 7 primeras (el + 9 evita un MOD negativo con los días pasados). La Sala VIP es
-- más cara.
INSERT INTO funciones (pelicula_id, sala_id, fecha_hora, precio)
WITH RECURSIVE dias (d) AS (
    SELECT -2 UNION ALL SELECT d + 1 FROM dias WHERE d < 9
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
WHERE TIMESTAMP(CURDATE()) + INTERVAL dias.d DAY < @segunda_entrega
ORDER BY s.id, dias.d, horarios.orden;

-- 2/12 a la noche: en cada sala a las 19:00 y a las 22:30, diez películas distintas (Casablanca y las nuevas,
-- ids 8 a 17).
INSERT INTO funciones (pelicula_id, sala_id, fecha_hora, precio)
WITH horarios (orden, minutos) AS (
    SELECT 0, 19 * 60 UNION ALL SELECT 1, 22 * 60 + 30
)
SELECT 8 + (s.id - 1) * 2 + horarios.orden,
       s.id,
       @segunda_entrega + INTERVAL horarios.minutos MINUTE,
       IF(s.nombre = 'Sala VIP', 9000.00, 5500.00)
FROM salas s
CROSS JOIN horarios
ORDER BY s.id, horarios.orden;

-- Del 3/12 al 9/12: en cada sala a las 14:00, 17:30 y 21:00, rotando entre las 22 películas. En cada horario las
-- 5 salas dan películas distintas y de un día al otro la rotación avanza 15 lugares.
INSERT INTO funciones (pelicula_id, sala_id, fecha_hora, precio)
WITH RECURSIVE dias (d) AS (
    SELECT 1 UNION ALL SELECT d + 1 FROM dias WHERE d < 7
),
horarios (orden, minutos) AS (
    SELECT 0, 14 * 60 UNION ALL SELECT 1, 17 * 60 + 30 UNION ALL SELECT 2, 21 * 60
)
SELECT 1 + MOD(dias.d * 15 + horarios.orden * 5 + s.id - 1, 22),
       s.id,
       @segunda_entrega + INTERVAL dias.d DAY + INTERVAL horarios.minutos MINUTE,
       IF(s.nombre = 'Sala VIP', 9000.00, 5500.00)
FROM salas s
CROSS JOIN dias
CROSS JOIN horarios
ORDER BY dias.d, horarios.orden, s.id;

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

-- Validaciones de ingreso de las funciones de ayer (SCRUM-125).
INSERT INTO validaciones_ingreso (compra_id, funcion_id, resultado, fecha_hora) VALUES
(1, @funcion_pasada, 'valida', @ayer_21 - INTERVAL 12 MINUTE),
(1, @funcion_pasada, 'ya_utilizada', @ayer_21 - INTERVAL 10 MINUTE),
(2, @funcion_pasada_belgrano, 'valida', @ayer_1730 - INTERVAL 8 MINUTE);
