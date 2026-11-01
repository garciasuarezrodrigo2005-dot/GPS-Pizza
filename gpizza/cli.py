"""Comandos de consola:  flask --app gpizza <comando>

  db-reset   borra y vuelve a crear las tablas, funciones y triggers (db/*.sql)
  db-seed    carga los datos de demostración (seed/datos_demo.py)
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

    @app.cli.command('alertas')
    def alertas():
        """RN-006 / RN-014: genera las alertas pendientes."""
        with db.engine.begin() as conexion:
            nuevas = conexion.execute(text('SELECT fn_generar_alertas()')).scalar_one()
        click.echo(f'Alertas nuevas: {nuevas}')
