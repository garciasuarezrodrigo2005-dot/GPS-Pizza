"""Traduce los errores de PostgreSQL a mensajes en español para la pantalla (RNF-004).

Los triggers ya devuelven su mensaje en español empezando por la regla ("RN-005: ..."); las
restricciones CHECK/UNIQUE devuelven su nombre (rn001_pedido_minimo, ...), que aquí se traduce.
Nunca se muestra al usuario el texto técnico de la base de datos.
"""
from sqlalchemy.exc import DBAPIError

MENSAJES_RESTRICCIONES = {
    'rn001_pedido_minimo': 'El pedido mínimo es de $100 en productos (RN-001).',
    'rn003_unidades': 'Puedes pedir de 1 a 5 unidades de cada producto (RN-003).',
    'rn003_producto_unico': 'Un producto aparece una sola vez en el pedido; ajusta su cantidad (RN-003).',
    'rn004_cliente_telefono': 'El teléfono debe tener 10 dígitos.',
    'cliente_telefono_key': 'Ya existe un cliente registrado con ese teléfono.',
    'rn008_descuento_rango': 'El descuento no puede ser mayor que el subtotal (RN-008).',
    'rn009_forma_pago': 'Elige una forma de pago: efectivo, tarjeta o transferencia (RN-009).',
    'rn010_cambio': 'El monto con que se paga debe cubrir el total del pedido (RN-010).',
    'ck_pedido_motivo': 'Escribe el motivo.',
}
GENERICO = 'No se pudo guardar. Revisa los datos e inténtalo de nuevo.'


def mensaje_bd(error: DBAPIError) -> str:
    diagnostico = getattr(error.orig, 'diag', None)
    if diagnostico is None:
        return GENERICO
    restriccion = diagnostico.constraint_name
    if restriccion in MENSAJES_RESTRICCIONES:
        return MENSAJES_RESTRICCIONES[restriccion]
    principal = diagnostico.message_primary or ''
    # Los mensajes propios de los triggers (fn_error) ya están en español y listos para mostrarse.
    if diagnostico.sqlstate == '23514' and restriccion is None:
        return principal
    return GENERICO
