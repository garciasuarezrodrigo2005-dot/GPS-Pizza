"""Fase 1: la base de datos hace cumplir las reglas de negocio por sí sola.

Cada prueba escribe SQL directo, saltándose el código Python a propósito: así se demuestra que
aunque alguien use la base sin pasar por la app, las reglas (RN-001 a RN-019) se respetan.
Los errores de la BD empiezan con el código de la regla o la restricción lleva su nombre (rn001_...).
"""
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from gpizza.seguridad.cifrado import cifrar

pytestmark = pytest.mark.usefixtures('motor_demo')

ZONA = ZoneInfo('America/Mexico_City')
EN_HORARIO = datetime.now(ZONA).replace(hour=15, minute=0, second=0, microsecond=0)


def producto(bd, nombre='Pepperoni', tamano='Mediana'):
    return bd.sql('SELECT id_producto, precio FROM producto WHERE nombre = :n AND tamano IS NOT DISTINCT FROM :t',
                  n=nombre, t=tamano).one()


def insertar_pedido(bd, *, renglones=None, origen='APP', forma_pago='Tarjeta', descuento=0, codigo=None,
                    monto_recibido=None, cambio=None, subtotal=None, cajero=None, cocinero=None, tiempo=None,
                    sucursal='Coyol (matriz)', telefono='2295865835'):
    """INSERT directo de un pedido y su detalle (como lo haría alguien sin usar la app)."""
    renglones = renglones or [(producto(bd).id_producto, 1)]
    precios = {r.id_producto: r.precio for r in bd.sql('SELECT id_producto, precio FROM producto')}
    if subtotal is None:
        subtotal = sum(precios[p] * q for p, q in renglones)
    descuento = Decimal(str(descuento))  # dinero siempre en Decimal, nunca float
    total = subtotal - descuento
    if forma_pago == 'Efectivo' and monto_recibido is None:
        monto_recibido, cambio = 500, 500 - total
    id_pedido = bd.valor(
        'INSERT INTO pedido (id_sucursal, id_cliente, id_cajero, id_cocinero, id_codigo_descuento, origen, '
        'direccion_entrega, subtotal, descuento, total, forma_pago, monto_recibido, cambio, tiempo_estimado_min) '
        'VALUES ((SELECT id_sucursal FROM sucursal WHERE nombre = :s), '
        '(SELECT id_cliente FROM cliente WHERE telefono = :tel), :caj, :coc, '
        '(SELECT id_codigo FROM codigo_descuento WHERE codigo = :cod), :o, :dir, :sub, :desc, :tot, :pago, '
        ':rec, :cam, :tiempo) RETURNING id_pedido',
        s=sucursal, tel=telefono, caj=cajero, coc=cocinero, cod=codigo, o=origen, dir=cifrar('Calle 1'),
        sub=subtotal, desc=descuento, tot=total, pago=forma_pago, rec=monto_recibido, cam=cambio, tiempo=tiempo)
    for p, q in renglones:
        bd.sql('INSERT INTO detalle_pedido (id_pedido, id_producto, cantidad, precio_unitario, subtotal) '
               'VALUES (:id, :p, :q, :pr, :sub)', id=id_pedido, p=p, q=q, pr=precios[p], sub=precios[p] * q)
    bd.sql('SET CONSTRAINTS ALL IMMEDIATE')  # revisa ya los triggers diferidos (RN-003)
    bd.sql('SET CONSTRAINTS ALL DEFERRED')
    return id_pedido


def falla_pedido(bd, patron, **kwargs):
    """El pedido completo (encabezado + detalle) debe ser rechazado."""
    from sqlalchemy.exc import DBAPIError
    punto = bd.c.begin_nested()
    with pytest.raises(DBAPIError, match=patron):
        insertar_pedido(bd, **kwargs)
    punto.rollback()


# ======================================================================= pedidos (RN-001 a RN-004)

def test_pedido_valido_se_registra_por_confirmar(bd):
    bd.como('Cliente', ahora=EN_HORARIO)
    id_pedido = insertar_pedido(bd)
    fila = bd.sql('SELECT estado, folio, id_cajero FROM pedido WHERE id_pedido = :p', p=id_pedido).one()
    assert fila.estado == 'Por Confirmar' and fila.folio.startswith('YP-') and fila.id_cajero is None
    # CU-007: el cajero recibe el aviso del pedido nuevo.
    assert bd.valor("SELECT count(*) FROM notificacion WHERE id_pedido = :p AND rol_destino = 'Cajero'", p=id_pedido) == 1


