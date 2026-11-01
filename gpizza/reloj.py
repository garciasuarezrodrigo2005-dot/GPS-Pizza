"""Hora oficial de la app.

Todo el código que necesite "la hora actual" la pide aquí y no a datetime.now(). Así:
- siempre se usa la zona horaria de la sucursal (America/Mexico_City), y
- con GPIZZA_HORA_DEMO se puede simular la hora en pruebas o en una presentación
  antes de las 11:00 (RN-002).
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo

from flask import current_app

from gpizza import reglas


def ahora() -> datetime:
    zona = ZoneInfo(current_app.config['ZONA_HORARIA'])
    real = datetime.now(zona)
    demo = current_app.config.get('HORA_DEMO')
    if demo:
        horas, minutos = (int(x) for x in demo.split(':'))
        return real.replace(hour=horas, minute=minutos, second=0, microsecond=0)
    return real


def en_horario(apertura: time = reglas.HORA_APERTURA, cierre: time = reglas.HORA_CIERRE) -> bool:
    """RN-002: ¿la hora actual está dentro del horario de pedidos?"""
    return apertura <= ahora().time() < cierre
