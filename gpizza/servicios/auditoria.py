"""RN-019: consulta de la bitácora de auditoría (solo lectura).

Decisión 20: la consulta el Administrador, no el gerente (separación de funciones: quien autoriza
precios, devoluciones y altas no revisa su propia bitácora). Ve toda la cadena o una sucursal: lo
que hizo su personal y lo que pasó con sus pedidos (incluidas las acciones de los clientes, que no
tienen empleado). La bitácora no se puede editar ni borrar: lo impiden un trigger y los permisos de
la base de datos (db/03_auditoria.sql).
"""
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from flask import current_app
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import selectinload

from gpizza import reloj
from gpizza.extensiones import db
from gpizza.modelos import AsignacionEntrega, Auditoria, Devolucion, Empleado, Pedido

POR_PAGINA = 50
ACCIONES = ('CREAR', 'MODIFICAR', 'CANCELAR', 'LOGIN', 'LOGOUT', 'LOGIN_FALLIDO', 'BLOQUEO')
ENTIDADES = ('pedido', 'asignacion_entrega', 'devolucion', 'empleado', 'producto', 'codigo_descuento', 'sesion', 'cliente',
             'sucursal')


@dataclass
class FiltrosAuditoria:
    desde: date
    hasta: date
    accion: str = ''
    entidad: str = ''
    usuario: str = ''
    pagina: int = 1
    sucursal: int | None = None   # None: toda la cadena


def leer_filtros(args) -> FiltrosAuditoria:
    hoy = reloj.ahora().date()
    try:
        hasta = date.fromisoformat(args.get('hasta') or hoy.isoformat())
        desde = date.fromisoformat(args.get('desde') or hasta.isoformat())
    except ValueError:
        desde = hasta = hoy
    return FiltrosAuditoria(min(desde, hasta), max(desde, hasta),
                            args.get('accion') if args.get('accion') in ACCIONES else '',
                            args.get('entidad') if args.get('entidad') in ENTIDADES else '',
                            (args.get('usuario') or '').strip().lower()[:40], max(1, args.get('pagina', 1, type=int)),
                            args.get('sucursal', type=int))


def _de_la_sucursal(id_sucursal: int):
    return or_(
        Auditoria.id_empleado.in_(select(Empleado.id_empleado).where(Empleado.id_sucursal == id_sucursal)),
        and_(Auditoria.entidad == 'pedido',
             Auditoria.id_entidad.in_(select(Pedido.id_pedido).where(Pedido.id_sucursal == id_sucursal))),
        and_(Auditoria.entidad == 'asignacion_entrega', Auditoria.id_entidad.in_(
            select(AsignacionEntrega.id_asignacion).join(Pedido).where(Pedido.id_sucursal == id_sucursal))),
        and_(Auditoria.entidad == 'devolucion', Auditoria.id_entidad.in_(
            select(Devolucion.id_devolucion).join(Pedido).where(Pedido.id_sucursal == id_sucursal))),
        and_(Auditoria.entidad == 'sucursal', Auditoria.id_entidad == id_sucursal))


def consultar(f: FiltrosAuditoria) -> tuple[list[Auditoria], int]:
    """Devuelve (registros de la página, total de registros)."""
    zona = ZoneInfo(current_app.config['ZONA_HORARIA'])
    inicio = datetime.combine(f.desde, datetime.min.time(), zona)
    fin = datetime.combine(f.hasta + timedelta(days=1), datetime.min.time(), zona)

    condiciones = [Auditoria.fecha_hora >= inicio, Auditoria.fecha_hora < fin]
    if f.sucursal:
        condiciones.append(_de_la_sucursal(f.sucursal))
    if f.accion:
        condiciones.append(Auditoria.accion == f.accion)
    if f.entidad:
        condiciones.append(Auditoria.entidad == f.entidad)
    if f.usuario:
        condiciones.append(Auditoria.id_empleado.in_(select(Empleado.id_empleado).where(Empleado.username == f.usuario)))

    total = db.session.scalar(select(func.count()).select_from(Auditoria).where(*condiciones))
    registros = db.session.scalars(select(Auditoria).options(selectinload(Auditoria.empleado)).where(*condiciones)
                                   .order_by(Auditoria.id_log.desc())
                                   .offset((f.pagina - 1) * POR_PAGINA).limit(POR_PAGINA)).all()
    return registros, total


def _corto(valor) -> str:
    if valor is None:
        return '—'
    texto = valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False)
    if isinstance(valor, str) and len(valor) >= 16 and valor[4] == '-' and valor[10] == 'T':
        return valor[11:16]          # '2026-11-01T17:31:24.2-06:00' → '17:31'
    return texto if len(texto) <= 40 else texto[:37] + '…'


def resumen(detalle: dict | None) -> str:
    """{'estado': {'antes': 'Por Confirmar', 'despues': 'En Preparación'}} → 'estado: Por Confirmar → En Preparación'."""
    if not detalle:
        return ''
    if 'nuevo' in detalle:
        nuevo = detalle['nuevo'] or {}
        claves = [k for k in ('folio', 'estado', 'nombre', 'username', 'codigo', 'tipo', 'total', 'precio', 'motivo')
                  if nuevo.get(k) is not None]
        return ', '.join(f'{k}: {_corto(nuevo[k])}' for k in claves) or 'Registro nuevo'
    return '; '.join(f"{campo}: {_corto(c.get('antes'))} → {_corto(c.get('despues'))}"
                     for campo, c in detalle.items() if isinstance(c, dict))
