"""Clases de SQLAlchemy para las 12 tablas del modelo de datos.

El esquema lo crean los scripts de db/*.sql (con sus CHECK y triggers); estas clases solo
describen las tablas para usarlas desde Python. Por eso nunca se llama a db.create_all().

FetchedValue() marca las columnas que llena la base de datos (DEFAULT o trigger): después de
un INSERT o UPDATE, SQLAlchemy las vuelve a leer en vez de suponer su valor.
"""
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (BigInteger, Boolean, Date, DateTime, FetchedValue, ForeignKey, Identity, Integer,
                        LargeBinary, Numeric, SmallInteger, String, Time, TypeDecorator)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gpizza.extensiones import db
from gpizza.seguridad.cifrado import cifrar, descifrar


class TextoCifrado(TypeDecorator):
    """Texto que se guarda cifrado con Fernet (RNF-003): en Python es un str, en la BD son bytes."""
    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, valor, _dialecto):
        return None if valor is None else cifrar(valor)

    def process_result_value(self, valor, _dialecto):
        return None if valor is None else descifrar(valor)


def _pk():
    return mapped_column(Integer, Identity(always=True), primary_key=True)


def _servidor(tipo, **kwargs):
    """Columna cuyo valor pone la base de datos (DEFAULT o trigger)."""
    return mapped_column(tipo, server_default=FetchedValue(), server_onupdate=FetchedValue(), **kwargs)


class Sucursal(db.Model):
    __tablename__ = 'sucursal'
    id_sucursal: Mapped[int] = _pk()
    nombre: Mapped[str] = mapped_column(String(80))
    direccion: Mapped[str] = mapped_column(String(200))
    ciudad: Mapped[str] = mapped_column(String(60))
    estado: Mapped[str] = mapped_column(String(60))
    radio_cobertura_km: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    hora_apertura: Mapped[time] = _servidor(Time)
    hora_cierre: Mapped[time] = _servidor(Time)
    activa: Mapped[bool] = _servidor(Boolean)


class Empleado(db.Model):
    __tablename__ = 'empleado'
    __mapper_args__ = {'eager_defaults': True}
    id_empleado: Mapped[int] = _pk()
    id_sucursal: Mapped[int | None] = mapped_column(ForeignKey('sucursal.id_sucursal'))  # None: Administrador
    nombre: Mapped[str] = mapped_column(String(60))
    apellidos: Mapped[str] = mapped_column(String(80))
    telefono: Mapped[str] = mapped_column(String(10))
    puesto: Mapped[str] = mapped_column(String(13))
    username: Mapped[str | None] = mapped_column(String(40))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    fecha_cambio_password: Mapped[date | None] = mapped_column(Date)
    intentos_fallidos: Mapped[int] = _servidor(SmallInteger)
    bloqueado: Mapped[bool] = _servidor(Boolean)
    disponible: Mapped[bool | None] = mapped_column(Boolean)
    latitud_actual: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitud_actual: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    fecha_alta: Mapped[date] = _servidor(Date)
    activo: Mapped[bool] = _servidor(Boolean)

    sucursal: Mapped[Sucursal | None] = relationship()

    @property
    def nombre_completo(self) -> str:
        return f'{self.nombre} {self.apellidos}'


class Sesion(db.Model):
    __tablename__ = 'sesion'
    __mapper_args__ = {'eager_defaults': True}
    id_sesion: Mapped[int] = _pk()
    id_empleado: Mapped[int] = mapped_column(ForeignKey('empleado.id_empleado'))
    token_hash: Mapped[str] = mapped_column(String(64))
    dispositivo: Mapped[str | None] = mapped_column(String(100))
    fecha_inicio: Mapped[datetime] = _servidor(DateTime(timezone=True))
    fecha_fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activa: Mapped[bool] = _servidor(Boolean)

    empleado: Mapped[Empleado] = relationship()


class Auditoria(db.Model):
    __tablename__ = 'auditoria'
    id_log: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_empleado: Mapped[int | None] = mapped_column(ForeignKey('empleado.id_empleado'))
    accion: Mapped[str] = mapped_column(String(40))
    entidad: Mapped[str] = mapped_column(String(40))
    id_entidad: Mapped[int | None] = mapped_column(Integer)
    detalle: Mapped[dict | None] = mapped_column(JSONB)
    fecha_hora: Mapped[datetime] = _servidor(DateTime(timezone=True))

    empleado: Mapped[Empleado | None] = relationship()


