"""Configuración del backend leída desde variables de entorno (.env)."""
import os

from dotenv import load_dotenv


def cargar_configuracion():
    """Devuelve un diccionario con la configuración de la app."""
    load_dotenv()
    return {
        "SECRET_KEY": os.getenv("SECRET_KEY", "dev-solo-para-desarrollo"),
        "DB_HOST": os.getenv("DB_HOST", "localhost"),
        "DB_PORT": int(os.getenv("DB_PORT", "3306")),
        "DB_USER": os.getenv("DB_USER", "root"),
        "DB_PASSWORD": os.getenv("DB_PASSWORD", ""),
        "DB_NAME": os.getenv("DB_NAME", "cine_paradiso"),
        "TMDB_API_KEY": os.getenv("TMDB_API_KEY", ""),
        "MINUTOS_RESERVA": int(os.getenv("MINUTOS_RESERVA", "10")),
        "HORAS_LIMITE_CANCELACION": int(os.getenv("HORAS_LIMITE_CANCELACION", "2")),
        "SMTP_HOST": os.getenv("SMTP_HOST", ""),
        "SMTP_PORT": int(os.getenv("SMTP_PORT", "587")),
        "SMTP_USER": os.getenv("SMTP_USER", ""),
        "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD", ""),
    }
