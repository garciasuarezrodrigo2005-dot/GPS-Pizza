"""Configuración de GPS.

Todos los valores salen de variables de entorno (archivo .env), para que la app se pueda
levantar en otra computadora o servidor sin tocar el código (RNF-008).
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / '.env')


def url_bd(nombre_bd: str) -> URL:
    """Arma la URL de conexión a PostgreSQL. URL.create escapa la contraseña aunque traiga
    caracteres especiales como @ o /."""
    return URL.create(
        'postgresql+psycopg',
        username=os.getenv('GPIZZA_DB_USER'),
        password=os.getenv('GPIZZA_DB_PASSWORD'),
        host=os.getenv('GPIZZA_DB_HOST', 'localhost'),
        port=int(os.getenv('GPIZZA_DB_PORT', '5432')),
        database=nombre_bd,
    )


class Config:
    SECRET_KEY = os.getenv('GPIZZA_SECRET_KEY')
    ZONA_HORARIA = os.getenv('GPIZZA_ZONA_HORARIA', 'America/Mexico_City')
    SQLALCHEMY_DATABASE_URI = url_bd(os.getenv('GPIZZA_DB_NAME', 'gpizza'))
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            # Si PostgreSQL no responde en 3 s, se reporta como caído en vez de colgar la app (RNF-002).
            'connect_timeout': 3,
            # La BD trabaja con la hora de la sucursal (horarios, alertas, reportes por día).
            'options': f'-c timezone={ZONA_HORARIA}',
        },
        # Descarta conexiones muertas (p. ej. tras reiniciar PostgreSQL) antes de usarlas.
        'pool_pre_ping': True,
    }

    HORA_DEMO = os.getenv('GPIZZA_HORA_DEMO') or None

    # Cookies de sesión: no accesibles desde JavaScript y no se envían desde otros sitios (RNF-003).
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    CARPETA_LOGS = RAIZ / 'logs'


class ConfigPruebas(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = url_bd(os.getenv('GPIZZA_DB_NAME_TEST', 'gpizza_test'))
