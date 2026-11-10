"""Franjas horarias y cancelaciones (SCRUM-76), ocupación y ventas por género (SCRUM-75) y resumen (SCRUM-124) contra MySQL real. Prueba OPT-IN: sin la variable se saltea.

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
from datetime import timedelta
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


# --- ocupación y ventas por género (SCRUM-75) ---
OCUPACION = "/api/admin/dashboards/ocupacion"
VENTAS_GENERO = "/api/admin/dashboards/ventas-genero"
OCUPACION_VACIA = {"por_pelicula": [], "por_funcion": []}
FUNCIONES_DEL_SEED = 135
CAPACIDAD_SALA_4 = 70


def _ocupacion(vendidas, capacidad, ocupacion, **identidad):
    return dict(identidad, vendidas=vendidas, capacidad=capacidad, ocupacion=ocupacion)


def _resumen_pelicula(fila):
    return fila["pelicula_id"], fila["vendidas"], fila["capacidad"], fila["ocupacion"]


def _resumen_funcion(fila):
    return fila["pelicula"], fila["sala"], fila["fecha_hora"], fila["vendidas"], fila["capacidad"], fila["ocupacion"]


def _genero(genero, entradas, monto):
    return {"genero": genero, "entradas": entradas, "monto": monto}


def test_ocupacion_del_seed_por_pelicula(pedir):
    assert [_resumen_pelicula(fila) for fila in pedir(OCUPACION)["por_pelicula"]] == [
        (7, 2, 1538, 0.13), (5, 2, 1760, 0.11), (6, 1, 1706, 0.06),
        (1, 0, 1328, 0.0), (2, 0, 1322, 0.0), (3, 0, 1446, 0.0), (4, 0, 1646, 0.0)]


def test_ocupacion_del_seed_por_funcion(pedir, dias):
    por_funcion = pedir(OCUPACION)["por_funcion"]
    assert len(por_funcion) == FUNCIONES_DEL_SEED
    assert [_resumen_funcion(fila) for fila in por_funcion[:3]] == [
        ("El viaje de Chihiro", "Sala 1", _iso(dias["ayer"], "21:00:00"), 2, 96, 2.08),
        ("Jurassic Park", "Sala 1", _iso(dias["manana"], "21:00:00"), 2, 96, 2.08),
        ("Toy Story", "Sala 1", _iso(dias["ayer"], "17:30:00"), 1, 140, 0.71)]
    assert all(fila["vendidas"] == 0 and fila["ocupacion"] == 0.0 for fila in por_funcion[3:])


def test_la_compra_cancelada_del_seed_no_cuenta_como_vendida(pedir):
    assert sum(fila["vendidas"] for fila in pedir(OCUPACION)["por_pelicula"]) == 5


def test_ocupacion_filtra_por_local_y_por_fecha(pedir, dias):
    por_local = pedir(OCUPACION, local_id=2)["por_funcion"]
    assert [fila["pelicula"] for fila in por_local if fila["vendidas"]] == ["Toy Story"]
    assert {fila["local"] for fila in por_local} == {por_local[0]["local"]}
    instante = _iso(dias["manana"], "21:00:00")
    vendidas = [fila for fila in pedir(OCUPACION, desde=instante, hasta=instante)["por_pelicula"] if fila["vendidas"]]
    assert [fila["pelicula"] for fila in vendidas] == ["Jurassic Park"]


def test_el_local_sin_ventas_aparece_con_ocupacion_cero(pedir):
    datos = pedir(OCUPACION, local_id=LOCAL_SIN_SEED)
    assert datos["por_funcion"]
    assert all(fila["vendidas"] == 0 for fila in datos["por_funcion"])


def test_ocupacion_de_local_inexistente_devuelve_vacios(pedir):
    assert pedir(OCUPACION, local_id=9999) == OCUPACION_VACIA


def test_ventas_genero_del_seed_usa_el_primer_genero_y_cierra_con_el_total(pedir):
    datos = pedir(VENTAS_GENERO)
    assert datos == [_genero("Animación", 3, 16500.0), _genero("Aventura", 2, 11000.0)]
    assert sum(fila["entradas"] for fila in datos) == sum(f["entradas"] for f in pedir(FRANJAS))


def test_ventas_genero_filtra_por_local(pedir):
    assert pedir(VENTAS_GENERO, local_id=1) == [_genero("Animación", 2, 11000.0), _genero("Aventura", 2, 11000.0)]
    assert pedir(VENTAS_GENERO, local_id=2) == [_genero("Animación", 1, 5500.0)]
    assert pedir(VENTAS_GENERO, local_id=LOCAL_SIN_SEED) == []


def test_ventas_genero_filtra_por_fecha_de_la_funcion(pedir, dias):
    assert pedir(VENTAS_GENERO, desde=_iso(dias["manana"])) == [_genero("Aventura", 2, 11000.0)]
    assert pedir(VENTAS_GENERO, hasta=_iso(dias["ayer"], "23:59:59")) == [_genero("Animación", 3, 16500.0)]


def test_la_funcion_sin_ventas_suma_capacidad_a_la_pelicula(pedir, conexion):
    _compra(conexion, _funcion(conexion, "14:00:00"), "confirmada", entradas=7)
    _funcion(conexion, "18:00:00")
    datos = pedir(OCUPACION, **FILTRO_BORDE)
    assert datos["por_pelicula"] == [_ocupacion(7, 2 * CAPACIDAD_SALA_4, 5.0, **CINEMA_PARADISO)]
    assert [fila["ocupacion"] for fila in datos["por_funcion"]] == [10.0, 0.0]


def test_ocupacion_no_multiplica_la_capacidad_por_entradas_ni_servicios(pedir, conexion):
    funcion = _funcion(conexion, "14:00:00")
    _compra(conexion, funcion, "confirmada", entradas=3, servicios=4)
    _compra(conexion, funcion, "confirmada", entradas=2)
    assert pedir(OCUPACION, **FILTRO_BORDE)["por_pelicula"] == [
        _ocupacion(5, CAPACIDAD_SALA_4, 7.14, **CINEMA_PARADISO)]


def test_ocupacion_no_cuenta_compras_no_confirmadas_ni_entradas_inactivas(pedir, conexion):
    funcion = _funcion(conexion, "14:00:00")
    _compra(conexion, funcion, "confirmada", entradas=2)
    for estado in ("pendiente", "vencida", "cancelada"):
        _compra(conexion, funcion, estado)
    _compra(conexion, funcion, "confirmada", activa=None)
    assert pedir(OCUPACION, **FILTRO_BORDE)["por_pelicula"][0]["vendidas"] == 2


def test_la_funcion_de_baja_no_suma_capacidad(pedir, conexion):
    _funcion(conexion, "14:00:00")
    _funcion(conexion, "18:00:00", activa=0)
    assert pedir(OCUPACION, **FILTRO_BORDE)["por_pelicula"][0]["capacidad"] == CAPACIDAD_SALA_4


def test_ocupacion_conserva_peliculas_y_salas_dadas_de_baja(pedir, conexion):
    _compra(conexion, _funcion(conexion, "14:00:00"), "confirmada", entradas=7)
    _ejecutar(conexion, "UPDATE peliculas SET activa = 0 WHERE id = 4")
    _ejecutar(conexion, "UPDATE salas SET activa = 0 WHERE id = 4")
    assert pedir(OCUPACION, **FILTRO_BORDE)["por_pelicula"] == [_ocupacion(7, CAPACIDAD_SALA_4, 10.0, **CINEMA_PARADISO)]


def test_ventas_genero_junta_peliculas_con_el_mismo_primer_genero(pedir, conexion):
    _ejecutar(conexion, "UPDATE peliculas SET genero = 'Drama, Romance' WHERE id = 4")
    _ejecutar(conexion, "UPDATE peliculas SET genero = 'Drama' WHERE id = 5")
    _compra(conexion, _funcion(conexion, "14:00:00"), "confirmada", entradas=2)
    _compra(conexion, _funcion(conexion, "18:00:00", pelicula_id=5), "confirmada")
    assert pedir(VENTAS_GENERO, **FILTRO_BORDE) == [_genero("Drama", 3, 16500.0)]


def test_ventas_genero_suma_entradas_y_no_el_total_con_servicios(pedir, conexion):
    _ejecutar(conexion, "UPDATE peliculas SET genero = 'Drama' WHERE id = 4")
    _compra(conexion, _funcion(conexion, "14:00:00"), "confirmada", entradas=3, servicios=4)
    assert pedir(VENTAS_GENERO, **FILTRO_BORDE) == [_genero("Drama", 3, 16500.0)]


def test_ventas_genero_no_cuenta_compras_no_confirmadas_ni_entradas_inactivas(pedir, conexion):
    _ejecutar(conexion, "UPDATE peliculas SET genero = 'Drama' WHERE id = 4")
    funcion = _funcion(conexion, "14:00:00")
    _compra(conexion, funcion, "confirmada", entradas=2)
    for estado in ("pendiente", "vencida", "cancelada"):
        _compra(conexion, funcion, estado)
    _compra(conexion, funcion, "confirmada", activa=None)
    assert pedir(VENTAS_GENERO, **FILTRO_BORDE) == [_genero("Drama", 2, 11000.0)]


# --- resumen de indicadores (SCRUM-124) ---
RESUMEN = "/api/admin/dashboards/resumen"
SIN_COMPARAR = {"anterior": None, "variacion": None}


def _periodo(desde, hasta):
    return {"desde": _iso(desde), "hasta": _iso(hasta, "23:59:59")}


def test_resumen_del_seed_sin_filtros(pedir):
    # 5 entradas confirmadas; 17.500 + 10.500 + 11.000 con servicios; 5 / 10.746 butacas; 1 cancelada de 4 compras.
    assert pedir(RESUMEN) == {
        "entradas": {"valor": 5, **SIN_COMPARAR},
        "ingresos": {"valor": 39000.0, **SIN_COMPARAR},
        "ocupacion": {"valor": 0.05, **SIN_COMPARAR},
        "cancelaciones": {"valor": 25.0, **SIN_COMPARAR},
    }


def test_resumen_del_seed_compara_con_los_dos_dias_anteriores(pedir, dias):
    # Hoy y mañana contra anteayer y ayer. Dos días son 2 x 3 funciones x 398 butacas = 2.388 de capacidad.
    hoy = dias["ayer"] + timedelta(days=1)
    assert pedir(RESUMEN, **_periodo(hoy, dias["manana"])) == {
        "entradas": {"valor": 2, "anterior": 3, "variacion": -33.33},  # (2 - 3) / 3
        "ingresos": {"valor": 11000.0, "anterior": 28000.0, "variacion": -60.71},  # (11.000 - 28.000) / 28.000
        "ocupacion": {"valor": 0.08, "anterior": 0.13, "variacion": -0.05},  # 2 / 2.388 y 3 / 2.388
        "cancelaciones": {"valor": 50.0, "anterior": 0.0, "variacion": 50.0},  # 1 de 2 contra 0 de 2
    }


def test_resumen_del_seed_filtra_por_local(pedir):
    # Belgrano: 1 entrada con 2 gaseosas = 10.500; 27 funciones x 140 butacas = 3.780; 0 canceladas de 1 compra.
    assert pedir(RESUMEN, local_id=2) == {
        "entradas": {"valor": 1, **SIN_COMPARAR},
        "ingresos": {"valor": 10500.0, **SIN_COMPARAR},
        "ocupacion": {"valor": 0.03, **SIN_COMPARAR},
        "cancelaciones": {"valor": 0.0, **SIN_COMPARAR},
    }


def test_resumen_de_local_sin_compras_y_de_local_inexistente(pedir):
    sin_compras = pedir(RESUMEN, local_id=LOCAL_SIN_SEED)
    assert sin_compras["entradas"]["valor"] == 0 and sin_compras["ingresos"]["valor"] == 0.0
    assert sin_compras["ocupacion"]["valor"] == 0.0 and sin_compras["cancelaciones"]["valor"] is None
    inexistente = pedir(RESUMEN, local_id=9999)
    assert inexistente["ocupacion"]["valor"] is None and inexistente["cancelaciones"]["valor"] is None


def test_resumen_no_multiplica_el_total_por_las_entradas_ni_los_servicios(pedir, conexion):
    _compra(conexion, _funcion(conexion, "14:00:00"), "confirmada", entradas=3, servicios=4)
    datos = pedir(RESUMEN, **FILTRO_BORDE)
    assert datos["entradas"]["valor"] == 3 and datos["ingresos"]["valor"] == 5500.0
    assert datos["ocupacion"]["valor"] == 4.29  # 3 / 70
    assert datos["cancelaciones"]["valor"] == 0.0


def test_resumen_no_cuenta_compras_pendientes_vencidas_ni_canceladas_como_ventas(pedir, conexion):
    funcion = _funcion(conexion, "14:00:00")
    _compra(conexion, funcion, "confirmada", entradas=2)
    for estado in ("pendiente", "vencida", "cancelada"):
        _compra(conexion, funcion, estado)
    datos = pedir(RESUMEN, **FILTRO_BORDE)
    assert datos["entradas"]["valor"] == 2 and datos["ingresos"]["valor"] == 5500.0
    assert datos["cancelaciones"]["valor"] == 50.0  # 1 cancelada de 2; pendiente y vencida no cuentan
