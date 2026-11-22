"""Pruebas del helper común de opciones de catálogos del frontend."""

from unittest.mock import patch

from src.frontend.routes import publico


def test_opciones_catalogo_llama_al_backend_y_convierte_los_textos():
    with patch(
        "src.frontend.routes.publico.llamar",
        return_value=(["Drama", " Animación ", "", None, 5], None),
    ) as llamar:
        opciones = publico._opciones_catalogo("generos")

    assert opciones == [
        {"valor": "Drama", "texto": "Drama"},
        {"valor": "Animación", "texto": "Animación"},
    ]

    llamar.assert_called_once_with("GET", "/api/catalogos/generos")


def test_opciones_catalogo_con_error_devuelve_lista_vacia():
    error = {
        "status": 503,
        "codigo": "BACKEND_NO_DISPONIBLE",
        "mensaje": "No se pudo conectar con el servidor.",
    }

    with patch(
        "src.frontend.routes.publico.llamar",
        return_value=(None, error),
    ):
        opciones = publico._opciones_catalogo("clasificaciones")

    assert opciones == []


def test_locales_reutiliza_el_helper_comun():
    with patch(
        "src.frontend.routes.publico._opciones_api",
        return_value=[],
    ) as opciones_api:
        publico._opciones_locales()

    opciones_api.assert_called_once_with(
        "/api/locales",
        publico._opcion_local,
    )