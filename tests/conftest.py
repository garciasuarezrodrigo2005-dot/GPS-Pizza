"""Configuración común de las pruebas: todas usan la base gpizza_test, nunca gpizza."""
from datetime import datetime

import pytest
from sqlalchemy import create_engine, text

from gpizza import create_app
from gpizza.bd import fijar_contexto, recrear_esquema
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


# ---------------------------------------------------------------- base de datos con datos de demo

@pytest.fixture(scope='session')
def motor_demo():
    """Una vez por corrida: recrea el esquema de gpizza_test y carga los datos de demo."""
    if not BD_PRUEBA_DISPONIBLE:
        pytest.skip('La base gpizza_test no existe o no responde.')
    from seed.datos_demo import cargar
    app = create_app(ConfigPruebas)
    with app.app_context():
        from gpizza.extensiones import db
        recrear_esquema(db.engine)
        cargar(db.engine, app)
        motor = db.engine
        yield motor


@pytest.fixture
def con(motor_demo):
    """Conexión dentro de una transacción que se deshace al terminar la prueba:
    cada prueba ve los datos de demo intactos, haga lo que haga."""
    conexion = motor_demo.connect()
    transaccion = conexion.begin()
    yield conexion
    transaccion.rollback()
    conexion.close()


class Bd:
    """Atajos para escribir las pruebas de reglas de negocio en SQL."""

    def __init__(self, conexion):
        self.c = conexion

    def sql(self, consulta, **parametros):
        return self.c.execute(text(consulta), parametros)

    def valor(self, consulta, **parametros):
        return self.sql(consulta, **parametros).scalar()

    def como(self, rol=None, usuario=None, ahora: datetime | None = None):
        id_empleado = self.empleado(usuario) if isinstance(usuario, str) else usuario
        fijar_contexto(self.c, rol=rol, id_empleado=id_empleado, ahora=ahora)

    def empleado(self, usuario):
        return self.valor('SELECT id_empleado FROM empleado WHERE username = :u', u=usuario)

    def pedido(self, estado, sucursal='Coyol (matriz)', extra=''):
        """Un pedido de la demo en el estado indicado (el más reciente)."""
        return self.sql(
            'SELECT p.* FROM pedido p JOIN sucursal s USING (id_sucursal) '
            f'WHERE p.estado = :e AND s.nombre = :s {extra} ORDER BY p.fecha_registro DESC LIMIT 1',
            e=estado, s=sucursal).mappings().one()

    def debe_fallar(self, patron, consulta, **parametros):
        """Ejecuta la consulta dentro de un SAVEPOINT y exige que la BD la rechace con un
        mensaje que contenga el patrón. El SAVEPOINT permite seguir usando la transacción."""
        from sqlalchemy.exc import DBAPIError
        punto = self.c.begin_nested()
        with pytest.raises(DBAPIError, match=patron):
            self.c.execute(text(consulta), parametros)
            self.c.execute(text('SET CONSTRAINTS ALL IMMEDIATE'))  # dispara los triggers diferidos
        punto.rollback()


@pytest.fixture
def bd(con):
    return Bd(con)


# ---------------------------------------------------------------- app conectada a la BD de demo

@pytest.fixture
def app_bd(motor_demo, crear_app):
    """App de prueba cuya sesión de BD vive dentro de una transacción que se deshace al final.
    Los commit() de la app se vuelven SAVEPOINTs: la prueba ve sus propios cambios, pero
    gpizza_test queda igual para la siguiente prueba (intentos, sesiones, contraseñas...)."""
    from gpizza.extensiones import db
    app = crear_app()
    # Ojo: el contexto de la app NO se deja abierto durante la prueba. Si lo estuviera, Flask lo
    # reutilizaría en cada petición del test_client y compartiría `g` entre peticiones (por ejemplo,
    # el token CSRF), cosa que nunca pasa en la app real.
    with app.app_context():
        conexion = db.engine.connect()
        transaccion = conexion.begin()
        db.session.remove()
        db.session.configure(bind=conexion, join_transaction_mode='create_savepoint')
    try:
        yield app
    finally:
        with app.app_context():
            db.session.remove()
            db.session.configure(bind=None)
        transaccion.rollback()
        conexion.close()


@pytest.fixture
def web(app_bd):
    return app_bd.test_client()


def token_csrf(cliente_web, ruta='/login'):
    """Lee el token CSRF del formulario, como haría el navegador."""
    import re
    html = cliente_web.get(ruta).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def iniciar_sesion(cliente_web, usuario, contrasena='Pizza2026', **kwargs):
    return cliente_web.post('/login', data={'usuario': usuario, 'contrasena': contrasena,
                                            'csrf_token': token_csrf(cliente_web)}, **kwargs)
