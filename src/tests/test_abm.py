"""Pruebas de los helpers comunes de ABM: existencia, baja lógica y duplicados (SCRUM-100)."""
import pymysql
import pytest
from werkzeug.exceptions import HTTPException

from src.backend import abm
from src.tests.utilidades import afirmar_error_json, simular_bd


@pytest.fixture
def bd(app_backend):
    """Base simulada (error_api necesita el contexto de la app para armar la respuesta JSON)."""
    with simular_bd() as simulacion:
        yield simulacion


def afirmar_error(status, codigo, mensaje, funcion, *args):
    with pytest.raises(HTTPException) as error:
        funcion(*args)
    afirmar_error_json(error.value.response, status, codigo, mensaje)


def duplicado():
    return pymysql.err.IntegrityError(1062, "Duplicate entry 'Gaseosa' for key 'nombre'")


def clave_foranea_rota():
    return pymysql.err.IntegrityError(1452, "Cannot add or update a child row")


# --- existencia ---
def test_requerir_existente_devuelve_la_fila(app_backend):
    fila = {"id": 3}
    assert abm.requerir_existente(fila, "No existe.") is fila


def test_requerir_existente_con_none_devuelve_404(app_backend):
    afirmar_error(404, "NO_ENCONTRADO", "La sala no existe.", abm.requerir_existente, None, "La sala no existe.")


@pytest.mark.parametrize("tabla, columna", [
    ("peliculas", "activa"), ("salas", "activa"), ("funciones", "activa"), ("servicios", "activo"),
])
def test_obtener_activo_filtra_por_la_columna_de_estado_de_la_tabla(bd, tabla, columna):
    bd.consultar_uno.return_value = {"id": 7}

    assert abm.obtener_activo(tabla, 7, "No existe.") == {"id": 7}

    sql, parametros = bd.consultar_uno.call_args.args
    assert sql == "SELECT id FROM " + tabla + " WHERE id = %s AND " + columna + " = TRUE"
    assert parametros == (7,)


def test_obtener_activo_inexistente_o_de_baja_devuelve_404(bd):
    bd.consultar_uno.return_value = None
    afirmar_error(404, "NO_ENCONTRADO", "La película no existe.", abm.obtener_activo, "peliculas", 9,
                  "La película no existe.")


# --- baja lógica ---
@pytest.mark.parametrize("tabla, columna", [("salas", "activa"), ("servicios", "activo")])
def test_dar_de_baja_logica_hace_update_y_no_delete(bd, tabla, columna):
    abm.dar_de_baja_logica(tabla, 4)

    sql, parametros = bd.ejecutar.call_args.args
    assert sql == "UPDATE " + tabla + " SET " + columna + " = FALSE WHERE id = %s"
    assert parametros == (4,)
    assert all("DELETE" not in llamada.args[0] for llamada in bd.ejecutar.call_args_list)


def test_reactivar_vuelve_a_poner_el_estado_en_true(bd):
    abm.reactivar("servicios", 4)

    sql, parametros = bd.ejecutar.call_args.args
    assert sql == "UPDATE servicios SET activo = TRUE WHERE id = %s"
    assert parametros == (4,)


@pytest.mark.parametrize("tabla", ["locales", "usuarios", "servicios; DROP TABLE compras", ""])
def test_tabla_fuera_de_la_lista_blanca_no_toca_la_base(bd, tabla):
    with pytest.raises(ValueError):
        abm.dar_de_baja_logica(tabla, 1)
    with pytest.raises(ValueError):
        abm.obtener_activo(tabla, 1, "No existe.")
    bd.ejecutar.assert_not_called()
    bd.consultar_uno.assert_not_called()


# --- duplicados ---
def test_es_clave_duplicada_distingue_unique_de_otros_errores():
    assert abm.es_clave_duplicada(duplicado())
    assert not abm.es_clave_duplicada(clave_foranea_rota())
    assert not abm.es_clave_duplicada(pymysql.err.IntegrityError())


def _insertar_que_falla(error):
    with abm.traducir_duplicado("Ya existe un servicio con ese nombre.", "SERVICIO_DUPLICADO"):
        raise error


def test_traducir_duplicado_convierte_el_unique_en_409(app_backend):
    afirmar_error(409, "SERVICIO_DUPLICADO", "Ya existe un servicio con ese nombre.", _insertar_que_falla,
                  duplicado())


def test_traducir_duplicado_usa_el_codigo_generico_por_defecto(app_backend):
    def insertar():
        with abm.traducir_duplicado("Ya existe."):
            raise duplicado()

    afirmar_error(409, "DUPLICADO", "Ya existe.", insertar)


def test_traducir_duplicado_deja_pasar_otros_errores_de_integridad(app_backend):
    with pytest.raises(pymysql.err.IntegrityError):
        _insertar_que_falla(clave_foranea_rota())


def test_traducir_duplicado_sin_error_no_hace_nada(app_backend):
    with abm.traducir_duplicado("Ya existe."):
        resultado = 5
    assert resultado == 5


def test_servicio_duplicado_por_la_api_responde_409(cliente_backend, cabeceras_admin, bd):
    """Prueba de punta a punta: el INSERT con nombre repetido llega como 409 con el código documentado."""
    bd.ejecutar.side_effect = duplicado()
    respuesta = cliente_backend.post(
        "/api/admin/servicios", json={"nombre": "Gaseosa", "precio": 2500}, headers=cabeceras_admin
    )
    afirmar_error_json(respuesta, 409, "SERVICIO_DUPLICADO")
