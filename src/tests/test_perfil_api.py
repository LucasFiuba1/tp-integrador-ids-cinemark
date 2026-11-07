"""Pruebas de los endpoints de perfil con los campos que usa la pantalla Mi perfil (SCRUM-49, SCRUM-50)."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.tests.utilidades import simular_bd


@pytest.fixture
def bd_perfil():
    with simular_bd(destinos=("src.backend.services.perfil",)) as simulacion:
        yield simulacion


def _fila_compra(**cambios):
    fila = {
        "id": 10, "estado": "confirmada", "total": Decimal("5000.00"), "token_qr": "qr-10",
        "creada_en": datetime(2026, 11, 1, 10, 0), "vence_en": datetime(2026, 11, 1, 10, 10),
        "confirmada_en": datetime(2026, 11, 1, 10, 3), "cancelada_en": None, "utilizada_en": None,
        "funcion_id": 4, "fecha_hora": datetime.now().replace(microsecond=0) + timedelta(days=3),
        "pelicula_id": 8, "titulo": "Prueba", "poster_url": None, "sala": "Sala 1", "local": "Centro",
    }
    fila.update(cambios)
    return fila


def _compras(cliente_backend, cabeceras_cliente, bd_perfil, *filas):
    bd_perfil.consultar.side_effect = [list(filas), [], []]
    respuesta = cliente_backend.get("/api/me/compras", headers=cabeceras_cliente)
    assert respuesta.status_code == 200
    return respuesta.get_json()


def test_compras_trae_pelicula_id_y_cancelable_hasta(cliente_backend, cabeceras_cliente, bd_perfil):
    fila = _fila_compra()
    [compra] = _compras(cliente_backend, cabeceras_cliente, bd_perfil, fila)
    assert compra["funcion"]["pelicula_id"] == 8
    assert compra["cancelable"] is True
    assert compra["cancelable_hasta"] == (fila["fecha_hora"] - timedelta(hours=2)).isoformat()
    assert compra["vence_en"] is None  # solo las pendientes tienen vencimiento


def test_compras_pendiente_vigente_trae_vence_en_y_no_es_cancelable(cliente_backend, cabeceras_cliente, bd_perfil):
    fila = _fila_compra(estado="pendiente", token_qr=None, confirmada_en=None)
    [compra] = _compras(cliente_backend, cabeceras_cliente, bd_perfil, fila)
    assert compra["vence_en"] == "2026-11-01T10:10:00"
    assert compra["cancelable"] is False
    assert compra["token_qr"] is None


def test_compras_confirmada_a_menos_de_2_horas_no_es_cancelable(cliente_backend, cabeceras_cliente, bd_perfil):
    fila = _fila_compra(fecha_hora=datetime.now() + timedelta(hours=1))
    [compra] = _compras(cliente_backend, cabeceras_cliente, bd_perfil, fila)
    assert compra["cancelable"] is False


def test_compras_solo_pide_pendientes_que_no_vencieron(cliente_backend, cabeceras_cliente, bd_perfil):
    _compras(cliente_backend, cabeceras_cliente, bd_perfil)
    sql, parametros = bd_perfil.consultar.call_args_list[0].args
    assert "c.estado = 'pendiente' AND c.vence_en > NOW()" in sql
    assert parametros == (2,)  # el id sale del token del cliente, nunca del request


def test_peliculas_vistas_trae_duracion_y_clasificacion(cliente_backend, cabeceras_cliente, bd_perfil):
    bd_perfil.consultar.return_value = [{
        "pelicula_id": 3, "titulo": "Vista", "poster_url": None, "genero": "Drama", "duracion_min": 102,
        "clasificacion": "+13", "fecha_hora": datetime(2026, 10, 18, 20, 0), "sala": "Sala 1", "local": "Centro",
        "utilizada_en": datetime(2026, 10, 18, 19, 52),
    }]
    respuesta = cliente_backend.get("/api/me/peliculas-vistas", headers=cabeceras_cliente)
    [vista] = respuesta.get_json()
    assert vista["duracion_min"] == 102 and vista["clasificacion"] == "+13"
    assert vista["utilizada_en"] == "2026-10-18T19:52:00"
    assert "p.duracion_min, p.clasificacion" in bd_perfil.consultar.call_args.args[0]


def test_me_devuelve_el_email_del_usuario(cliente_backend, cabeceras_cliente, usuarios):
    usuarios["cliente"]["email"] = "cliente@email.com"
    respuesta = cliente_backend.get("/api/auth/me", headers=cabeceras_cliente)
    assert respuesta.get_json()["email"] == "cliente@email.com"
