"""CU-004 Generar Reporte de Desempeño Operativo (RF-008).

Filtros: período y repartidor; la sucursal siempre es la del gerente (decisión 11). Todo se calcula
con consultas agregadas en PostgreSQL (COUNT, SUM, AVG, GROUP BY): no se traen los pedidos uno por
uno a Python, así el reporte se genera en mucho menos de los 5 s que pide CU-004.
"""
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from flask import current_app
from sqlalchemy import Date, cast, exists, func, select

from gpizza import reloj
from gpizza.extensiones import db
from gpizza.modelos import AsignacionEntrega, DetallePedido, Devolucion, Empleado, Pedido, Producto

MAX_DIAS = 366


@dataclass
class Filtros:
    desde: date
    hasta: date
    id_repartidor: int | None = None


@dataclass
class Reporte:
    filtros: Filtros
    total: int = 0
    entregados: int = 0
    cancelados: int = 0
    rechazados: int = 0
    devoluciones: int = 0
    ingresos: Decimal = Decimal('0.00')
    ticket_promedio: Decimal = Decimal('0.00')
    minutos_entrega: float | None = None
    pizza_mas_vendida: tuple[str, int] | None = None
    por_dia: list[tuple[date, int]] = field(default_factory=list)
    por_repartidor: list[dict] = field(default_factory=list)
    segundos: float = 0.0

    @property
    def vacio(self) -> bool:
        return self.total == 0


def leer_filtros(args) -> tuple[Filtros, str | None]:
    """Por omisión, los últimos 7 días. Devuelve los filtros y un problema si las fechas no sirven."""
    hoy = reloj.ahora().date()
    try:
        hasta = date.fromisoformat(args.get('hasta') or hoy.isoformat())
        desde = date.fromisoformat(args.get('desde') or (hasta - timedelta(days=6)).isoformat())
    except ValueError:
        return Filtros(hoy - timedelta(days=6), hoy), 'Escribe las fechas con el calendario (día/mes/año).'
    id_repartidor = args.get('id_repartidor', type=int)  # args es el MultiDict de Flask
    if desde > hasta:
        return Filtros(hasta, desde, id_repartidor), 'La fecha inicial era posterior a la final; se invirtieron.'
    if (hasta - desde).days >= MAX_DIAS:
        return Filtros(hasta - timedelta(days=MAX_DIAS - 1), hasta, id_repartidor), 'El período máximo es de un año.'
    return Filtros(desde, hasta, id_repartidor), None


def repartidores(id_sucursal: int) -> list[Empleado]:
    return db.session.scalars(select(Empleado).where(Empleado.id_sucursal == id_sucursal,
                                                     Empleado.puesto == 'Repartidor').order_by(Empleado.nombre)).all()


def _minutos(intervalo):
    return func.extract('epoch', intervalo) / 60


def generar(id_sucursal: int, filtros: Filtros) -> Reporte:
    inicio_reloj = time.perf_counter()
    zona = ZoneInfo(current_app.config['ZONA_HORARIA'])
    inicio = datetime.combine(filtros.desde, datetime.min.time(), zona)
    fin = datetime.combine(filtros.hasta + timedelta(days=1), datetime.min.time(), zona)

    condiciones = [Pedido.id_sucursal == id_sucursal, Pedido.fecha_registro >= inicio, Pedido.fecha_registro < fin]
    if filtros.id_repartidor:
        # Pedidos que ese repartidor aceptó (los entregó o se cancelaron en su ruta).
        condiciones.append(exists().where(AsignacionEntrega.id_pedido == Pedido.id_pedido,
                                          AsignacionEntrega.id_repartidor == filtros.id_repartidor,
                                          AsignacionEntrega.fecha_confirmacion.is_not(None)))
    ids = select(Pedido.id_pedido).where(*condiciones)
    reporte = Reporte(filtros)

    entregado = Pedido.estado == 'Entregado'
    fila = db.session.execute(select(
        func.count(),
        func.count().filter(entregado),
        func.count().filter(Pedido.estado == 'Cancelado'),
        func.count().filter(Pedido.estado == 'Rechazado'),
        func.coalesce(func.sum(Pedido.total).filter(entregado), 0),
        func.avg(_minutos(Pedido.fecha_entrega - Pedido.fecha_preparacion)).filter(entregado),
    ).where(*condiciones)).one()
    (reporte.total, reporte.entregados, reporte.cancelados, reporte.rechazados,
     reporte.ingresos, minutos) = fila
    reporte.ingresos = Decimal(reporte.ingresos).quantize(Decimal('0.01'))
    reporte.minutos_entrega = round(float(minutos), 1) if minutos is not None else None
    if reporte.entregados:
        reporte.ticket_promedio = (reporte.ingresos / reporte.entregados).quantize(Decimal('0.01'))

    reporte.devoluciones = db.session.scalar(select(func.count()).select_from(Devolucion)
                                             .where(Devolucion.id_pedido.in_(ids)))

    pizza = db.session.execute(
        select(Producto.nombre, func.sum(DetallePedido.cantidad).label('unidades'))
        .join(DetallePedido.producto).join(DetallePedido.pedido)
        .where(Producto.categoria == 'Pizza', entregado, DetallePedido.id_pedido.in_(ids))
        .group_by(Producto.nombre).order_by(func.sum(DetallePedido.cantidad).desc(), Producto.nombre).limit(1)).first()
    reporte.pizza_mas_vendida = (pizza.nombre, int(pizza.unidades)) if pizza else None

    # Pedidos por día (la fecha se toma en la zona horaria de la sucursal, que es la de la sesión de la BD).
    dia = cast(Pedido.fecha_registro, Date)
    conteo = dict(db.session.execute(select(dia, func.count()).where(*condiciones).group_by(dia)).all())
    reporte.por_dia = [(filtros.desde + timedelta(days=i), conteo.get(filtros.desde + timedelta(days=i), 0))
                       for i in range((filtros.hasta - filtros.desde).days + 1)]

    # Detalle por repartidor (boceto 10): entregas, tiempo promedio en camino y devoluciones.
    devuelto = exists().where(Devolucion.id_pedido == AsignacionEntrega.id_pedido)
    filas = db.session.execute(
        select(Empleado.id_empleado, Empleado.nombre, Empleado.apellidos, func.count(),
               func.avg(_minutos(AsignacionEntrega.fecha_hora_entrega - AsignacionEntrega.fecha_confirmacion)),
               func.count().filter(devuelto))
        .join(AsignacionEntrega.repartidor)
        .where(AsignacionEntrega.estado == 'ENTREGADA', AsignacionEntrega.id_pedido.in_(ids))
        .group_by(Empleado.id_empleado, Empleado.nombre, Empleado.apellidos)
        .order_by(func.count().desc(), Empleado.nombre)).all()
    reporte.por_repartidor = [{'nombre': f'{n} {a}', 'entregas': e, 'minutos': round(float(m), 1) if m is not None else None,
                               'devoluciones': d} for _, n, a, e, m, d in filas]

    reporte.segundos = time.perf_counter() - inicio_reloj
    current_app.logger.info('Reporte %s–%s generado en %.3f s', filtros.desde, filtros.hasta, reporte.segundos)
    return reporte