def test_rn001_subtotal_menor_a_100_es_rechazado(bd):
    bd.como('Cliente', ahora=EN_HORARIO)
    falla_pedido(bd, 'rn001_pedido_minimo', renglones=[(producto(bd, 'Pepperoni', 'Personal').id_producto, 1)])


def test_rn002_fuera_de_horario_es_rechazado(bd):
    bd.como('Cliente', ahora=EN_HORARIO.replace(hour=8))
    falla_pedido(bd, 'RN-002')
    bd.como('Cliente', ahora=EN_HORARIO.replace(hour=22, minute=5))
    falla_pedido(bd, 'RN-002')


def test_rn003_mas_de_5_unidades_es_rechazado(bd):
    bd.como('Cliente', ahora=EN_HORARIO)
    falla_pedido(bd, 'rn003_unidades', renglones=[(producto(bd).id_producto, 6)])


def test_rn003_mas_de_10_productos_distintos_es_rechazado(bd):
    bd.como('Cliente', ahora=EN_HORARIO)
    once = [r.id_producto for r in bd.sql('SELECT id_producto FROM producto WHERE disponible ORDER BY 1 LIMIT 11')]
    falla_pedido(bd, 'RN-003', renglones=[(p, 1) for p in once])
    insertar_pedido(bd, renglones=[(p, 1) for p in once[:10]])  # 10 sí se permiten


def test_rn004_telefono_no_numerico_y_datos_vacios_son_rechazados(bd):
    bd.debe_fallar('rn004_cliente_telefono',
                   "INSERT INTO cliente (nombre, telefono, direccion) VALUES ('Ana', '229-ABC', :d)", d=cifrar('x'))
    bd.debe_fallar('cliente_nombre_check',
                   "INSERT INTO cliente (nombre, telefono, direccion) VALUES ('  ', '2290000000', :d)", d=cifrar('x'))
    bd.debe_fallar('direccion', "INSERT INTO cliente (nombre, telefono, direccion) VALUES ('Ana', '2290000000', NULL)")


def test_producto_agotado_no_se_puede_pedir(bd):
    bd.como('Cliente', ahora=EN_HORARIO)
    agotado = producto(bd, 'Yungla Especial', 'Familiar').id_producto
    falla_pedido(bd, 'no está disponible', renglones=[(agotado, 1)])


# ======================================================================= precios y pagos (RN-007 a RN-010)

def test_rn007_cajero_no_cambia_precios_y_gerente_si(bd):
    pizza = producto(bd).id_producto
    bd.como('Cajero', 'cajero1.coyol')
    bd.debe_fallar('RN-007', 'UPDATE producto SET precio = 1 WHERE id_producto = :p', p=pizza)
    bd.como('Gerente', 'gerente.coyol')
    bd.sql('UPDATE producto SET precio = 155 WHERE id_producto = :p', p=pizza)
    assert bd.valor('SELECT precio FROM producto WHERE id_producto = :p', p=pizza) == 155


def test_rn007_precio_alterado_en_el_pedido_es_rechazado(bd):
    bd.como('Cliente', ahora=EN_HORARIO)
    pizza = producto(bd)
    id_pedido = bd.valor(
        "INSERT INTO pedido (id_sucursal, id_cliente, origen, direccion_entrega, subtotal, total, forma_pago) "
        "VALUES (1, 1, 'APP', :d, 100, 100, 'Tarjeta') RETURNING id_pedido", d=cifrar('x'))
    bd.debe_fallar('RN-007', 'INSERT INTO detalle_pedido (id_pedido, id_producto, cantidad, precio_unitario, subtotal) '
                             'VALUES (:p, :prod, 1, 100, 100)', p=id_pedido, prod=pizza.id_producto)


def test_rn008_no_hay_descuentos_sin_codigo(bd):
    bd.como('Cliente', ahora=EN_HORARIO)
    falla_pedido(bd, 'RN-008', descuento=20)


def test_rn008_codigo_vencido_usado_o_mal_calculado_es_rechazado(bd):
    bd.como('Cliente', ahora=EN_HORARIO)
    renglones = [(producto(bd, 'Pepperoni', 'Familiar').id_producto, 1)]  # $259
    falla_pedido(bd, 'no está vigente', renglones=renglones, codigo='VENCIDO20', descuento=51.80)
    falla_pedido(bd, 'ya fue usado', renglones=renglones, codigo='USADO15', descuento=38.85)
    falla_pedido(bd, 'RN-008: el descuento debe ser 25.90', renglones=renglones, codigo='BIENVENIDA10', descuento=40)
    id_pedido = insertar_pedido(bd, renglones=renglones, codigo='BIENVENIDA10', descuento=25.90)
    assert bd.valor("SELECT usado FROM codigo_descuento WHERE codigo = 'BIENVENIDA10'") is True
    assert bd.valor('SELECT total FROM pedido WHERE id_pedido = :p', p=id_pedido) == Decimal('233.10')