class Cliente(db.Model):
    __tablename__ = 'cliente'
    __mapper_args__ = {'eager_defaults': True}
    id_cliente: Mapped[int] = _pk()
    nombre: Mapped[str] = mapped_column(String(100))
    telefono: Mapped[str] = mapped_column(String(10))
    direccion: Mapped[str] = mapped_column(TextoCifrado)
    colonia: Mapped[str | None] = mapped_column(String(80))
    codigo_postal: Mapped[str | None] = mapped_column(String(5))
    latitud: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitud: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    fecha_registro: Mapped[datetime] = _servidor(DateTime(timezone=True))
    # Cuenta del cliente (decisión 18): sin contraseña si solo lo registró el cajero.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    fecha_alta_cuenta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    intentos_fallidos: Mapped[int] = _servidor(SmallInteger)
    bloqueado: Mapped[bool] = _servidor(Boolean)

    @property
    def tiene_cuenta(self) -> bool:
        return self.password_hash is not None


class Producto(db.Model):
    __tablename__ = 'producto'
    id_producto: Mapped[int] = _pk()
    nombre: Mapped[str] = mapped_column(String(80))
    descripcion: Mapped[str | None] = mapped_column(String(200))
    categoria: Mapped[str] = mapped_column(String(12))
    tamano: Mapped[str | None] = mapped_column(String(10))
    precio: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    codigo_qr_barras: Mapped[str | None] = mapped_column(String(50))
    disponible: Mapped[bool] = _servidor(Boolean)
    activo: Mapped[bool] = _servidor(Boolean)


class CodigoDescuento(db.Model):
    __tablename__ = 'codigo_descuento'
    id_codigo: Mapped[int] = _pk()
    codigo: Mapped[str] = mapped_column(String(20))
    id_gerente: Mapped[int] = mapped_column(ForeignKey('empleado.id_empleado'))
    tipo: Mapped[str] = mapped_column(String(12))
    valor: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    vigencia_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    vigencia_fin: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    usado: Mapped[bool] = _servidor(Boolean)


class Pedido(db.Model):
    __tablename__ = 'pedido'
    __mapper_args__ = {'eager_defaults': True}
    id_pedido: Mapped[int] = _pk()
    folio: Mapped[str] = _servidor(String(20))
    id_sucursal: Mapped[int] = mapped_column(ForeignKey('sucursal.id_sucursal'))
    id_cliente: Mapped[int] = mapped_column(ForeignKey('cliente.id_cliente'))
    id_cajero: Mapped[int | None] = mapped_column(ForeignKey('empleado.id_empleado'))
    id_cocinero: Mapped[int | None] = mapped_column(ForeignKey('empleado.id_empleado'))
    id_codigo_descuento: Mapped[int | None] = mapped_column(ForeignKey('codigo_descuento.id_codigo'))
    origen: Mapped[str] = mapped_column(String(10))
    direccion_entrega: Mapped[str] = mapped_column(TextoCifrado)
    latitud_entrega: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitud_entrega: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    estado: Mapped[str] = _servidor(String(20))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    descuento: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal('0'))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    forma_pago: Mapped[str] = mapped_column(String(15))
    monto_recibido: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    cambio: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    referencia_pago: Mapped[str | None] = mapped_column(TextoCifrado)
    tiempo_estimado_min: Mapped[int | None] = _servidor(SmallInteger)
    codigo_entrega: Mapped[str | None] = _servidor(String(4))
    fecha_registro: Mapped[datetime] = _servidor(DateTime(timezone=True))
    fecha_preparacion: Mapped[datetime | None] = _servidor(DateTime(timezone=True))
    fecha_listo: Mapped[datetime | None] = _servidor(DateTime(timezone=True))
    fecha_en_camino: Mapped[datetime | None] = _servidor(DateTime(timezone=True))
    fecha_entrega: Mapped[datetime | None] = _servidor(DateTime(timezone=True))
    cancelacion_solicitada_por: Mapped[str | None] = _servidor(String(8))
    fecha_solicitud_cancelacion: Mapped[datetime | None] = _servidor(DateTime(timezone=True))
    cancelacion_confirmada_por_telefono: Mapped[bool] = _servidor(Boolean)
    motivo_cancelacion: Mapped[str | None] = _servidor(String(200))
    sincronizado: Mapped[bool] = _servidor(Boolean)

    sucursal: Mapped[Sucursal] = relationship()
    cliente: Mapped[Cliente] = relationship()
    cajero: Mapped[Empleado | None] = relationship(foreign_keys=[id_cajero])
    cocinero: Mapped[Empleado | None] = relationship(foreign_keys=[id_cocinero])
    detalles: Mapped[list['DetallePedido']] = relationship(back_populates='pedido', order_by='DetallePedido.id_detalle')


