"""GPizza: Sistema de Gestión de Pedidos a Domicilio de Yungla Pizza S.A. de C.V."""
from flask import Flask

from gpizza.bd import registrar_contexto_automatico
from gpizza.cli import registrar_comandos
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
    registrar_contexto_automatico()
    registrar_comandos(app)

    from gpizza.seguridad.acceso import cargar_usuario
    from gpizza.web import admin, auth, cajero, cliente, gerente, notificaciones, repartidor, seguimiento, sistema
    for modulo in (sistema, cliente, auth, cajero, repartidor, gerente, admin, notificaciones, seguimiento):
        app.register_blueprint(modulo.bp)
    app.before_request(cargar_usuario)
    from gpizza.servicios import ciclo
    from gpizza.web.filtros import registrar_filtros
    registrar_filtros(app)
    app.jinja_env.globals.update(alerta_pedido=ciclo.alerta, minutos_en_estado=ciclo.minutos_en_estado)

    @app.context_processor
    def _datos_globales():
        from flask import g
        return {'version': __version__, 'usuario': g.get('usuario')}

    return app
