"""Pruebas de las utilidades comunes de las pruebas del backend (SCRUM-101).

Cubren la base simulada, los usuarios y tokens por rol, y el helper de errores JSON, sin acceso a MySQL.
"""
from unittest.mock import Mock, patch

import pytest
from itsdangerous import URLSafeTimedSerializer

from src.backend import auth, db
from src.backend.services import compras, peliculas
from src.tests.utilidades import (
    ID_ADMIN, ID_CLIENTE, afirmar_error_json, cabeceras_de, contexto_app_backend, crear_app_backend, simular_bd,
    simular_usuarios, usuario_de_prueba,
)

RUTA_PELICULAS = "/api/admin/peliculas"  # solo admin
RUTA_COMPRAS = "/api/compras"  # solo cliente
SERVICE_PELICULAS = "src.backend.services.peliculas"
SERVICE_COMPRAS = "src.backend.services.compras"


def respuesta_falsa(status, cuerpo):
    return Mock(status_code=status, get_json=Mock(return_value=cuerpo))


def error_json(codigo="CODIGO", mensaje="Mensaje."):
    return {"error": {"codigo": codigo, "mensaje": mensaje}}


# --- app ---
def test_crear_app_backend_aplica_la_configuracion_de_prueba_y_permite_pisarla():
    app = crear_app_backend(TMDB_API_KEY="")
    assert app.config["TESTING"] is True
    assert app.config["SECRET_KEY"] == "pruebas"
    assert app.config["TMDB_API_KEY"] == ""


def test_contexto_app_backend_activa_el_contexto_solo_dentro_del_with():
    with contexto_app_backend() as app:
        assert cabeceras_de({"id": 1})["Authorization"].startswith("Bearer ")
        assert app.config["TMDB_API_KEY"] == "clave-de-prueba"
    with pytest.raises(RuntimeError):
        cabeceras_de({"id": 1})


# --- base simulada: módulo original ---
def test_simular_bd_reemplaza_las_cuatro_operaciones_de_db_con_valores_seguros():
    with simular_bd() as simulacion:
        assert db.consultar("SELECT 1") == []
        assert db.consultar_uno("SELECT 1", (1,)) is None
        assert db.ejecutar("INSERT x", (1,)) == 1
        with db.transaccion() as cursor:
            assert cursor is simulacion.cursor
            cursor.execute("UPDATE x", (1,))
            assert cursor.fetchone() is None
            assert cursor.fetchall() == []
            assert cursor.lastrowid == 1
    simulacion.consultar.assert_called_once_with("SELECT 1")
    simulacion.consultar_uno.assert_called_once_with("SELECT 1", (1,))
    simulacion.ejecutar.assert_called_once_with("INSERT x", (1,))
    simulacion.transaccion.assert_called_once_with()
    simulacion.cursor.execute.assert_called_once_with("UPDATE x", (1,))


def test_simular_bd_permite_configurar_los_mocks():
    with simular_bd() as simulacion:
        simulacion.consultar.return_value = [{"id": 1}]
        simulacion.consultar_uno.side_effect = [{"id": 2}, None]
        simulacion.ejecutar.return_value = 9
        simulacion.cursor.fetchone.return_value = {"id": 3}
        assert db.consultar("x") == [{"id": 1}]
        assert [db.consultar_uno("x"), db.consultar_uno("x")] == [{"id": 2}, None]
        assert db.ejecutar("x") == 9
        with db.transaccion() as cursor:
            assert cursor.fetchone() == {"id": 3}


def test_simular_bd_no_abre_conexiones_reales():
    with patch("src.backend.db.pymysql.connect") as conectar_real, simular_bd() as simulacion:
        db.consultar("x")
        db.consultar_uno("x")
        db.ejecutar("x")
        with db.transaccion():
            pass
        with pytest.raises(AssertionError, match="conexión real"):
            db._conectar()
    conectar_real.assert_not_called()
    simulacion.conectar.assert_called_once_with()