class DetallePedido(db.Model):
    __tablename__ = 'detalle_pedido'
    id_detalle: Mapped[int] = _pk()
    id_pedido: Mapped[int] = mapped_column(ForeignKey('pedido.id_pedido'))
    id_producto: Mapped[int] = mapped_column(ForeignKey('producto.id_producto'))
    cantidad: Mapped[int] = mapped_column(SmallInteger)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    pedido: Mapped[Pedido] = relationship(back_populates='detalles')
    producto: Mapped[Producto] = relationship()


class AsignacionEntrega(db.Model):
    __tablename__ = 'asignacion_entrega'
    __mapper_args__ = {'eager_defaults': True}
    id_asignacion: Mapped[int] = _pk()
    id_pedido: Mapped[int] = mapped_column(ForeignKey('pedido.id_pedido'))
    id_repartidor: Mapped[int] = mapped_column(ForeignKey('empleado.id_empleado'))
    id_gerente: Mapped[int | None] = mapped_column(ForeignKey('empleado.id_empleado'))
    tipo: Mapped[str] = mapped_column(String(10))
    estado: Mapped[str] = _servidor(String(12))
    fecha_asignacion: Mapped[datetime] = _servidor(DateTime(timezone=True))
    fecha_confirmacion: Mapped[datetime | None] = _servidor(DateTime(timezone=True))
    fecha_limite_entrega: Mapped[datetime | None] = _servidor(DateTime(timezone=True))
    firma_digital: Mapped[bytes | None] = mapped_column(LargeBinary)
    codigo_confirmacion: Mapped[str | None] = mapped_column(String(10))
    fecha_confirmacion_cliente: Mapped[datetime | None] = _servidor(DateTime(timezone=True))
    fecha_hora_entrega: Mapped[datetime | None] = _servidor(DateTime(timezone=True))

    pedido: Mapped[Pedido] = relationship()
    repartidor: Mapped[Empleado] = relationship(foreign_keys=[id_repartidor])


class Devolucion(db.Model):
    __tablename__ = 'devolucion'
    id_devolucion: Mapped[int] = _pk()
    id_pedido: Mapped[int] = mapped_column(ForeignKey('pedido.id_pedido'))
    id_gerente: Mapped[int] = mapped_column(ForeignKey('empleado.id_empleado'))
    fecha_hora: Mapped[datetime] = _servidor(DateTime(timezone=True))
    motivo: Mapped[str] = mapped_column(String(200))
    accion_correctiva: Mapped[str] = mapped_column(String(200))

    pedido: Mapped[Pedido] = relationship()
    gerente: Mapped[Empleado] = relationship()


class Notificacion(db.Model):
    __tablename__ = 'notificacion'
    id_notificacion: Mapped[int] = _pk()
    id_pedido: Mapped[int | None] = mapped_column(ForeignKey('pedido.id_pedido'))
    id_empleado: Mapped[int | None] = mapped_column(ForeignKey('empleado.id_empleado'))
    id_cliente: Mapped[int | None] = mapped_column(ForeignKey('cliente.id_cliente'))
    rol_destino: Mapped[str | None] = mapped_column(String(12))
    tipo_evento: Mapped[str] = mapped_column(String(30))
    mensaje: Mapped[str] = mapped_column(String(255))
    canal: Mapped[str] = _servidor(String(15))
    fecha_envio: Mapped[datetime] = _servidor(DateTime(timezone=True))
    leida: Mapped[bool] = _servidor(Boolean)
