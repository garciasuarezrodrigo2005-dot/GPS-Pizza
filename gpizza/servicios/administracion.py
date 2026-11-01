"""Catálogo y precios (RF-002, RN-007), códigos de descuento (RN-008) y devoluciones (RF-011, RN-015).
Todo esto solo lo hace el gerente; la base de datos lo vuelve a exigir con sus triggers."""
import secrets
import string
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import selectinload

from gpizza import reglas, reloj
from gpizza.extensiones import db
from gpizza.modelos import CodigoDescuento, Devolucion, Empleado, Pedido, Producto
from gpizza.servicios.catalogo import ORDEN_TAMANOS
from gpizza.servicios.errores import mensaje_bd

TAMANOS = tuple(ORDEN_TAMANOS)


def _precio(texto) -> Decimal | None:
    try:
        valor = Decimal(str(texto).replace('$', '').replace(',', '').strip()).quantize(Decimal('0.01'))
    except InvalidOperation:
        return None
    return valor if Decimal('0') < valor <= Decimal('9999') else None


# ------------------------------------------------------------------------------ catálogo

def productos() -> list[Producto]:
    todos = db.session.scalars(select(Producto)).all()
    return sorted(todos, key=lambda p: (p.categoria != 'Pizza', p.nombre, ORDEN_TAMANOS.get(p.tamano, 0)))


def actualizar_producto(id_producto: int, precio: str, disponible: bool, activo: bool) -> str | None:
    """RN-007: el precio solo lo cambia el gerente (esta ruta y el trigger trg_producto_gerente)."""
    producto = db.session.get(Producto, id_producto)
    if producto is None:
        return 'Ese producto no existe.'
    nuevo = _precio(precio)
    if nuevo is None:
        return 'Escribe un precio válido (mayor que 0).'
    producto.precio, producto.disponible, producto.activo = nuevo, disponible, activo
    return _guardar()


def crear_producto(nombre: str, descripcion: str, categoria: str, tamano: str, precio: str) -> dict[str, str]:
    errores = {}
    if not (nombre or '').strip():
        errores['nombre'] = 'Escribe el nombre del producto.'
    if categoria not in ('Pizza', 'Complemento'):
        errores['categoria'] = 'Elige pizza o complemento.'
    if categoria == 'Pizza' and tamano not in TAMANOS:
        errores['tamano'] = 'Las pizzas llevan tamaño.'
    valor = _precio(precio)
    if valor is None:
        errores['precio'] = 'Escribe un precio válido (mayor que 0).'
    if errores:
        return errores
    siguiente = (db.session.scalar(select(func.max(Producto.id_producto))) or 0) + 1
    db.session.add(Producto(nombre=nombre.strip(), descripcion=(descripcion or '').strip() or None, categoria=categoria,
                            tamano=tamano if categoria == 'Pizza' else None, precio=valor,
                            codigo_qr_barras=f'YP{siguiente:06d}'))
    problema = _guardar()
    return {'general': problema} if problema else {}


# ------------------------------------------------------------------------------ códigos de descuento

def codigos(id_sucursal: int) -> list[CodigoDescuento]:
    """Los códigos que emitieron los gerentes de esta sucursal, del más reciente al más antiguo."""
    return db.session.scalars(select(CodigoDescuento).join(Empleado, Empleado.id_empleado == CodigoDescuento.id_gerente)
                              .where(Empleado.id_sucursal == id_sucursal)
                              .order_by(CodigoDescuento.vigencia_inicio.desc(), CodigoDescuento.id_codigo.desc())).all()


def estado_codigo(codigo: CodigoDescuento) -> str:
    if codigo.usado:
        return 'Usado'
    ahora = reloj.ahora()
    if ahora < codigo.vigencia_inicio:
        return 'Programado'
    return 'Vigente' if ahora < codigo.vigencia_fin else 'Vencido'


def emitir_codigo(id_gerente: int, tipo: str, valor: str, dias: str, texto: str = '') -> tuple[str | None, dict]:
    """RN-008: solo el gerente emite códigos; cada uno sirve para un solo pedido."""
    errores = {}
    if tipo not in ('PORCENTAJE', 'MONTO'):
        errores['tipo'] = 'Elige porcentaje o monto fijo.'
    numero = _precio(valor)
    if numero is None or (tipo == 'PORCENTAJE' and numero > 100):
        errores['valor'] = 'El porcentaje va de 1 a 100; el monto debe ser mayor que 0.'
    try:
        dias_vigencia = int(dias)
        if not 1 <= dias_vigencia <= 90:
            raise ValueError
    except (TypeError, ValueError):
        errores['dias'] = 'La vigencia va de 1 a 90 días.'
    codigo = (texto or '').strip().upper() or 'YP-' + ''.join(secrets.choice(string.ascii_uppercase + string.digits)
                                                              for _ in range(6))
    if not 4 <= len(codigo) <= 20 or not all(c.isalnum() or c == '-' for c in codigo):
        errores['codigo'] = 'El código lleva de 4 a 20 letras, números o guiones.'
    if errores:
        return None, errores
    ahora = reloj.ahora()
    db.session.add(CodigoDescuento(codigo=codigo, id_gerente=id_gerente, tipo=tipo, valor=numero,
                                   vigencia_inicio=ahora, vigencia_fin=ahora + timedelta(days=dias_vigencia)))
    problema = _guardar()
    return (None, {'codigo': problema}) if problema else (codigo, {})


# ------------------------------------------------------------------------------ devoluciones

def devoluciones(id_sucursal: int, limite: int = 50) -> list[Devolucion]:
    return db.session.scalars(select(Devolucion).join(Pedido).where(Pedido.id_sucursal == id_sucursal)
                              .order_by(Devolucion.fecha_hora.desc()).limit(limite)).all()


def pedidos_devolvibles(id_sucursal: int) -> list[Pedido]:
    """RN-015: entregados hace 2 h o menos y sin devolución registrada."""
    limite = reloj.ahora() - timedelta(hours=reglas.PLAZO_DEVOLUCION_HORAS)
    ya_devueltos = select(Devolucion.id_pedido)
    return db.session.scalars(select(Pedido).options(selectinload(Pedido.cliente))
                              .where(Pedido.id_sucursal == id_sucursal, Pedido.estado == 'Entregado',
                                     Pedido.fecha_entrega >= limite, Pedido.id_pedido.not_in(ya_devueltos))
                              .order_by(Pedido.fecha_entrega.desc())).all()


def registrar_devolucion(id_pedido: int, id_sucursal: int, id_gerente: int, motivo: str, accion: str) -> str | None:
    pedido = db.session.get(Pedido, id_pedido)
    if pedido is None or pedido.id_sucursal != id_sucursal:
        return 'Ese pedido no existe en tu sucursal.'
    if len((motivo or '').strip()) < 5 or len((accion or '').strip()) < 5:
        return 'Escribe el motivo y la acción correctiva.'
    db.session.add(Devolucion(id_pedido=id_pedido, id_gerente=id_gerente, motivo=motivo.strip()[:200],
                              accion_correctiva=accion.strip()[:200]))
    return _guardar()


def _guardar() -> str | None:
    try:
        db.session.commit()
    except DBAPIError as error:
        db.session.rollback()
        return mensaje_bd(error)
    return None
