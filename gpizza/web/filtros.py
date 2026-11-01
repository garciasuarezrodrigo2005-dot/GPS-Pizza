"""Filtros de Jinja para mostrar dinero y horas como en los bocetos."""
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from flask import Flask, current_app

from gpizza import reloj


def dinero(valor) -> str:
    """Decimal('1408.5') -> '$ 1,408.50' (formato de los bocetos)."""
    return f'$ {Decimal(valor or 0):,.2f}'


def hora(momento: datetime | None) -> str:
    if momento is None:
        return ''
    return momento.astimezone(ZoneInfo(current_app.config['ZONA_HORARIA'])).strftime('%H:%M')


def minutos_desde(momento: datetime | None) -> int:
    if momento is None:
        return 0
    return max(0, int((reloj.ahora() - momento).total_seconds() // 60))


def hace(momento: datetime | None) -> str:
    """'Hace 4 min' como en la tarjeta del cajero (boceto 7)."""
    minutos = minutos_desde(momento)
    if minutos < 1:
        return 'Hace un momento'
    if minutos < 60:
        return f'Hace {minutos} min'
    return f'Hace {minutos // 60} h {minutos % 60:02d} min'


def telefono(numero: str | None) -> str:
    """'2295865835' -> '229 586 5835'."""
    if not numero or len(numero) != 10:
        return numero or ''
    return f'{numero[:3]} {numero[3:6]} {numero[6:]}'


def registrar_filtros(app: Flask) -> None:
    for funcion in (dinero, hora, hace, telefono, minutos_desde):
        app.add_template_filter(funcion)