def test_rn008_solo_el_gerente_emite_codigos(bd):
    bd.como('Cajero', 'cajero1.coyol')
    bd.debe_fallar('RN-008', "INSERT INTO codigo_descuento (codigo, id_gerente, tipo, valor, vigencia_inicio, vigencia_fin) "
                             "VALUES ('CAJERO99', :g, 'PORCENTAJE', 99, now(), now() + interval '1 day')",
                   g=bd.empleado('cajero1.coyol'))


def test_rn009_un_solo_metodo_de_pago_valido(bd):
    bd.como('Cliente', ahora=EN_HORARIO)
    falla_pedido(bd, 'rn009_forma_pago', forma_pago='Mixto', monto_recibido=None, cambio=None)


def test_rn010_cambio_mal_calculado_es_rechazado(bd):
    bd.como('Cliente', ahora=EN_HORARIO)  # Pepperoni mediana: $149, paga con $200 -> cambio $51
    falla_pedido(bd, 'rn010_cambio', forma_pago='Efectivo', monto_recibido=200, cambio=60)
    falla_pedido(bd, 'rn010_cambio', forma_pago='Efectivo', monto_recibido=100, cambio=0)  # no alcanza
    insertar_pedido(bd, forma_pago='Efectivo', monto_recibido=200, cambio=51)


def test_montos_de_un_pedido_registrado_no_cambian(bd):
    p = bd.pedido('En Preparación')
    bd.como('Gerente', 'gerente.coyol')
    bd.debe_fallar('no se modifican', 'UPDATE pedido SET total = 1 WHERE id_pedido = :p', p=p['id_pedido'])
    bd.debe_fallar('no se borran', 'DELETE FROM pedido WHERE id_pedido = :p', p=p['id_pedido'])


# ======================================================================= ciclo del pedido (RN-005, RN-006)

def test_estados_no_se_saltan(bd):
    p = bd.pedido('Por Confirmar')
    bd.como('Gerente', 'gerente.coyol')
    bd.debe_fallar('no permitido', "UPDATE pedido SET estado = 'Entregado' WHERE id_pedido = :p", p=p['id_pedido'])


def test_confirmar_exige_cajero_y_cocinero_de_la_sucursal(bd):
    p = bd.pedido('Por Confirmar')
    otra = bd.valor("SELECT id_empleado FROM empleado WHERE puesto = 'Cocinero' AND id_sucursal <> :s LIMIT 1",
                    s=p['id_sucursal'])
    bd.como('Cajero', 'cajero1.coyol')
    bd.debe_fallar('otra sucursal', "UPDATE pedido SET estado = 'En Preparación', id_cajero = :c, id_cocinero = :k, "
                                    'tiempo_estimado_min = 45 WHERE id_pedido = :p',
                   c=bd.empleado('cajero1.coyol'), k=otra, p=p['id_pedido'])


def test_rn005_cajero_solo_no_cancela_un_pedido_en_preparacion(bd):
    p = bd.pedido('En Preparación', extra="AND origen = 'APP' AND cancelacion_solicitada_por IS NULL")
    bd.como('Cajero', 'cajero1.coyol')
    bd.debe_fallar('RN-005', "UPDATE pedido SET estado = 'Cancelado', motivo_cancelacion = 'x' WHERE id_pedido = :p",
                   p=p['id_pedido'])
    # Ni siquiera marcando "confirmó por teléfono": el pedido se hizo en la app.
    bd.debe_fallar('RN-005', "UPDATE pedido SET estado = 'Cancelado', motivo_cancelacion = 'x', "
                             'cancelacion_confirmada_por_telefono = true WHERE id_pedido = :p', p=p['id_pedido'])


def test_rn005_acuerdo_mutuo_cancela(bd):
    p = bd.pedido('En Preparación', extra="AND cancelacion_solicitada_por = 'CLIENTE'")  # pendiente en la demo
    bd.como('Cajero', 'cajero1.coyol')
    bd.sql("UPDATE pedido SET estado = 'Cancelado' WHERE id_pedido = :p", p=p['id_pedido'])
    assert bd.valor('SELECT estado FROM pedido WHERE id_pedido = :p', p=p['id_pedido']) == 'Cancelado'