# --- base simulada: alias importados por los services ---
def test_simular_bd_intercepta_los_alias_importados_en_un_service():
    original = (peliculas.consultar, peliculas.consultar_uno, peliculas.ejecutar)
    with simular_bd(destinos=(SERVICE_PELICULAS,)) as simulacion:
        assert peliculas.consultar is simulacion.consultar
        assert peliculas.consultar_uno is simulacion.consultar_uno
        assert peliculas.ejecutar is simulacion.ejecutar
        assert db.consultar is simulacion.consultar
        assert peliculas.consultar("x") == []
        assert peliculas.consultar_uno("x") is None
        assert peliculas.ejecutar("x") == 1
    assert (peliculas.consultar, peliculas.consultar_uno, peliculas.ejecutar) == original


def test_simular_bd_intercepta_transaccion_importada_en_un_service():
    original = compras.transaccion
    with simular_bd(destinos=(SERVICE_COMPRAS,)) as simulacion:
        assert compras.transaccion is simulacion.transaccion
        with compras.transaccion() as cursor:
            cursor.execute("SELECT 1")
    simulacion.cursor.execute.assert_called_once_with("SELECT 1")
    assert compras.transaccion is original


def test_simular_bd_acepta_varios_destinos_con_los_mismos_mocks():
    with simular_bd(destinos=(SERVICE_PELICULAS, SERVICE_COMPRAS)) as simulacion:
        assert peliculas.ejecutar is db.ejecutar is simulacion.ejecutar
        assert compras.transaccion is db.transaccion is simulacion.transaccion


def test_simular_bd_rechaza_un_destino_sin_operaciones_de_base():
    with pytest.raises(ValueError, match="no importa ninguna operación"):
        with simular_bd(destinos=("src.backend.errores",)):
            pass


def test_simular_bd_no_deja_nada_parchado_si_falla_el_armado():
    originales = (db.consultar, db.consultar_uno, db._conectar, peliculas.consultar, peliculas.ejecutar)
    with pytest.raises(ValueError):
        with simular_bd(destinos=(SERVICE_PELICULAS, "src.backend.errores")):
            pass
    assert (db.consultar, db.consultar_uno, db._conectar, peliculas.consultar, peliculas.ejecutar) == originales


# --- transacción y cursor ---
def test_transaccion_simulada_se_puede_usar_varias_veces_con_el_mismo_cursor():
    with simular_bd() as simulacion:
        with db.transaccion() as primero:
            primero.execute("INSERT 1")
        with db.transaccion() as segundo:
            segundo.execute("INSERT 2")
        assert primero is segundo is simulacion.cursor
    assert simulacion.transaccion.call_count == 2
    assert [llamada.args[0] for llamada in simulacion.cursor.execute.call_args_list] == ["INSERT 1", "INSERT 2"]


def test_transaccion_simulada_propaga_excepciones_y_sigue_siendo_usable():
    with simular_bd() as simulacion:
        with pytest.raises(KeyError):
            with db.transaccion() as cursor:
                cursor.execute("INSERT 1")
                raise KeyError("falla")
        with db.transaccion() as cursor:
            cursor.execute("INSERT 2")
    assert simulacion.cursor.execute.call_count == 2


# --- restauración ---
def test_simular_bd_restaura_las_funciones_originales_al_salir():
    originales = {nombre: getattr(db, nombre) for nombre in ("consultar", "consultar_uno", "ejecutar", "transaccion", "_conectar")}
    with simular_bd():
        assert db.consultar is not originales["consultar"]
    assert {nombre: getattr(db, nombre) for nombre in originales} == originales


def test_simular_bd_restaura_las_funciones_originales_aunque_haya_una_excepcion():
    originales = (db.consultar, db.consultar_uno, db.ejecutar, db.transaccion, db._conectar,
                  peliculas.consultar, peliculas.consultar_uno, peliculas.ejecutar)
    with pytest.raises(RuntimeError):
        with simular_bd(destinos=(SERVICE_PELICULAS,)):
            raise RuntimeError("falla dentro de la prueba")
    assert (db.consultar, db.consultar_uno, db.ejecutar, db.transaccion, db._conectar,
            peliculas.consultar, peliculas.consultar_uno, peliculas.ejecutar) == originales


def test_simulaciones_sucesivas_son_independientes():
    with simular_bd() as primera:
        primera.consultar.return_value = [{"id": 1}]
        db.consultar("x")
    with simular_bd() as segunda:
        assert db.consultar("x") == []
        segunda.consultar.assert_called_once_with("x")
    assert primera is not segunda
    primera.consultar.assert_called_once_with("x")


