"""Pruebas de consistencia de los archivos de instalación desde cero (SCRUM-84)."""
import re
from pathlib import Path

from src.backend.config import cargar_configuracion as config_backend
from src.frontend.config import cargar_configuracion as config_frontend

RAIZ = Path(__file__).resolve().parents[2]


def test_requirements_tiene_todas_las_dependencias_con_version_fija():
    lineas = [
        linea.strip()
        for linea in (RAIZ / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if linea.strip() and not linea.strip().startswith("#")
    ]
    assert lineas
    for linea in lineas:
        assert re.fullmatch(r"[A-Za-z0-9_.-]+==[0-9][A-Za-z0-9_.-]*", linea), (
            f"La dependencia {linea!r} debe tener versión fija con ==."
        )


def test_env_example_define_todas_las_variables_de_backend_y_frontend():
    contenido = (RAIZ / ".env.example").read_text(encoding="utf-8")
    claves_definidas = {
        linea.split("=", 1)[0].strip()
        for linea in contenido.splitlines()
        if "=" in linea and not linea.lstrip().startswith("#")
    }
    esperadas = set(config_backend().keys()) | {"FRONTEND_SECRET_KEY", "BACKEND_URL", "BACKEND_TIMEOUT"}
    faltantes = esperadas - claves_definidas
    assert not faltantes, f"Faltan variables en .env.example: {sorted(faltantes)}"
    assert set(config_frontend().keys()) == {
        "SECRET_KEY", "BACKEND_URL", "BACKEND_TIMEOUT", "HORAS_LIMITE_CANCELACION",
    }


def test_init_sh_referencia_scripts_sql_y_requirements_existentes():
    init_sh = (RAIZ / "init.sh").read_text(encoding="utf-8")
    for ruta_relativa in ("requirements.txt", ".env.example", "src/backend/db/schema.sql", "src/backend/db/seed.sql"):
        assert ruta_relativa in init_sh
        assert (RAIZ / ruta_relativa).is_file()


def test_readme_documenta_instalacion_ejecucion_pruebas_y_usuarios_del_seed():
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    for fragmento in (
        "bash init.sh",
        "bash init.sh --db",
        "flask --app src.backend.app run --port 5000",
        "flask --app src.frontend.app run --port 5001",
        "python -m pytest src/tests -v",
        "admin@cineparadiso.com",
        "ana@mail.com",
    ):
        assert fragmento in readme
