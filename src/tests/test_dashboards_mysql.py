"""Franjas horarias y cancelaciones contra MySQL real (SCRUM-76). Prueba OPT-IN: sin la variable se saltea.

Verifica el SQL de services/dashboards.py contra `seed.sql` recién cargado, con valores fijos esperados.
No carga schema ni seed ni usa las credenciales del .env para MySQL: la app de pruebas se configura (DB_HOST, DB_PORT, DB_USER, DB_PASSWORD
y DB_NAME) hacia una base `cine_paradiso` ya provisionada en un MySQL local y aislado (root sin contraseña en
127.0.0.1) y los endpoints usan `src.backend.db` real.

    PRUEBAS_MYSQL_PUERTO=3307 python -m pytest src/tests/test_dashboards_mysql.py -v

Las fechas del seed son relativas al día de carga: "ayer" y "mañana" se toman de las funciones con compras de
la propia base. Las pruebas de borde insertan datos temporales (2031) en una transacción
que siempre termina en rollback (fixture `conexion`), así la base queda como el seed.
"""
import os
from unittest.mock import MagicMock, patch

import pytest

PUERTO = os.environ.get("PRUEBAS_MYSQL_PUERTO")
if not PUERTO:
    pytest.skip("Definir PRUEBAS_MYSQL_PUERTO para correr las pruebas contra MySQL real.", allow_module_level=True)

from src.backend import db  # noqa: E402

FRANJAS = "/api/admin/dashboards/franjas-horarias"
CANCELACIONES = "/api/admin/dashboards/cancelaciones"
VACIAS = {"por_pelicula": [], "por_periodo": []}
LOCAL_SIN_SEED = 3  # el local 3 (Palermo) no tiene compras en el seed


# --- infraestructura ---
@pytest.fixture(autouse=True)
def mysql_real(app_backend):
    """Apunta la app al MySQL de pruebas: `src.backend.db` real, solo cambia la configuración de conexión."""
    app_backend.config.update(DB_HOST="127.0.0.1", DB_PORT=int(PUERTO), DB_USER="root", DB_PASSWORD="",
                              DB_NAME="cine_paradiso")


@pytest.fixture
def conexion():
    """Para las pruebas que insertan datos: todas las consultas del backend (`db._conectar`) usan una única
    conexión, así ven lo insertado, y al terminar se hace rollback. Devuelve esa conexión."""
    conexion = db._conectar()
    prestada = MagicMock(wraps=conexion)
    prestada.close = MagicMock()  # db.consultar cierra la conexión al terminar cada consulta
    try:
        with patch("src.backend.db._conectar", return_value=prestada):
            yield conexion
    finally:
        conexion.rollback()
        conexion.close()


def _ejecutar(conexion, sql, parametros=()):
    """INSERT/UPDATE dentro de la transacción de la prueba; devuelve el id insertado."""
    with conexion.cursor() as cursor:
        cursor.execute(sql, parametros)
        return cursor.lastrowid


@pytest.fixture
def pedir(cliente_backend, cabeceras):
    """GET al backend con la autenticación simulada; los dashboards consultan la base real."""
    def hacer_pedido(ruta, **filtros):
        respuesta = cliente_backend.get(ruta, query_string=filtros, headers=cabeceras)
        assert respuesta.status_code == 200, respuesta.get_json()
        return respuesta.get_json()

    return hacer_pedido


@pytest.fixture
def dias():
    """Días de las funciones con compras del seed: ayer (2 compras) y mañana (2 compras)."""
    fila = db.consultar("SELECT MIN(DATE(f.fecha_hora)) AS ayer, MAX(DATE(f.fecha_hora)) AS manana "
                        "FROM compras c JOIN funciones f ON f.id = c.funcion_id")[0]
    return {"ayer": fila["ayer"], "manana": fila["manana"]}


def _iso(dia, hora="00:00:00"):
    return f"{dia:%Y-%m-%d}T{hora}"


def _franja(desde, entradas):
    return {"hora_desde": desde, "hora_hasta": desde + 2, "entradas": entradas}


def _fila(compras, canceladas, porcentaje, **identidad):
    return dict(identidad, compras=compras, canceladas=canceladas, porcentaje=porcentaje)


CHIHIRO = {"pelicula_id": 5, "pelicula": "El viaje de Chihiro"}
TOY_STORY = {"pelicula_id": 6, "pelicula": "Toy Story"}
JURASSIC = {"pelicula_id": 7, "pelicula": "Jurassic Park"}
CINEMA_PARADISO = {"pelicula_id": 4, "pelicula": "Cinema Paradiso"}