# --- usuarios y tokens por rol ---
def test_usuario_de_prueba_tiene_id_y_rol_propios():
    assert usuario_de_prueba("admin") == {"id": ID_ADMIN, "nombre": "Admin", "rol": "admin"}
    assert usuario_de_prueba("cliente") == {"id": ID_CLIENTE, "nombre": "Cliente", "rol": "cliente"}
    assert usuario_de_prueba("admin") is not usuario_de_prueba("admin")


def test_cabeceras_por_rol_son_tokens_reales_firmados_con_el_id_de_cada_usuario(
        app_backend, usuarios, cabeceras_admin, cabeceras_cliente):
    serializador = URLSafeTimedSerializer(app_backend.config["SECRET_KEY"])
    assert cabeceras_admin != cabeceras_cliente
    assert serializador.loads(cabeceras_admin["Authorization"].removeprefix("Bearer "))["user_id"] == ID_ADMIN
    assert serializador.loads(cabeceras_cliente["Authorization"].removeprefix("Bearer "))["user_id"] == ID_CLIENTE
    assert cabeceras_de(usuarios["admin"]) == cabeceras_admin
    assert cabeceras_de(usuarios["cliente"]) == cabeceras_cliente


def test_cabecera_conserva_el_nombre_y_conducta_de_la_fixture_usuario(usuario, cabeceras, cabeceras_admin):
    assert usuario == {"id": ID_ADMIN, "nombre": "Admin", "rol": "admin"}
    assert cabeceras == cabeceras_admin


def test_simular_usuarios_busca_por_id_y_desconoce_los_demas(app_backend):
    admin, cliente = usuario_de_prueba("admin"), usuario_de_prueba("cliente")
    with simular_usuarios(admin, cliente) as consultar_uno:
        assert auth.consultar_uno("SELECT ...", (ID_ADMIN,)) is admin
        assert auth.consultar_uno("SELECT ...", (ID_CLIENTE,)) is cliente
        assert auth.consultar_uno("SELECT ...", (99,)) is None
        assert auth.consultar_uno("SELECT ...") is None
        assert consultar_uno.call_count == 4


def test_simular_usuarios_restaura_auth_aunque_haya_una_excepcion():
    original = auth.consultar_uno
    with pytest.raises(RuntimeError):
        with simular_usuarios(usuario_de_prueba("admin")):
            raise RuntimeError("falla")
    assert auth.consultar_uno is original


# --- endpoints reales: 401 / 403 / acceso por rol, sin base real ---
def endpoint_peliculas_en_bd_simulada():
    return simular_bd(destinos=(SERVICE_PELICULAS, SERVICE_COMPRAS))


def test_admin_y_cliente_en_la_misma_prueba_ven_cada_uno_su_permiso(
        cliente_backend, cabeceras_admin, cabeceras_cliente):
    with endpoint_peliculas_en_bd_simulada() as bd:
        admin_peliculas = cliente_backend.get(RUTA_PELICULAS, headers=cabeceras_admin)
        cliente_peliculas = cliente_backend.get(RUTA_PELICULAS, headers=cabeceras_cliente)
        admin_compras = cliente_backend.post(RUTA_COMPRAS, json={}, headers=cabeceras_admin)
        cliente_compras = cliente_backend.post(RUTA_COMPRAS, json={}, headers=cabeceras_cliente)
    assert admin_peliculas.status_code == 200
    assert admin_peliculas.get_json() == []
    afirmar_error_json(cliente_peliculas, 403, "SIN_PERMISO")
    afirmar_error_json(admin_compras, 403, "SIN_PERMISO")
    afirmar_error_json(cliente_compras, 400, "DATOS_INVALIDOS")  # pasó la autenticación; falla la validación
    bd.consultar.assert_called_once()  # solo el listado del admin llegó al service
    bd.conectar.assert_not_called()


def test_el_token_se_resuelve_por_user_id_en_la_base_de_usuarios(cliente_backend, app_backend, usuarios):
    with endpoint_peliculas_en_bd_simulada():
        admin = cliente_backend.get(RUTA_PELICULAS, headers=cabeceras_de(usuarios["admin"]))
        cliente = cliente_backend.get(RUTA_PELICULAS, headers=cabeceras_de(usuarios["cliente"]))
        desconocido = cliente_backend.get(RUTA_PELICULAS, headers=cabeceras_de({"id": 99}))
    assert admin.status_code == 200
    afirmar_error_json(cliente, 403, "SIN_PERMISO")
    afirmar_error_json(desconocido, 401, "TOKEN_INVALIDO")


