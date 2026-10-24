"""Configuración del frontend leída desde variables de entorno (.env)."""
import os

from dotenv import load_dotenv


def cargar_configuracion():
    load_dotenv()
    return {
        "SECRET_KEY": os.getenv("FRONTEND_SECRET_KEY", "dev-solo-para-desarrollo"),
        "BACKEND_URL": os.getenv("BACKEND_URL", "http://localhost:5000").rstrip("/"),
    }
