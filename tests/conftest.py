"""Configuración común de las pruebas: todas usan la base gpizza_test, nunca gpizza."""
import pytest
from sqlalchemy import create_engine, text

from gpizza import create_app
from gpizza.config import ConfigPruebas


def _bd_prueba_disponible() -> bool:
    try:
        motor = create_engine(ConfigPruebas.SQLALCHEMY_DATABASE_URI, connect_args={'connect_timeout': 3})
        with motor.connect() as conexion:
            conexion.execute(text('SELECT 1'))
        motor.dispose()
        return True
    except Exception:
        return False


BD_PRUEBA_DISPONIBLE = _bd_prueba_disponible()

requiere_bd = pytest.mark.skipif(
    not BD_PRUEBA_DISPONIBLE,
    reason='La base gpizza_test no existe o no responde (ver README, paso "Base de datos").')


@pytest.fixture
def crear_app():
    """Devuelve una función para crear apps de prueba con ajustes extra de configuración."""
    def _crear(**ajustes):
        config = type('ConfigAjustada', (ConfigPruebas,), ajustes)
        return create_app(config)
    return _crear


@pytest.fixture
def app(crear_app):
    return crear_app()


@pytest.fixture
def cliente(app):
    return app.test_client()