def test_rn005_pedido_telefonico_se_cancela_con_confirmacion_registrada(bd):
    p = bd.pedido('En Preparación', extra="AND origen = 'TELEFONO'")
    bd.como('Cajero', 'cajero1.coyol')
    bd.sql("UPDATE pedido SET estado = 'Cancelado', motivo_cancelacion = 'Lo pidió por teléfono', "
           'cancelacion_confirmada_por_telefono = true WHERE id_pedido = :p', p=p['id_pedido'])
    assert bd.valor("SELECT accion FROM auditoria WHERE entidad = 'pedido' AND id_entidad = :p "
                    'ORDER BY id_log DESC LIMIT 1', p=p['id_pedido']) == 'CANCELAR'


def test_rn005_en_camino_solo_cancela_el_gerente(bd):
    p = bd.pedido('En Camino')
    bd.como('Cajero', 'cajero1.coyol')
    bd.debe_fallar('RN-005', "UPDATE pedido SET estado = 'Cancelado', motivo_cancelacion = 'x' WHERE id_pedido = :p",
                   p=p['id_pedido'])
    bd.como('Gerente', 'gerente.coyol')
    bd.sql("UPDATE pedido SET estado = 'Cancelado', motivo_cancelacion = 'x' WHERE id_pedido = :p", p=p['id_pedido'])
    assert bd.valor("SELECT estado FROM asignacion_entrega WHERE id_pedido = :p", p=p['id_pedido']) == 'CANCELADA'


def test_rn006_alerta_a_los_45_minutos_sin_duplicarse(bd):
    p = bd.pedido('En Preparación')
    bd.como(ahora=p['fecha_preparacion'] + timedelta(minutes=47))
    bd.sql('SELECT fn_generar_alertas()')
    consulta = "SELECT count(*) FROM notificacion WHERE id_pedido = :p AND tipo_evento = 'ALERTA_45'"
    assert bd.valor(consulta, p=p['id_pedido']) == 1
    bd.sql('SELECT fn_generar_alertas()')
    assert bd.valor(consulta, p=p['id_pedido']) == 1


def test_rn014_alerta_a_los_90_minutos_al_gerente_y_al_cajero(bd):
    p = bd.pedido('En Camino')
    bd.como(ahora=p['fecha_en_camino'] + timedelta(minutes=91))
    bd.sql('SELECT fn_generar_alertas()')
    roles = {r for r, in bd.sql("SELECT rol_destino FROM notificacion WHERE id_pedido = :p AND tipo_evento = 'ALERTA_90'",
                                p=p['id_pedido'])}
    assert roles == {'Gerente', 'Cajero'}


# ======================================================================= repartidores y entregas (RN-011, RN-013)

def test_rn011_un_repartidor_no_tiene_mas_de_2_pedidos_activos(bd):
    r1 = bd.empleado('repartidor1.coyol')  # en la demo ya lleva 1 pedido en camino
    listo = bd.pedido('Listo para Entrega')
    bd.sql("INSERT INTO asignacion_entrega (id_pedido, id_repartidor, tipo) VALUES (:p, :r, 'AUTOMATICA')",
           p=listo['id_pedido'], r=r1)
    otro = bd.pedido('En Preparación', extra='AND cancelacion_solicitada_por IS NULL')
    bd.como('Cajero', 'cajero1.coyol')
    bd.sql("UPDATE pedido SET estado = 'Listo para Entrega' WHERE id_pedido = :p", p=otro['id_pedido'])
    bd.debe_fallar('RN-011', "INSERT INTO asignacion_entrega (id_pedido, id_repartidor, tipo) VALUES (:p, :r, 'AUTOMATICA')",
                   p=otro['id_pedido'], r=r1)


def _en_camino(bd):
    p = bd.pedido('En Camino')
    a = bd.sql("SELECT id_asignacion, id_repartidor FROM asignacion_entrega WHERE id_pedido = :p AND estado = 'CONFIRMADA'",
               p=p['id_pedido']).one()
    bd.como('Repartidor', a.id_repartidor)
    return p, a


def test_rn013_sin_confirmacion_del_cliente_no_hay_entrega(bd):
    p, a = _en_camino(bd)
    bd.debe_fallar('rn013_entrega', "UPDATE asignacion_entrega SET estado = 'ENTREGADA' WHERE id_asignacion = :a",
                   a=a.id_asignacion)
    bd.debe_fallar('RN-013', "UPDATE pedido SET estado = 'Entregado' WHERE id_pedido = :p", p=p['id_pedido'])