# --- seed completo ---
def test_franjas_horarias_del_seed(pedir):
    assert pedir(FRANJAS) == [_franja(20, 4), _franja(16, 1)]


def test_cancelaciones_del_seed_por_pelicula(pedir):
    assert pedir(CANCELACIONES)["por_pelicula"] == [
        _fila(2, 1, 50.0, **JURASSIC), _fila(1, 0, 0.0, **CHIHIRO), _fila(1, 0, 0.0, **TOY_STORY)]


def test_cancelaciones_del_seed_por_periodo(pedir, dias):
    assert pedir(CANCELACIONES)["por_periodo"] == [
        _fila(2, 0, 0.0, periodo=_iso(dias["ayer"])), _fila(2, 1, 50.0, periodo=_iso(dias["manana"]))]


# --- filtro por local ---
def test_local_1_tiene_las_entradas_de_20_a_22_y_tres_compras(pedir, dias):
    assert pedir(FRANJAS, local_id=1) == [_franja(20, 4)]
    datos = pedir(CANCELACIONES, local_id=1)
    assert datos["por_pelicula"] == [_fila(2, 1, 50.0, **JURASSIC), _fila(1, 0, 0.0, **CHIHIRO)]
    assert datos["por_periodo"] == [
        _fila(1, 0, 0.0, periodo=_iso(dias["ayer"])), _fila(2, 1, 50.0, periodo=_iso(dias["manana"]))]
    assert sum(fila["compras"] for fila in datos["por_pelicula"]) == 3
    assert sum(fila["canceladas"] for fila in datos["por_pelicula"]) == 1


def test_local_2_tiene_una_entrada_de_16_a_18_y_una_compra_sin_cancelar(pedir, dias):
    assert pedir(FRANJAS, local_id=2) == [_franja(16, 1)]
    assert pedir(CANCELACIONES, local_id=2) == {
        "por_pelicula": [_fila(1, 0, 0.0, **TOY_STORY)],
        "por_periodo": [_fila(1, 0, 0.0, periodo=_iso(dias["ayer"]))]}


@pytest.mark.parametrize("local_id", [LOCAL_SIN_SEED, 9999])
def test_local_sin_compras_o_inexistente_devuelve_vacios(pedir, local_id):
    assert pedir(FRANJAS, local_id=local_id) == []
    assert pedir(CANCELACIONES, local_id=local_id) == VACIAS


# --- filtro por fecha de la función ---
def test_desde_manana_deja_solo_las_compras_de_manana(pedir, dias):
    desde = _iso(dias["manana"])
    assert pedir(FRANJAS, desde=desde) == [_franja(20, 2)]
    assert pedir(CANCELACIONES, desde=desde) == {
        "por_pelicula": [_fila(2, 1, 50.0, **JURASSIC)],
        "por_periodo": [_fila(2, 1, 50.0, periodo=_iso(dias["manana"]))]}


def test_hasta_ayer_deja_solo_las_compras_de_ayer(pedir, dias):
    hasta = _iso(dias["ayer"], "23:59:59")
    assert pedir(FRANJAS, hasta=hasta) == [_franja(20, 2), _franja(16, 1)]
    assert pedir(CANCELACIONES, hasta=hasta) == {
        "por_pelicula": [_fila(1, 0, 0.0, **CHIHIRO), _fila(1, 0, 0.0, **TOY_STORY)],
        "por_periodo": [_fila(2, 0, 0.0, periodo=_iso(dias["ayer"]))]}


@pytest.mark.parametrize("dia, hora, franja, pelicula", [
    ("ayer", "17:30:00", 16, TOY_STORY),
    ("ayer", "21:00:00", 20, CHIHIRO),
    ("manana", "21:00:00", 20, JURASSIC),
])
def test_los_extremos_son_inclusivos_a_la_hora_exacta_de_la_funcion(pedir, dias, dia, hora, franja, pelicula):
    instante = _iso(dias[dia], hora)
    datos = pedir(CANCELACIONES, desde=instante, hasta=instante)
    assert [fila["pelicula_id"] for fila in datos["por_pelicula"]] == [pelicula["pelicula_id"]]
    assert [f["hora_desde"] for f in pedir(FRANJAS, desde=instante, hasta=instante)] == [franja]