def test_cambiar_el_rol_del_usuario_cambia_lo_que_ve_la_autenticacion(cliente_backend, usuario, cabeceras):
    with endpoint_peliculas_en_bd_simulada():
        assert cliente_backend.get(RUTA_PELICULAS, headers=cabeceras).status_code == 200
        usuario["rol"] = "cliente"
        afirmar_error_json(cliente_backend.get(RUTA_PELICULAS, headers=cabeceras), 403, "SIN_PERMISO")


@pytest.mark.parametrize("cabeceras_invalidas, codigo", [
    ({}, "NO_AUTENTICADO"),
    ({"Authorization": "Token abc"}, "NO_AUTENTICADO"),
    ({"Authorization": "Bearer cualquiera"}, "TOKEN_INVALIDO"),
])
def test_sin_token_o_con_token_invalido_devuelve_401_sin_tocar_la_base(
        cliente_backend, usuarios, cabeceras_invalidas, codigo):
    with endpoint_peliculas_en_bd_simulada() as bd:
        respuesta = cliente_backend.get(RUTA_PELICULAS, headers=cabeceras_invalidas)
    afirmar_error_json(respuesta, 401, codigo)
    bd.consultar.assert_not_called()
    bd.conectar.assert_not_called()


# --- helper de errores JSON ---
def test_afirmar_error_json_acepta_un_error_correcto():
    afirmar_error_json(respuesta_falsa(409, error_json("PELICULA_DUPLICADA", "Ya existe.")), 409, "PELICULA_DUPLICADA")


def test_afirmar_error_json_valida_el_mensaje_esperado_si_se_pasa():
    respuesta = respuesta_falsa(404, error_json("NO_ENCONTRADO", "No existe."))
    afirmar_error_json(respuesta, 404, "NO_ENCONTRADO", "No existe.")
    with pytest.raises(AssertionError, match="mensaje"):
        afirmar_error_json(respuesta, 404, "NO_ENCONTRADO", "Otro mensaje.")


def test_afirmar_error_json_acepta_una_respuesta_real_del_backend(cliente_backend):
    afirmar_error_json(cliente_backend.get(RUTA_PELICULAS), 401, "NO_AUTENTICADO", "Tenés que iniciar sesión.")


@pytest.mark.parametrize("respuesta, texto", [
    (respuesta_falsa(400, error_json("CODIGO")), "status"),
    (respuesta_falsa(409, None), "objeto JSON"),
    (respuesta_falsa(409, [error_json()]), "objeto JSON"),
    (respuesta_falsa(409, "error"), "objeto JSON"),
    (respuesta_falsa(409, {}), "solo la clave 'error'"),
    (respuesta_falsa(409, {**error_json(), "extra": 1}), "solo la clave 'error'"),
    (respuesta_falsa(409, {"error": "CODIGO"}), "no es un objeto"),
    (respuesta_falsa(409, {"error": {"codigo": "CODIGO"}}), "solo 'codigo' y 'mensaje'"),
    (respuesta_falsa(409, {"error": {"mensaje": "Mensaje."}}), "solo 'codigo' y 'mensaje'"),
    (respuesta_falsa(409, {"error": {"codigo": "CODIGO", "mensaje": "Mensaje.", "extra": 1}}), "solo 'codigo' y 'mensaje'"),
    (respuesta_falsa(409, error_json(codigo="")), "código"),
    (respuesta_falsa(409, error_json(codigo="  ")), "código"),
    (respuesta_falsa(409, error_json(codigo=409)), "código"),
    (respuesta_falsa(409, error_json(mensaje="")), "mensaje"),
    (respuesta_falsa(409, error_json(mensaje=None)), "mensaje"),
    (respuesta_falsa(409, error_json(mensaje=["x"])), "mensaje"),
    (respuesta_falsa(409, error_json(codigo="OTRO")), "Se esperaba el código"),
])
def test_afirmar_error_json_rechaza_formatos_invalidos(respuesta, texto):
    with pytest.raises(AssertionError, match=texto):
        afirmar_error_json(respuesta, 409, "CODIGO")
