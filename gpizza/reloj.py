"""Hora oficial de la app.

Todo el código que necesite "la hora actual" la pide aquí y no a datetime.now(). Así:
- siempre se usa la zona horaria de la sucursal (America/Mexico_City), y
- con GPIZZA_HORA_DEMO se puede simular la hora en pruebas o en una presentación
  antes de las 11:00 (RN-002). La hora simulada arranca en ese valor cuando inicia la app
  y desde ahí avanza normalmente, para que los contadores de 45 y 90 min sigan corriendo.

La base de datos usa la misma hora: bd.fijar_contexto() se la pasa como gpizza.ahora.
"""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from flask import current_app

from gpizza import reglas


def _desfase(real: datetime) -> timedelta:
    """Diferencia entre la hora simulada y la real; se calcula una vez por proceso."""
    demo = current_app.config.get('HORA_DEMO')
    if not demo:
        return timedelta(0)
    guardado = current_app.extensions.get('gpizza_desfase')
    if guardado is None:
        horas, minutos = (int(x) for x in demo.split(':'))
        inicio = real.replace(hour=horas, minute=minutos, second=0, microsecond=0)
        guardado = current_app.extensions['gpizza_desfase'] = inicio - real
    return guardado


def ahora() -> datetime:
    real = datetime.now(ZoneInfo(current_app.config['ZONA_HORARIA']))
    return real + _desfase(real)


def simulada() -> bool:
    return bool(current_app.config.get('HORA_DEMO'))


def en_horario(apertura: time = reglas.HORA_APERTURA, cierre: time = reglas.HORA_CIERRE) -> bool:
    """RN-002: ¿la hora actual está dentro del horario de pedidos?"""
    return apertura <= ahora().time() < cierre
