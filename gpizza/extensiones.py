"""Extensiones de Flask compartidas por toda la app.

Se crean aquí sin app y se conectan en create_app(); así cualquier módulo puede importarlas
sin provocar importaciones circulares.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy.session import Session as SesionFlask
from flask_wtf.csrf import CSRFProtect


class SesionGPizza(SesionFlask):
    """Sesión de SQLAlchemy que respeta una conexión fija si se le da una.

    Solo las pruebas la usan así: conectan la app a una transacción que se deshace al final,
    para que cada prueba deje la base gpizza_test como estaba (tests/conftest.py).
    """

    def get_bind(self, *args, **kwargs):
        if self.bind is not None:
            return self.bind
        return super().get_bind(*args, **kwargs)


db = SQLAlchemy(session_options={'class_': SesionGPizza})
csrf = CSRFProtect()
