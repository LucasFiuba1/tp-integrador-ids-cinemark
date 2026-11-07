"""SCRUM-15: TLS opcional hacia MySQL y timeout configurable para el despliegue.

Ninguna prueba necesita MySQL ni servidores levantados: pymysql.connect y requests se simulan.
"""
import ssl
from unittest.mock import Mock, patch

import pytest
import requests

from src.backend import db
from src.backend.config import cargar_configuracion as configuracion_backend
from src.frontend.api_client import llamar
from src.frontend.config import cargar_configuracion as configuracion_frontend


@pytest.fixture
def sin_env(monkeypatch):
    """Evita que el .env local o el entorno cambien los valores por defecto."""
    monkeypatch.setattr("src.backend.config.load_dotenv", lambda: None)
    monkeypatch.setattr("src.frontend.config.load_dotenv", lambda: None)
    for nombre in ("DB_SSL", "BACKEND_TIMEOUT"):
        monkeypatch.delenv(nombre, raising=False)
    return monkeypatch


def test_config_backend_sin_db_ssl_devuelve_false(sin_env):
    assert configuracion_backend()["DB_SSL"] is False


@pytest.mark.parametrize("valor", ["true", "TRUE", "1", "yes", "on", " True "])
def test_config_backend_con_db_ssl_activo_devuelve_true(sin_env, valor):
    sin_env.setenv("DB_SSL", valor)
    assert configuracion_backend()["DB_SSL"] is True


@pytest.mark.parametrize("valor", ["false", "0", "no", "off", ""])
def test_config_backend_con_db_ssl_inactivo_devuelve_false(sin_env, valor):
    sin_env.setenv("DB_SSL", valor)
    assert configuracion_backend()["DB_SSL"] is False


def test_config_frontend_sin_timeout_usa_5_segundos(sin_env):
    assert configuracion_frontend()["BACKEND_TIMEOUT"] == 5


def test_config_frontend_con_timeout_en_env_lo_toma(sin_env):
    sin_env.setenv("BACKEND_TIMEOUT", "90")
    assert configuracion_frontend()["BACKEND_TIMEOUT"] == 90


def test_conectar_con_db_ssl_pasa_contexto_que_verifica_certificado_y_hostname(app_backend):
    app_backend.config["DB_SSL"] = True
    with patch("src.backend.db.pymysql.connect") as conectar:
        db._conectar()
    contexto = conectar.call_args.kwargs["ssl"]
    assert isinstance(contexto, ssl.SSLContext)
    assert contexto.verify_mode == ssl.CERT_REQUIRED
    assert contexto.check_hostname is True


def test_conectar_sin_db_ssl_no_pasa_opciones_tls(app_backend):
    app_backend.config["DB_SSL"] = False
    with patch("src.backend.db.pymysql.connect") as conectar:
        db._conectar()
    assert "ssl" not in conectar.call_args.kwargs
    assert conectar.call_args.kwargs["host"] == app_backend.config["DB_HOST"]


def test_conectar_con_db_ssl_conserva_los_demas_parametros(app_backend):
    app_backend.config.update(DB_SSL=True, DB_HOST="base.test", DB_PORT=4000, DB_NAME="cine")
    with patch("src.backend.db.pymysql.connect") as conectar:
        db._conectar()
    argumentos = conectar.call_args.kwargs
    assert (argumentos["host"], argumentos["port"], argumentos["database"]) == ("base.test", 4000, "cine")
    assert argumentos["charset"] == "utf8mb4"
    assert argumentos["autocommit"] is False


def test_llamar_usa_el_timeout_configurado(app_frontend):
    app_frontend.config["BACKEND_TIMEOUT"] = 90
    with patch("src.frontend.api_client.requests.request") as peticion:
        peticion.return_value = Mock(ok=True, content=b"")
        with app_frontend.test_request_context():
            llamar("GET", "/api/salud")
    assert peticion.call_args.kwargs["timeout"] == 90


def test_llamar_post_con_timeout_no_reintenta_y_devuelve_503(app_frontend):
    with patch("src.frontend.api_client.requests.request", side_effect=requests.Timeout) as peticion:
        with app_frontend.test_request_context():
            datos, error = llamar("POST", "/api/compras", json={})
    assert peticion.call_count == 1
    assert datos is None
    assert error["status"] == 503