@pytest.mark.parametrize("dia, desde, hasta", [
    ("ayer", "21:00:01", "23:59:59"),  # justo después de la función de las 21:00
    ("ayer", "17:30:01", "20:59:59"),  # entre las funciones de las 17:30 y las 21:00
    ("manana", "21:00:01", "23:59:59"),
])
def test_un_segundo_fuera_del_rango_deja_resultados_vacios(pedir, dias, dia, desde, hasta):
    filtros = {"desde": _iso(dias[dia], desde), "hasta": _iso(dias[dia], hasta)}
    assert pedir(FRANJAS, **filtros) == []
    assert pedir(CANCELACIONES, **filtros) == VACIAS


def test_rango_de_ayer_que_incluye_ambas_funciones_en_sus_extremos(pedir, dias):
    filtros = {"desde": _iso(dias["ayer"], "17:30:00"), "hasta": _iso(dias["ayer"], "21:00:00")}
    assert pedir(FRANJAS, **filtros) == [_franja(20, 2), _franja(16, 1)]
    assert pedir(CANCELACIONES, **filtros)["por_periodo"] == [_fila(2, 0, 0.0, periodo=_iso(dias["ayer"]))]


def test_filtros_combinados_local_y_fecha(pedir, dias):
    filtros = {"local_id": 1, "desde": _iso(dias["manana"]), "hasta": _iso(dias["manana"], "23:59:59")}
    assert pedir(FRANJAS, **filtros) == [_franja(20, 2)]
    assert pedir(CANCELACIONES, **filtros)["por_pelicula"] == [_fila(2, 1, 50.0, **JURASSIC)]


# --- casos de borde con datos temporales (rollback) ---
DIA_BORDE = "2031-05-05"
FILTRO_BORDE = {"desde": f"{DIA_BORDE}T00:00:00", "hasta": f"{DIA_BORDE}T23:59:59"}
PERIODO_BORDE = f"{DIA_BORDE}T00:00:00"
ESTADOS_VIGENTES = ("pendiente", "confirmada")
SEGUN_ESTADO = "segun estado"


def _funcion(conexion, hora, pelicula_id=4, sala_id=4, activa=1):
    """Función de prueba (por defecto Cinema Paradiso en la Sala 1 del local 3)."""
    return _ejecutar(conexion, "INSERT INTO funciones (pelicula_id, sala_id, fecha_hora, precio, activa) "
                               "VALUES (%s, %s, %s, 5500, %s)",
                     (pelicula_id, sala_id, f"{DIA_BORDE} {hora}", activa))


def _compra(conexion, funcion_id, estado, entradas=1, servicios=0, activa=SEGUN_ESTADO):
    """Compra de Ana con `entradas` butacas libres de la función y `servicios` servicios distintos.
    Sus entradas valen activa=1 si la compra está vigente y NULL si se canceló o venció (como en el schema),
    salvo que se indique `activa`."""
    compra_id = _ejecutar(conexion, "INSERT INTO compras (usuario_id, funcion_id, estado, total, vence_en) "
                                    "VALUES (2, %s, %s, 5500, %s)", (funcion_id, estado, f"{DIA_BORDE} 00:00:00"))
    butacas = db.consultar("SELECT b.id FROM butacas b JOIN funciones f ON f.sala_id = b.sala_id "
                           "WHERE f.id = %s AND b.id NOT IN "
                           "(SELECT butaca_id FROM entradas WHERE funcion_id = %s AND activa = 1) "
                           "ORDER BY b.id LIMIT %s", (funcion_id, funcion_id, entradas))
    if activa == SEGUN_ESTADO:
        activa = 1 if estado in ESTADOS_VIGENTES else None
    for butaca in butacas:
        _ejecutar(conexion, "INSERT INTO entradas (compra_id, funcion_id, butaca_id, precio, activa) "
                            "VALUES (%s, %s, %s, 5500, %s)", (compra_id, funcion_id, butaca["id"], activa))
    for servicio_id in range(1, servicios + 1):
        _ejecutar(conexion, "INSERT INTO compra_servicios (compra_id, servicio_id, cantidad, precio_unitario) "
                            "VALUES (%s, %s, 1, 100)", (compra_id, servicio_id))
    return compra_id


def test_las_franjas_incluyen_sus_limites_y_la_ultima_llega_a_24(pedir, conexion):
    for hora in ("00:00:00", "01:59:59", "02:00:00", "23:59:00"):
        _compra(conexion, _funcion(conexion, hora), "confirmada")
    assert pedir(FRANJAS, **FILTRO_BORDE) == [
        _franja(0, 2), _franja(2, 1), {"hora_desde": 22, "hora_hasta": 24, "entradas": 1}]