def test_rn013_codigo_del_cliente_incorrecto_es_rechazado(bd):
    p, a = _en_camino(bd)
    incorrecto = '0000' if p['codigo_entrega'] != '0000' else '1111'
    bd.debe_fallar('RN-013: el código', 'UPDATE asignacion_entrega SET codigo_confirmacion = :c WHERE id_asignacion = :a',
                   c=incorrecto, a=a.id_asignacion)


def test_rn013_entrega_en_dos_pasos(bd):
    p, a = _en_camino(bd)
    bd.sql('UPDATE asignacion_entrega SET codigo_confirmacion = :c WHERE id_asignacion = :a',
           c=p['codigo_entrega'], a=a.id_asignacion)                   # paso 1: el cliente
    bd.sql("UPDATE asignacion_entrega SET estado = 'ENTREGADA' WHERE id_asignacion = :a", a=a.id_asignacion)  # paso 2
    fila = bd.sql('SELECT estado, fecha_entrega FROM pedido WHERE id_pedido = :p', p=p['id_pedido']).one()
    assert fila.estado == 'Entregado' and fila.fecha_entrega is not None


def test_solo_el_repartidor_asignado_acepta(bd):
    listo = bd.pedido('Listo para Entrega')
    r2 = bd.empleado('repartidor2.coyol')
    id_asig = bd.valor("INSERT INTO asignacion_entrega (id_pedido, id_repartidor, tipo) VALUES (:p, :r, 'AUTOMATICA') "
                       'RETURNING id_asignacion', p=listo['id_pedido'], r=r2)
    bd.como('Repartidor', 'repartidor1.coyol')
    bd.debe_fallar('solo el repartidor asignado',
                   "UPDATE asignacion_entrega SET estado = 'CONFIRMADA' WHERE id_asignacion = :a", a=id_asig)


# ======================================================================= devoluciones (RN-015)

def _entregado_sin_devolucion(bd):
    return bd.pedido('Entregado', extra='AND NOT EXISTS (SELECT 1 FROM devolucion d WHERE d.id_pedido = p.id_pedido)')


def test_rn015_solo_el_gerente_registra_devoluciones(bd):
    p = _entregado_sin_devolucion(bd)
    bd.como('Cajero', 'cajero1.coyol', ahora=p['fecha_entrega'] + timedelta(minutes=30))
    bd.debe_fallar('RN-015', "INSERT INTO devolucion (id_pedido, id_gerente, motivo, accion_correctiva) "
                             "VALUES (:p, :g, 'Fría', 'Reposición')", p=p['id_pedido'], g=bd.empleado('gerente.coyol'))


def test_rn015_devolucion_dentro_y_fuera_de_las_2_horas(bd):
    p = _entregado_sin_devolucion(bd)
    insertar = ("INSERT INTO devolucion (id_pedido, id_gerente, motivo, accion_correctiva) "
                "VALUES (:p, :g, 'Llegó fría', 'Reposición sin costo')")
    gerente = bd.empleado('gerente.coyol')
    bd.como('Gerente', gerente, ahora=p['fecha_entrega'] + timedelta(hours=2, minutes=1))
    bd.debe_fallar('RN-015: el plazo', insertar, p=p['id_pedido'], g=gerente)
    bd.como('Gerente', gerente, ahora=p['fecha_entrega'] + timedelta(minutes=90))
    bd.sql(insertar, p=p['id_pedido'], g=gerente)


# ======================================================================= usuarios (RN-016 a RN-018)

def test_rn016_un_rol_por_usuario_y_el_cocinero_no_inicia_sesion(bd):
    bd.debe_fallar('rn016_empleado_acceso',
                   "INSERT INTO empleado (id_sucursal, nombre, apellidos, telefono, puesto, username, password_hash, "
                   "fecha_cambio_password) VALUES (1, 'Ana', 'Pérez', '2290000000', 'Cocinero', 'ana.cocina', 'x', current_date)")
    bd.debe_fallar('rn016_empleado_acceso',
                   "INSERT INTO empleado (id_sucursal, nombre, apellidos, telefono, puesto) "
                   "VALUES (1, 'Ana', 'Pérez', '2290000000', 'Cajero')")
    bd.debe_fallar('puesto', "INSERT INTO empleado (id_sucursal, nombre, apellidos, telefono, puesto) "
                             "VALUES (1, 'Ana', 'Pérez', '2290000000', 'Cajero y Gerente')")
    cocinero = bd.valor("SELECT id_empleado FROM empleado WHERE puesto = 'Cocinero' LIMIT 1")
    bd.debe_fallar('RN-016', "INSERT INTO sesion (id_empleado, token_hash) VALUES (:e, repeat('a', 64))", e=cocinero)


