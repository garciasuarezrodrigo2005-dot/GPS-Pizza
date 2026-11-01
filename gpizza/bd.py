"""Utilidades de base de datos: aplicar el esquema y decirle a los triggers quién actúa.

Los triggers de db/*.sql leen tres valores de la transacción:
- gpizza.rol          'Cliente', 'Cajero', 'Repartidor', 'Gerente' (sin valor = 'Sistema')
- gpizza.id_empleado  quién hace la acción (para la auditoría, RN-019)
- gpizza.ahora        la hora oficial, solo cuando está simulada (GPIZZA_HORA_DEMO)
"""
from datetime import datetime
from pathlib import Path

from sqlalchemy import Connection, Engine, event, text
from sqlalchemy.orm import Session

CARPETA_SQL = Path(__file__).resolve().parent.parent / 'db'
SCRIPTS = ('01_esquema.sql', '02_funciones.sql', '03_auditoria.sql')


def recrear_esquema(motor: Engine) -> None:
    """Borra TODO el esquema public y lo vuelve a crear con los scripts de db/.

    Los scripts se mandan con el cursor de psycopg directamente (sin parámetros), porque
    el código PL/pgSQL usa '%' en format() y SQLAlchemy lo confundiría con un parámetro.
    """
    conexion = motor.raw_connection()
    try:
        with conexion.cursor() as cursor:
            cursor.execute('DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;')
            for nombre in SCRIPTS:
                cursor.execute((CARPETA_SQL / nombre).read_text(encoding='utf-8'))
        conexion.commit()
    finally:
        conexion.close()


def fijar_contexto(conexion: Connection | Session, rol: str | None = None,
                   id_empleado: int | None = None, ahora: datetime | None = None) -> None:
    """Fija el contexto de la transacción actual (dura hasta el COMMIT o ROLLBACK)."""
    conexion.execute(
        text("SELECT set_config('gpizza.rol', :rol, true), "
             "set_config('gpizza.id_empleado', :emp, true), "
             "set_config('gpizza.ahora', :ahora, true)"),
        {'rol': rol or '', 'emp': '' if id_empleado is None else str(id_empleado),
         'ahora': ahora.isoformat() if ahora else ''})


def registrar_contexto_automatico() -> None:
    """Cada transacción de la app recibe el usuario de la petición (g.usuario, desde la Fase 2)
    y la hora simulada si GPIZZA_HORA_DEMO está activa."""
    if event.contains(Session, 'after_begin', _al_iniciar):
        return  # create_app() se llama varias veces en las pruebas; se registra una sola vez
    event.listen(Session, 'after_begin', _al_iniciar)


def _al_iniciar(_sesion, _transaccion, conexion):
    from flask import g, has_app_context

    from gpizza import reloj
    if not has_app_context():
        return
    usuario = g.get('usuario')
    fijar_contexto(conexion,
                   rol=getattr(usuario, 'rol', None) or g.get('rol_bd'),
                   id_empleado=getattr(usuario, 'id_empleado', None),
                   ahora=reloj.ahora() if reloj.simulada() else None)
