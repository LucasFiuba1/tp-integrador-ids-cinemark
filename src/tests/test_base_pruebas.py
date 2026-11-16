"""Configuración de la base MySQL de pruebas, sin MySQL (SCRUM-78).

Comprueba que nunca se pueda apuntar las pruebas a una base de trabajo y que los scripts se separen bien.
"""
import pytest

from src.tests import mysql_pruebas


@pytest.fixture
def sin_archivos(tmp_path, monkeypatch):
    """Ni .env.test ni .env: la configuración sale solo de las variables de entorno de cada prueba."""
    monkeypatch.setattr(mysql_pruebas, "ARCHIVO_CONFIG", tmp_path / ".env.test")
    monkeypatch.setattr(mysql_pruebas, "RAIZ", tmp_path)
    for clave in mysql_pruebas.CLAVES:
        monkeypatch.delenv(clave, raising=False)
    return tmp_path


def test_sin_puerto_no_hay_base_de_pruebas(sin_archivos):
    assert mysql_pruebas.leer_config() is None


def test_config_por_defecto_es_local_con_nombre_test(sin_archivos, monkeypatch):
    monkeypatch.setenv("PRUEBAS_DB_PORT", "3317")
    assert mysql_pruebas.leer_config() == {
        "DB_HOST": "127.0.0.1", "DB_PORT": 3317, "DB_USER": "root", "DB_PASSWORD": "",
        "DB_NAME": "cine_paradiso_test", "DB_SSL": False,
    }


def test_el_archivo_env_test_se_lee_y_el_entorno_lo_pisa(sin_archivos, monkeypatch):
    (sin_archivos / ".env.test").write_text("PRUEBAS_DB_PORT=3306\nPRUEBAS_DB_USER=cine\nPRUEBAS_DB_NAME=otra_test\n")
    monkeypatch.setenv("PRUEBAS_DB_PORT", "3399")
    config = mysql_pruebas.leer_config()
    assert (config["DB_PORT"], config["DB_USER"], config["DB_NAME"]) == (3399, "cine", "otra_test")


@pytest.mark.parametrize("nombre", ["cine_paradiso", "test", "Cine_test", "cine-paradiso_test", "x_test; DROP"])
def test_nombre_que_no_termina_en_test_se_rechaza(sin_archivos, monkeypatch, nombre):
    monkeypatch.setenv("PRUEBAS_DB_PORT", "3317")
    monkeypatch.setenv("PRUEBAS_DB_NAME", nombre)
    with pytest.raises(ValueError):
        mysql_pruebas.leer_config()


def test_la_base_de_desarrollo_nunca_es_la_de_pruebas(sin_archivos, monkeypatch):
    (sin_archivos / ".env").write_text("DB_NAME=cine_paradiso_test\n")
    monkeypatch.setenv("PRUEBAS_DB_PORT", "3317")
    with pytest.raises(ValueError):
        mysql_pruebas.leer_config()


def test_sentencias_de_saca_comentarios_y_corta_en_cada_punto_y_coma():
    script = (
        "-- comentario; con punto y coma\n"
        "USE cine_paradiso;\n"
        "INSERT INTO locales (nombre, direccion) VALUES\n"
        "('A', 'Calle 1'),\n"
        "    -- comentario en el medio\n"
        "('B', 'Calle 2');\n"
        "\n"
    )
    assert mysql_pruebas.sentencias_de(script) == [
        "USE cine_paradiso",
        "INSERT INTO locales (nombre, direccion) VALUES\n('A', 'Calle 1'),\n('B', 'Calle 2')",
    ]


def test_los_scripts_reales_se_separan_en_sentencias_completas():
    """Ninguna sentencia de schema.sql ni seed.sql queda partida ni vacía."""
    for script in mysql_pruebas.SCRIPTS:
        sentencias = mysql_pruebas.sentencias_de(script.read_text(encoding="utf-8"))
        assert sentencias
        assert all(sentencia.count("(") == sentencia.count(")") for sentencia in sentencias), script.name
