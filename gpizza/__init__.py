"""GPizza: Sistema de Gestión de Pedidos a Domicilio de Yungla Pizza S.A. de C.V."""
from flask import Flask

from gpizza.config import Config
from gpizza.extensiones import csrf, db
from gpizza.monitoreo import configurar_logs, registrar_medicion

__version__ = '0.1.0'


def create_app(config_class: type[Config] = Config) -> Flask:
    """Fábrica de la aplicación: arma una app nueva con la configuración indicada.
    Las pruebas la llaman con ConfigPruebas para usar la base gpizza_test."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    if not app.config.get('SECRET_KEY'):
        raise RuntimeError('Falta GPIZZA_SECRET_KEY en el archivo .env (ver README).')

    db.init_app(app)
    csrf.init_app(app)
    configurar_logs(app)
    registrar_medicion(app)

    from gpizza.web.cliente import bp as cliente_bp
    from gpizza.web.sistema import bp as sistema_bp
    app.register_blueprint(sistema_bp)
    app.register_blueprint(cliente_bp)

    @app.context_processor
    def _datos_globales():
        return {'version': __version__}

    return app