def test_rn017_un_segundo_inicio_de_sesion_cierra_el_primero(bd):
    cajero = bd.empleado('cajero1.coyol')
    primera = bd.valor("INSERT INTO sesion (id_empleado, token_hash) VALUES (:e, repeat('a', 64)) RETURNING id_sesion", e=cajero)
    bd.sql("INSERT INTO sesion (id_empleado, token_hash) VALUES (:e, repeat('b', 64))", e=cajero)
    assert bd.valor('SELECT activa FROM sesion WHERE id_sesion = :s', s=primera) is False
    assert bd.valor('SELECT count(*) FROM sesion WHERE id_empleado = :e AND activa', e=cajero) == 1
    assert bd.valor("SELECT count(*) FROM auditoria WHERE accion = 'LOGIN' AND id_empleado = :e", e=cajero) == 2


def test_rn018_tres_intentos_bloquean_la_cuenta(bd):
    cajero = bd.empleado('cajero1.coyol')
    for _ in range(3):
        bd.sql('UPDATE empleado SET intentos_fallidos = intentos_fallidos + 1 WHERE id_empleado = :e', e=cajero)
    assert bd.valor('SELECT bloqueado FROM empleado WHERE id_empleado = :e', e=cajero) is True
    bd.debe_fallar('rn018_intentos', 'UPDATE empleado SET intentos_fallidos = 4 WHERE id_empleado = :e', e=cajero)
    bd.debe_fallar('RN-018', "INSERT INTO sesion (id_empleado, token_hash) VALUES (:e, repeat('c', 64))", e=cajero)
    assert bd.valor("SELECT count(*) FROM auditoria WHERE accion = 'BLOQUEO' AND id_entidad = :e", e=cajero) == 1


# ======================================================================= auditoría (RN-019)

def test_rn019_cada_accion_queda_registrada_con_usuario(bd):
    p = bd.pedido('Por Confirmar')
    cajero = bd.empleado('cajero1.coyol')
    cocinero = bd.valor("SELECT id_empleado FROM empleado WHERE puesto = 'Cocinero' AND id_sucursal = :s LIMIT 1",
                        s=p['id_sucursal'])
    bd.como('Cajero', cajero)
    bd.sql("UPDATE pedido SET estado = 'En Preparación', id_cajero = :c, id_cocinero = :k, tiempo_estimado_min = 60 "
           'WHERE id_pedido = :p', c=cajero, k=cocinero, p=p['id_pedido'])
    registro = bd.sql("SELECT id_empleado, accion, detalle FROM auditoria WHERE entidad = 'pedido' AND id_entidad = :p "
                      'ORDER BY id_log DESC LIMIT 1', p=p['id_pedido']).one()
    assert registro.id_empleado == cajero and registro.accion == 'MODIFICAR'
    assert registro.detalle['estado'] == {'antes': 'Por Confirmar', 'despues': 'En Preparación'}


@pytest.mark.parametrize('consulta', [
    "UPDATE auditoria SET accion = 'NADA'",
    'DELETE FROM auditoria',
    'TRUNCATE auditoria',
])
def test_rn019_la_bitacora_no_se_puede_editar_ni_borrar(bd, consulta):
    bd.debe_fallar(r'(?i)(RN-019|permiso|permission)', consulta)


def test_rn019_la_bitacora_no_guarda_datos_sensibles(bd):
    detalles = ' '.join(d for d, in bd.sql("SELECT detalle::text FROM auditoria WHERE entidad IN ('empleado', 'cliente')"))
    assert 'argon2' not in detalles and 'password_hash' not in detalles and '"direccion"' not in detalles


# ======================================================================= RNF-003: cifrado

def test_rnf003_la_direccion_se_guarda_cifrada(bd):
    from gpizza.seguridad.cifrado import descifrar
    guardado = bytes(bd.valor("SELECT direccion FROM cliente WHERE telefono = '2295865835'"))
    assert b'Pino' not in guardado and guardado.startswith(b'gAAAA')
    assert descifrar(guardado).startswith('Calle Pino Suárez 120')
