"""Configuración del frontend leída desde variables de entorno (.env)."""
import os

from dotenv import load_dotenv


def cargar_configuracion():
    load_dotenv()
    return {
        "SECRET_KEY": os.getenv("FRONTEND_SECRET_KEY", "dev-solo-para-desarrollo"),
        "BACKEND_URL": os.getenv("BACKEND_URL", "http://localhost:5000").rstrip("/"),
        # Segundos de espera al backend; en hosting gratuito el primer pedido puede tardar por el arranque en frío.
        "BACKEND_TIMEOUT": float(os.getenv("BACKEND_TIMEOUT", "5")),
        # Misma variable que lee el backend: el perfil decide con ella si ofrece "Cancelar".
        "HORAS_LIMITE_CANCELACION": int(os.getenv("HORAS_LIMITE_CANCELACION", "2")),
    }
