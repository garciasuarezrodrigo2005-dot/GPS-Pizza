"""Extensiones de Flask compartidas por toda la app.

Se crean aquí sin app y se conectan en create_app(); así cualquier módulo puede importarlas
sin provocar importaciones circulares.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
csrf = CSRFProtect()
