"""Comandos de consola:  flask --app gpizza <comando>

  db-reset   borra y vuelve a crear las tablas, funciones y triggers (db/*.sql)
  db-seed    carga los datos de demostración (seed/datos_demo.py)
  desbloquear <usuario>   desbloquea una cuenta tras 3 intentos fallidos (RN-018)
  nueva-sucursal          agrega una sucursal y su gerente solo con datos (RNF-005)
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

    @app.cli.command('nueva-sucursal')
    @click.option('--nombre', required=True, help='Nombre de la sucursal, p. ej. "Boca del Río".')
    @click.option('--direccion', required=True)
    @click.option('--ciudad', required=True)
    @click.option('--estado', default='Veracruz', show_default=True)
    @click.option('--radio', default=4.0, show_default=True, help='Radio de cobertura en km (dato para RNF-009).')
    @click.option('--apertura', default='11:00', show_default=True)
    @click.option('--cierre', default='22:00', show_default=True)
    @click.option('--gerente', 'usuario_gerente', required=True, help='Usuario del gerente, p. ej. gerente.bocadelrio')
    @click.option('--gerente-nombre', required=True)
    @click.option('--gerente-apellidos', required=True)
    @click.option('--gerente-telefono', required=True)
    def nueva_sucursal(nombre, direccion, ciudad, estado, radio, apertura, cierre, usuario_gerente, gerente_nombre,
                       gerente_apellidos, gerente_telefono):
        """RNF-005: agrega una sucursal y su gerente SOLO con datos, sin tocar el código."""
        from gpizza.modelos import Empleado, Sucursal
        from gpizza.seguridad.contrasenas import generar_hash
        from gpizza.servicios.personal import _vencida_desde_hoy, contrasena_temporal
        sucursal = Sucursal(nombre=nombre, direccion=direccion, ciudad=ciudad, estado=estado, radio_cobertura_km=radio,
                            hora_apertura=apertura, hora_cierre=cierre)
        db.session.add(sucursal)
        db.session.flush()
        temporal = contrasena_temporal()
        db.session.add(Empleado(id_sucursal=sucursal.id_sucursal, nombre=gerente_nombre, apellidos=gerente_apellidos,
                                telefono=gerente_telefono, puesto='Gerente', username=usuario_gerente.lower(),
                                password_hash=generar_hash(temporal), fecha_cambio_password=_vencida_desde_hoy()))
        try:
            db.session.commit()
        except Exception as error:
            db.session.rollback()
            raise click.ClickException(f'No se pudo crear la sucursal: {getattr(error, "orig", error)}')
        click.echo(f'Sucursal "{nombre}" creada (id {sucursal.id_sucursal}). Ya aparece para los clientes.')
        click.echo(f'Gerente: {usuario_gerente.lower()} · contraseña temporal: {temporal} (la cambiará al entrar).')
        click.echo('El gerente da de alta a su personal en "Personal". No hubo que modificar ni reiniciar la app.')

    @app.cli.command('crear-admin')
    @click.option('--usuario', required=True, help='Usuario del administrador, p. ej. admin.yungla')
    @click.option('--nombre', required=True)
    @click.option('--apellidos', required=True)
    @click.option('--telefono', required=True, help='10 dígitos.')
    def crear_admin(usuario, nombre, apellidos, telefono):
        """CU-011 (decisión 19): crea un Administrador. Es la única forma: no hay botón en la web, porque
        es la cuenta con más permisos del sistema."""
        from gpizza.modelos import Empleado
        from gpizza.seguridad.contrasenas import generar_hash
        from gpizza.servicios.personal import _vencida_desde_hoy, contrasena_temporal
        temporal = contrasena_temporal()
        db.session.add(Empleado(id_sucursal=None, nombre=nombre, apellidos=apellidos, telefono=telefono,
                                puesto='Administrador', username=usuario.strip().lower(),
                                password_hash=generar_hash(temporal), fecha_cambio_password=_vencida_desde_hoy()))
        try:
            db.session.commit()
        except Exception as error:
            db.session.rollback()
            raise click.ClickException(f'No se pudo crear el administrador: {getattr(error, "orig", error)}')
        click.echo(f'Administrador "{usuario.strip().lower()}" creado · contraseña temporal: {temporal}')
        click.echo('Deberá cambiarla al entrar. Desde /admin da de alta sucursales y gerentes.')

    @app.cli.command('alertas')
    def alertas():
        """RN-006 / RN-014 y CU-002 FA-2: alertas, asignaciones vencidas y reasignación."""
        from gpizza.servicios import ciclo
        nuevas = ciclo.revisar_tiempos(forzar=True)
        click.echo(f'Alertas nuevas: {nuevas}')
