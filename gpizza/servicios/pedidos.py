"""CU-001 Registrar Pedido de Pizzas (RF-001) con su procesamiento de pago, y la confirmación o el
rechazo del cajero.

Las reglas se validan aquí para dar mensajes claros (RN-001 a RN-004, RN-008 a RN-010) y la base de
datos las vuelve a validar con sus triggers. Los precios y el total SIEMPRE se calculan en el servidor
con los precios vigentes de la BD: lo que mande el navegador solo son productos y cantidades (RN-007).
"""
import logging
import time
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError

from gpizza import reglas, reloj
from gpizza.extensiones import db
from gpizza.modelos import CodigoDescuento, DetallePedido, Empleado, Pedido, Producto, Sucursal
from gpizza.servicios import catalogo, clientes
from gpizza.servicios.errores import mensaje_bd

log_rendimiento = logging.getLogger('gpizza.rendimiento')

ESTADOS_EN_CURSO = ('Por Confirmar', 'En Preparación', 'Listo para Entrega', 'En Camino')


def dinero(valor) -> Decimal:
    return Decimal(valor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# ------------------------------------------------------------------------------ consultas

def sucursales_activas() -> list[Sucursal]:
    return db.session.scalars(select(Sucursal).where(Sucursal.activa).order_by(Sucursal.id_sucursal)).all()


def en_horario(sucursal: Sucursal) -> bool:
    """RN-002 con el horario propio de la sucursal (RNF-005: es un dato, no está en el código)."""
    return sucursal.hora_apertura <= reloj.ahora().time() < sucursal.hora_cierre


def cocineros(id_sucursal: int) -> list[Empleado]:
    return db.session.scalars(select(Empleado).where(
        Empleado.id_sucursal == id_sucursal, Empleado.puesto == 'Cocinero', Empleado.activo)
        .order_by(Empleado.nombre)).all()


def por_confirmar(id_sucursal: int) -> list[Pedido]:
    """Pedidos hechos en la app que esperan a un cajero, del más antiguo al más nuevo (boceto 7)."""
    return db.session.scalars(select(Pedido).where(
        Pedido.id_sucursal == id_sucursal, Pedido.estado == 'Por Confirmar').order_by(Pedido.fecha_registro)).all()


def contar_por_confirmar(id_sucursal: int) -> int:
    return db.session.scalar(select(func.count()).select_from(Pedido).where(
        Pedido.id_sucursal == id_sucursal, Pedido.estado == 'Por Confirmar'))


def del_sucursal(id_pedido: int, id_sucursal: int) -> Pedido | None:
    """El personal solo trabaja con pedidos de su sucursal."""
    pedido = db.session.get(Pedido, id_pedido)
    return pedido if pedido is not None and pedido.id_sucursal == id_sucursal else None


def del_cliente(folio: str, telefono: str) -> Pedido | None:
    """Un cliente solo puede ver sus propios pedidos."""
    pedido = db.session.scalar(select(Pedido).where(Pedido.folio == folio))
    if pedido is None or pedido.cliente.telefono != telefono:
        return None
    return pedido


def en_curso_del_cliente(telefono: str) -> Pedido | None:
    cliente = clientes.por_telefono(telefono)
    if cliente is None:
        return None
    return db.session.scalar(select(Pedido).where(Pedido.id_cliente == cliente.id_cliente,
                                                  Pedido.estado.in_(ESTADOS_EN_CURSO))
                             .order_by(Pedido.fecha_registro.desc()).limit(1))


# ------------------------------------------------------------------------------ cotización

@dataclass
class Linea:
    producto: Producto
    cantidad: int

    @property
    def importe(self) -> Decimal:
        return self.producto.precio * self.cantidad

    @property
    def nombre(self) -> str:
        return catalogo.nombre_producto(self.producto)


@dataclass
class Cotizacion:
    lineas: list[Linea] = field(default_factory=list)
    subtotal: Decimal = Decimal('0.00')
    descuento: Decimal = Decimal('0.00')
    codigo: CodigoDescuento | None = None
    monto_recibido: Decimal | None = None
    cambio: Decimal | None = None

    @property
    def total(self) -> Decimal:
        return self.subtotal - self.descuento


def leer_renglones(formulario) -> dict[int, int]:
    """Del formulario toma solo los campos cantidad_<id_producto>; ignora todo lo demás."""
    renglones = {}
    for clave, valor in formulario.items():
        if clave.startswith('cantidad_'):
            try:
                id_producto, cantidad = int(clave.removeprefix('cantidad_')), int(valor)
            except ValueError:
                continue
            if cantidad > 0:
                renglones[id_producto] = cantidad
    return renglones


def validar_codigo(texto: str, subtotal: Decimal) -> tuple[CodigoDescuento | None, Decimal, str | None]:
    """RN-008: el descuento solo existe con un código vigente del gerente, y cada código sirve una vez."""
    codigo = db.session.scalar(select(CodigoDescuento).where(CodigoDescuento.codigo == texto.strip().upper()))
    ahora = reloj.ahora()
    if codigo is None:
        return None, Decimal('0.00'), 'Ese código de descuento no existe.'
    if codigo.usado:
        return None, Decimal('0.00'), 'Ese código de descuento ya fue usado.'
    if not codigo.vigencia_inicio <= ahora < codigo.vigencia_fin:
        return None, Decimal('0.00'), 'Ese código de descuento no está vigente.'
    if codigo.tipo == 'PORCENTAJE':
        descuento = dinero(subtotal * codigo.valor / 100)
    else:
        descuento = min(codigo.valor, subtotal)
    return codigo, descuento, None


def cotizar(renglones: dict[int, int], codigo: str = '', forma_pago: str = '',
            monto_recibido: str = '') -> tuple[Cotizacion, dict[str, str]]:
    errores: dict[str, str] = {}
    cot = Cotizacion()
    productos = catalogo.productos_por_id(list(renglones))

    if not renglones:
        errores['productos'] = 'Agrega al menos un producto.'
    elif len(renglones) > reglas.MAX_PRODUCTOS_DISTINTOS:
        errores['productos'] = f'Máximo {reglas.MAX_PRODUCTOS_DISTINTOS} productos distintos por pedido (RN-003).'
    for id_producto, cantidad in renglones.items():
        producto = productos.get(id_producto)
        if producto is None or not producto.activo:
            errores['productos'] = 'Uno de los productos ya no existe en el menú.'
        elif not producto.disponible:
            errores['productos'] = f'"{catalogo.nombre_producto(producto)}" está agotado; elige otro (CU-001 FA-2).'
        elif cantidad > reglas.MAX_UNIDADES_POR_PRODUCTO:
            errores['productos'] = f'Máximo {reglas.MAX_UNIDADES_POR_PRODUCTO} unidades de cada producto (RN-003).'
        else:
            cot.lineas.append(Linea(producto, cantidad))
    cot.subtotal = sum((linea.importe for linea in cot.lineas), Decimal('0.00'))

    if 'productos' not in errores and cot.subtotal < reglas.PEDIDO_MINIMO:
        errores['productos'] = (f'El pedido mínimo es de ${reglas.PEDIDO_MINIMO} en productos; '
                                f'te faltan ${reglas.PEDIDO_MINIMO - cot.subtotal:.2f} (RN-001).')

    if codigo.strip():
        cot.codigo, cot.descuento, problema = validar_codigo(codigo, cot.subtotal)
        if problema:
            errores['codigo'] = problema

    if forma_pago not in reglas.FORMAS_PAGO:
        errores['pago'] = 'Elige una sola forma de pago: efectivo, tarjeta o transferencia (RN-009).'
    elif forma_pago == 'Efectivo':
        try:
            cot.monto_recibido = dinero((monto_recibido or '').replace('$', '').replace(',', '').strip())
        except InvalidOperation:
            errores['monto'] = 'Escribe con cuánto se paga, solo números (para calcular el cambio).'
        else:
            if cot.monto_recibido < cot.total:
                errores['monto'] = f'El pago debe cubrir el total de ${cot.total:.2f} (RN-010).'
            else:
                cot.cambio = cot.monto_recibido - cot.total  # RN-010: cambio automático
    return cot, errores


# ------------------------------------------------------------------------------ registro

@dataclass
class SolicitudPedido:
    id_sucursal: int
    cliente: clientes.DatosCliente
    renglones: dict[int, int]
    forma_pago: str
    codigo: str = ''
    monto_recibido: str = ''
    referencia_pago: str = ''
    origen: str = 'APP'
    id_cocinero: int | None = None
    tiempo_estimado_min: int | None = None


@dataclass
class Resultado:
    pedido: Pedido | None = None
    errores: dict[str, str] = field(default_factory=dict)
    segundos: float = 0.0
    cotizacion: Cotizacion | None = None


def registrar(solicitud: SolicitudPedido, id_cajero: int | None = None) -> Resultado:
    """Registra el pedido. Por la app queda "Por Confirmar"; por teléfono o en sucursal, el cajero
    lo confirma en el mismo paso ("En Preparación"). Mide su duración (RNF-001: < 3 s)."""
    inicio = time.perf_counter()
    errores: dict[str, str] = {}

    sucursal = db.session.get(Sucursal, solicitud.id_sucursal)
    if sucursal is None or not sucursal.activa:
        errores['sucursal'] = 'Elige una sucursal.'
    elif not en_horario(sucursal):
        errores['horario'] = (f'Los pedidos se reciben de {sucursal.hora_apertura:%H:%M} a '
                              f'{sucursal.hora_cierre:%H:%M} h (RN-002).')
    errores |= clientes.validar(_cliente_normalizado(solicitud.cliente))
    cot, errores_cot = cotizar(solicitud.renglones, solicitud.codigo, solicitud.forma_pago, solicitud.monto_recibido)
    errores |= errores_cot
    if solicitud.origen != 'APP':
        if solicitud.id_cocinero not in {c.id_empleado for c in cocineros(solicitud.id_sucursal)}:
            errores['cocinero'] = 'Elige el cocinero que preparará el pedido.'
        if solicitud.tiempo_estimado_min not in reglas.TIEMPOS_ESTIMADOS_MIN:
            errores['tiempo'] = 'Elige el tiempo estimado: 45 min, 1 h o 1 h 30.'
    if errores:
        return Resultado(errores=errores, cotizacion=cot)

    cliente, errores_cliente = clientes.registrar_o_actualizar(solicitud.cliente)
    if errores_cliente:
        return Resultado(errores=errores_cliente, cotizacion=cot)
    pedido = Pedido(
        id_sucursal=sucursal.id_sucursal, id_cliente=cliente.id_cliente, origen=solicitud.origen,
        direccion_entrega=clientes.direccion_completa(cliente),  # copia al momento del pedido
        latitud_entrega=cliente.latitud, longitud_entrega=cliente.longitud,
        subtotal=cot.subtotal, descuento=cot.descuento, total=cot.total, forma_pago=solicitud.forma_pago,
        monto_recibido=cot.monto_recibido, cambio=cot.cambio,
        referencia_pago=solicitud.referencia_pago.strip() or None,
        id_codigo_descuento=cot.codigo.id_codigo if cot.codigo else None,
        id_cajero=id_cajero if solicitud.origen != 'APP' else None,
        id_cocinero=solicitud.id_cocinero if solicitud.origen != 'APP' else None,
        tiempo_estimado_min=solicitud.tiempo_estimado_min if solicitud.origen != 'APP' else None,
        detalles=[DetallePedido(id_producto=linea.producto.id_producto, cantidad=linea.cantidad,
                                precio_unitario=linea.producto.precio, subtotal=linea.importe)
                  for linea in cot.lineas])
    db.session.add(pedido)
    try:
        db.session.commit()  # aquí también corren los triggers diferidos (RN-003, subtotal)
    except DBAPIError as error:
        db.session.rollback()
        return Resultado(errores={'general': mensaje_bd(error)}, cotizacion=cot)

    segundos = time.perf_counter() - inicio
    log_rendimiento.info('Pedido %s registrado en %.3f s (RNF-001: límite 3 s)', pedido.folio, segundos)
    return Resultado(pedido=pedido, segundos=segundos, cotizacion=cot)


def _cliente_normalizado(datos: clientes.DatosCliente) -> clientes.DatosCliente:
    datos.telefono = clientes.normalizar_telefono(datos.telefono)
    return datos


# ------------------------------------------------------------------------------ confirmación (cajero)

def _bloquear(id_pedido: int, id_sucursal: int) -> Pedido | None:
    """Toma el pedido con FOR UPDATE: si dos cajeros lo atienden a la vez, el segundo espera y ve
    el estado ya cambiado."""
    pedido = db.session.get(Pedido, id_pedido, with_for_update=True)
    if pedido is None or pedido.id_sucursal != id_sucursal:
        return None
    return pedido


def confirmar(id_pedido: int, id_sucursal: int, id_cajero: int, id_cocinero: int | None,
              tiempo: int | None) -> str | None:
    """Boceto 7: el cajero confirma eligiendo tiempo estimado y cocinero. Devuelve el problema o None."""
    pedido = _bloquear(id_pedido, id_sucursal)
    if pedido is None:
        return 'Ese pedido no existe en tu sucursal.'
    if pedido.estado != 'Por Confirmar':
        db.session.rollback()
        return f'El pedido {pedido.folio} ya fue atendido ({pedido.estado}).'
    if tiempo not in reglas.TIEMPOS_ESTIMADOS_MIN:
        db.session.rollback()
        return 'Elige el tiempo estimado que verá el cliente.'
    if id_cocinero not in {c.id_empleado for c in cocineros(id_sucursal)}:
        db.session.rollback()
        return 'Elige el cocinero que preparará el pedido.'
    pedido.estado = 'En Preparación'
    pedido.id_cajero, pedido.id_cocinero, pedido.tiempo_estimado_min = id_cajero, id_cocinero, tiempo
    return _guardar()


def rechazar(id_pedido: int, id_sucursal: int, id_cajero: int, motivo: str) -> str | None:
    pedido = _bloquear(id_pedido, id_sucursal)
    if pedido is None:
        return 'Ese pedido no existe en tu sucursal.'
    if pedido.estado != 'Por Confirmar':
        db.session.rollback()
        return f'El pedido {pedido.folio} ya fue atendido ({pedido.estado}).'
    if len((motivo or '').strip()) < 5:
        db.session.rollback()
        return 'Escribe el motivo del rechazo; el cliente lo verá.'
    pedido.estado, pedido.id_cajero, pedido.motivo_cancelacion = 'Rechazado', id_cajero, motivo.strip()[:200]
    return _guardar()


def retirar_por_cliente(pedido: Pedido) -> str | None:
    """Boceto 3: mientras nadie lo confirma, el cliente puede cancelar su pedido (RN-005, decisión 7)."""
    if pedido.estado != 'Por Confirmar':
        return 'El pedido ya está en preparación; la cancelación requiere el acuerdo del cajero.'
    pedido.estado, pedido.motivo_cancelacion = 'Cancelado', 'El cliente canceló antes de que se confirmara.'
    return _guardar()


def _guardar() -> str | None:
    try:
        db.session.commit()
    except DBAPIError as error:
        db.session.rollback()
        return mensaje_bd(error)
    return None