def test_las_franjas_ordenan_por_entradas_y_desempatan_por_hora_ascendente(pedir, conexion):
    _compra(conexion, _funcion(conexion, "18:00:00"), "confirmada", entradas=1)
    _compra(conexion, _funcion(conexion, "10:00:00"), "confirmada", entradas=1)
    _compra(conexion, _funcion(conexion, "14:00:00"), "confirmada", entradas=3)
    assert [franja["hora_desde"] for franja in pedir(FRANJAS, **FILTRO_BORDE)] == [14, 10, 18]


def test_las_franjas_no_cuentan_compras_no_confirmadas_ni_entradas_inactivas(pedir, conexion):
    funcion = _funcion(conexion, "14:00:00")
    _compra(conexion, funcion, "confirmada", entradas=2)
    for estado in ("pendiente", "vencida", "cancelada"):
        _compra(conexion, funcion, estado, entradas=1)
    _compra(conexion, funcion, "confirmada", entradas=1, activa=None)  # entrada liberada de una confirmada
    assert pedir(FRANJAS, **FILTRO_BORDE) == [_franja(14, 2)]


def test_las_franjas_no_multiplican_entradas_por_los_servicios_de_la_compra(pedir, conexion):
    _compra(conexion, _funcion(conexion, "14:00:00"), "confirmada", entradas=3, servicios=4)
    assert pedir(FRANJAS, **FILTRO_BORDE) == [_franja(14, 3)]


def test_las_cancelaciones_cuentan_compras_y_no_entradas_ni_servicios(pedir, conexion):
    funcion = _funcion(conexion, "14:00:00")
    _compra(conexion, funcion, "confirmada", entradas=3, servicios=4)
    _compra(conexion, funcion, "cancelada", entradas=2, servicios=2)
    datos = pedir(CANCELACIONES, **FILTRO_BORDE)
    assert datos["por_pelicula"] == [_fila(2, 1, 50.0, **CINEMA_PARADISO)]
    assert datos["por_periodo"] == [_fila(2, 1, 50.0, periodo=PERIODO_BORDE)]


def test_las_cancelaciones_excluyen_pendientes_y_vencidas_del_denominador(pedir, conexion):
    funcion = _funcion(conexion, "14:00:00")
    for estado in ("confirmada", "cancelada", "pendiente", "vencida"):
        _compra(conexion, funcion, estado)
    assert pedir(CANCELACIONES, **FILTRO_BORDE)["por_pelicula"] == [_fila(2, 1, 50.0, **CINEMA_PARADISO)]


def test_el_porcentaje_se_redondea_a_dos_decimales_y_viaja_como_numero(pedir, conexion):
    funcion = _funcion(conexion, "14:00:00")
    for estado in ("confirmada", "confirmada", "cancelada"):
        _compra(conexion, funcion, estado)
    porcentaje = pedir(CANCELACIONES, **FILTRO_BORDE)["por_pelicula"][0]["porcentaje"]
    assert porcentaje == 33.33 and isinstance(porcentaje, float)


def test_el_periodo_es_el_dia_de_la_funcion_y_no_el_de_creacion_de_la_compra(pedir, conexion):
    # Las compras se crean hoy (creada_en = NOW()) pero sus funciones son de 2031.
    _compra(conexion, _funcion(conexion, "23:30:00"), "confirmada")
    _compra(conexion, _funcion(conexion, "00:30:00", pelicula_id=5), "cancelada")
    datos = pedir(CANCELACIONES, **FILTRO_BORDE)
    assert datos["por_pelicula"] == [_fila(1, 1, 100.0, **CHIHIRO), _fila(1, 0, 0.0, **CINEMA_PARADISO)]
    assert datos["por_periodo"] == [_fila(2, 1, 50.0, periodo=PERIODO_BORDE)]


def test_el_historial_de_peliculas_salas_y_funciones_dados_de_baja_se_conserva(pedir, conexion):
    activa = _funcion(conexion, "14:00:00", sala_id=4)
    dada_de_baja = _funcion(conexion, "15:00:00", sala_id=5, activa=0)
    for funcion in (activa, dada_de_baja):
        _compra(conexion, funcion, "confirmada", entradas=2)
    _ejecutar(conexion, "UPDATE peliculas SET activa = 0 WHERE id = 4")
    _ejecutar(conexion, "UPDATE salas SET activa = 0 WHERE id IN (4, 5)")
    assert pedir(FRANJAS, **FILTRO_BORDE) == [_franja(14, 4)]
    assert pedir(CANCELACIONES, **FILTRO_BORDE)["por_pelicula"] == [_fila(2, 0, 0.0, **CINEMA_PARADISO)]
    assert pedir(FRANJAS, local_id=3, **FILTRO_BORDE) == [_franja(14, 4)]
