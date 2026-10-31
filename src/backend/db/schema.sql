-- Cine Paradiso: creación de la base de datos.
-- Ejecutar: mysql -u <usuario> -p < src/backend/sql/schema.sql
-- Re-ejecutable: borra y vuelve a crear todas las tablas.
-- Todas las fechas y horas se guardan en un único campo DATETIME.

CREATE DATABASE IF NOT EXISTS cine_paradiso CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE cine_paradiso;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS compra_servicios;
DROP TABLE IF EXISTS entradas;
DROP TABLE IF EXISTS compras;
DROP TABLE IF EXISTS servicios;
DROP TABLE IF EXISTS funciones;
DROP TABLE IF EXISTS peliculas;
DROP TABLE IF EXISTS butacas;
DROP TABLE IF EXISTS salas;
DROP TABLE IF EXISTS locales;
DROP TABLE IF EXISTS usuarios;
SET FOREIGN_KEY_CHECKS = 1;

-- Clientes y administradores. Las contraseñas se guardan con hash.
CREATE TABLE usuarios (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    nombre        VARCHAR(100) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    rol           ENUM('cliente', 'admin') NOT NULL DEFAULT 'cliente',
    creado_en     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Los 3 centros de entretenimiento de Cine Paradiso.
CREATE TABLE locales (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    nombre    VARCHAR(100) NOT NULL UNIQUE,
    direccion VARCHAR(200) NOT NULL UNIQUE
);

-- Cada sala pertenece a un local. Capacidad = filas x columnas.
CREATE TABLE salas (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    local_id INT NOT NULL,
    nombre   VARCHAR(50) NOT NULL,
    filas    TINYINT UNSIGNED NOT NULL,
    columnas TINYINT UNSIGNED NOT NULL,
    activa   BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE KEY uq_sala_local (local_id, nombre),
    FOREIGN KEY (local_id) REFERENCES locales (id)
);

-- Butacas de cada sala, identificadas por fila (letra) y número.
CREATE TABLE butacas (
    id      INT AUTO_INCREMENT PRIMARY KEY,
    sala_id INT NOT NULL,
    fila    CHAR(2) NOT NULL,
    numero  TINYINT UNSIGNED NOT NULL,
    UNIQUE KEY uq_butaca (sala_id, fila, numero),
    FOREIGN KEY (sala_id) REFERENCES salas (id) ON DELETE CASCADE
);

-- Catálogo importado desde TMDB, con el período en que está disponible.
CREATE TABLE peliculas (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    tmdb_id          INT NOT NULL UNIQUE,
    titulo           VARCHAR(200) NOT NULL,
    sinopsis         TEXT,
    poster_url       VARCHAR(300),
    duracion_min     SMALLINT UNSIGNED NOT NULL,
    clasificacion    VARCHAR(10),
    genero           VARCHAR(50) NOT NULL,
    disponible_desde DATETIME NOT NULL,
    disponible_hasta DATETIME NOT NULL,
    activa           BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (disponible_hasta > disponible_desde)
);

-- Una función es una película en una sala, en una fecha y hora puntual.
CREATE TABLE funciones (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    pelicula_id INT NOT NULL,
    sala_id     INT NOT NULL,
    fecha_hora  DATETIME NOT NULL,
    precio      DECIMAL(10, 2) NOT NULL,
    activa      BOOLEAN NOT NULL DEFAULT TRUE,
    INDEX idx_funcion_sala_fecha (sala_id, fecha_hora),
    FOREIGN KEY (pelicula_id) REFERENCES peliculas (id),
    FOREIGN KEY (sala_id) REFERENCES salas (id),
    CHECK (precio > 0)
);

-- Productos adicionales (comida, bebidas, estacionamiento, VIP...). Valen para todas las salas.
CREATE TABLE servicios (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    nombre      VARCHAR(100) NOT NULL UNIQUE,
    descripcion VARCHAR(255),
    precio      DECIMAL(10, 2) NOT NULL,
    activo      BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (precio > 0)
);

-- Una compra es de un cliente para una función. El token firmado va dentro del QR.
CREATE TABLE compras (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id    INT NOT NULL,
    funcion_id    INT NOT NULL,
    estado        ENUM('pendiente', 'confirmada', 'cancelada', 'vencida') NOT NULL DEFAULT 'pendiente',
    total         DECIMAL(10, 2) NOT NULL DEFAULT 0,
    token_qr      VARCHAR(255) UNIQUE,
    creada_en     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    vence_en      DATETIME NOT NULL,
    confirmada_en DATETIME NULL,
    cancelada_en  DATETIME NULL,
    utilizada_en  DATETIME NULL,
    INDEX idx_compra_usuario (usuario_id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
    FOREIGN KEY (funcion_id) REFERENCES funciones (id)
);

-- Una entrada es una butaca vendida dentro de una compra.
-- Regla crítica: una butaca no se vende dos veces en la misma función.
-- "activa" vale 1 mientras la compra está vigente y NULL cuando se cancela o vence:
-- MySQL permite varios NULL en un UNIQUE, así la butaca se puede volver a vender
-- sin perder el historial.
CREATE TABLE entradas (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    compra_id  INT NOT NULL,
    funcion_id INT NOT NULL,
    butaca_id  INT NOT NULL,
    precio     DECIMAL(10, 2) NOT NULL,
    activa     TINYINT NULL DEFAULT 1,
    UNIQUE KEY uq_butaca_por_funcion (funcion_id, butaca_id, activa),
    FOREIGN KEY (compra_id) REFERENCES compras (id) ON DELETE CASCADE,
    FOREIGN KEY (funcion_id) REFERENCES funciones (id),
    FOREIGN KEY (butaca_id) REFERENCES butacas (id),
    CHECK (activa IS NULL OR activa = 1)
);

-- Servicios agregados a una compra, con el precio vigente al momento de comprar.
CREATE TABLE compra_servicios (
    compra_id       INT NOT NULL,
    servicio_id     INT NOT NULL,
    cantidad        SMALLINT UNSIGNED NOT NULL,
    precio_unitario DECIMAL(10, 2) NOT NULL,
    PRIMARY KEY (compra_id, servicio_id),
    FOREIGN KEY (compra_id) REFERENCES compras (id) ON DELETE CASCADE,
    FOREIGN KEY (servicio_id) REFERENCES servicios (id),
    CHECK (cantidad > 0)
);
