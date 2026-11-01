"""Comandos de consola:  flask --app gpizza <comando>

  db-reset   borra y vuelve a crear las tablas, funciones y triggers (db/*.sql)
  db-seed    carga los datos de demostración (seed/datos_demo.py)
  desbloquear <usuario>   desbloquea una cuenta tras 3 intentos fallidos (RN-018)
  alertas    genera las alertas de 45 y 90 min y vence asignaciones sin aceptar
"""
import click
from flask import Flask, current_app
from sqlalchemy import text

from gpizza import bd
from gpizza.extensiones import db


def registrar_comandos(app: Flask) -> None:
    @app.cli.command('db-reset')
    @click.option('--si', is_flag=True, help='No pedir confirmación.')
    def db_reset(si):
        """Borra TODOS los datos y recrea el esquema."""
        nombre = db.engine.url.database
        if not si:
            click.confirm(f'Se borrarán todos los datos de la base "{nombre}". ¿Continuar?', abort=True)
        bd.recrear_esquema(db.engine)
        click.echo(f'Esquema recreado en "{nombre}" ({", ".join(bd.SCRIPTS)}).')

    @app.cli.command('db-seed')
    def db_seed():
        """Carga los datos de demostración (requiere un esquema recién creado)."""
        from seed.datos_demo import cargar
        resumen = cargar(db.engine, current_app)
        for linea in resumen:
            click.echo(linea)

    @app.cli.command('desbloquear')
    @click.argument('usuario')
    def desbloquear(usuario):
        """RN-018: desbloquea una cuenta (p. ej. la de un gerente, que no tiene a quién pedírselo)."""
        fila = db.session.execute(
            text('UPDATE empleado SET bloqueado = false WHERE username = :u RETURNING bloqueado'),
            {'u': usuario.strip().lower()}).first()
        db.session.commit()
        if fila is None:
            raise click.ClickException(f'No existe el usuario "{usuario}".')
        if fila.bloqueado:  # se confirma con lo que devolvió la BD, no se supone
            raise click.ClickException(f'La cuenta "{usuario}" sigue bloqueada.')
        click.echo(f'Cuenta "{usuario}" desbloqueada; sus intentos fallidos volvieron a 0.')

    @app.cli.command('alertas')
    def alertas():
        """RN-006 / RN-014: genera las alertas pendientes."""
        nuevas = db.session.execute(text('SELECT fn_generar_alertas()')).scalar_one()
        db.session.commit()
        click.echo(f'Alertas nuevas: {nuevas}')
