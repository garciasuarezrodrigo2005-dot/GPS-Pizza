"""Filtros de Jinja para mostrar dinero y horas como en los bocetos, y el ícono de cada producto."""
import re
import unicodedata
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, current_app, url_for

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


def combine_pagina(argumentos: dict, pagina: int) -> dict:
    """Los mismos filtros de la URL con otra página (paginación de la auditoría)."""
    return argumentos | {'pagina': pagina}


def _clave_producto(nombre: str) -> str:
    """'Alitas BBQ (8 pzas)' -> 'alitas-bbq'; 'Ensalada César' -> 'ensalada-cesar'."""
    sin_parentesis = re.sub(r'\(.*?\)', '', nombre)
    sin_acentos = unicodedata.normalize('NFKD', sin_parentesis).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', sin_acentos.lower()).strip('-')


@lru_cache(maxsize=256)
def _archivo_icono(carpeta: str, nombre: str, categoria: str) -> str:
    clave = _clave_producto(nombre)
    if (Path(carpeta) / f'{clave}.svg').is_file():
        return f'img/productos/{clave}.svg'
    # Producto nuevo sin dibujo propio (RNF-005): ícono general de su categoría.
    return 'img/productos/pizza.svg' if categoria == 'Pizza' else 'img/productos/complemento.svg'


def icono_producto(nombre: str, categoria: str) -> str:
    """URL del dibujo del producto: cada pizza y complemento tiene el suyo en static/img/productos."""
    carpeta = str(Path(current_app.static_folder) / 'img' / 'productos')
    return url_for('static', filename=_archivo_icono(carpeta, nombre, categoria))


def registrar_filtros(app: Flask) -> None:
    for funcion in (dinero, hora, hace, telefono, minutos_desde, combine_pagina):
        app.add_template_filter(funcion)
    app.add_template_global(icono_producto)
