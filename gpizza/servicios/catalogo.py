"""CU-010 Consultar Menú Digital (RF-002): catálogo agrupado como en el boceto.

En la BD cada tamaño es un producto (Pepperoni Mediana, Pepperoni Familiar...); en pantalla se
agrupan en una tarjeta por pizza con sus tamaños, como en el boceto de la página 2.
"""
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select

from gpizza.extensiones import db
from gpizza.modelos import Producto

ORDEN_TAMANOS = {'Personal': 1, 'Mediana': 2, 'Grande': 3, 'Familiar': 4}


@dataclass
class Opcion:
    id_producto: int
    tamano: str | None
    precio: Decimal
    disponible: bool
    codigo: str | None = None   # QR / código de barras (RF-009)


@dataclass
class Tarjeta:
    nombre: str
    descripcion: str | None
    categoria: str
    opciones: list[Opcion] = field(default_factory=list)

    @property
    def agotado(self) -> bool:
        return not any(o.disponible for o in self.opciones)


def menu() -> dict[str, list[Tarjeta]]:
    """{'Pizza': [...], 'Complemento': [...]} con solo productos activos (los agotados se muestran en gris)."""
    productos = db.session.scalars(select(Producto).where(Producto.activo).order_by(Producto.nombre)).all()
    tarjetas: dict[tuple[str, str], Tarjeta] = {}
    for p in productos:
        tarjeta = tarjetas.setdefault((p.categoria, p.nombre), Tarjeta(p.nombre, p.descripcion, p.categoria))
        tarjeta.opciones.append(Opcion(p.id_producto, p.tamano, p.precio, p.disponible, p.codigo_qr_barras))
    for t in tarjetas.values():
        t.opciones.sort(key=lambda o: ORDEN_TAMANOS.get(o.tamano, 0))
    resultado = {'Pizza': [], 'Complemento': []}
    for (categoria, _), tarjeta in tarjetas.items():
        resultado[categoria].append(tarjeta)
    return resultado


def productos_por_id(ids) -> dict[int, Producto]:
    if not ids:
        return {}
    return {p.id_producto: p for p in db.session.scalars(select(Producto).where(Producto.id_producto.in_(ids)))}


def nombre_producto(p: Producto) -> str:
    return f'{p.nombre} {p.tamano}' if p.tamano else p.nombre
