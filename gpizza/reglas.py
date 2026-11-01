"""Constantes de las reglas de negocio (ERS, sección 3.4).

Viven en un solo lugar para que el código, las plantillas y las pruebas usen los mismos
valores. La base de datos repite estas reglas con CHECK y triggers (db/*.sql).
"""
from datetime import time

PEDIDO_MINIMO = 100                 # RN-001: subtotal mínimo en MXN, antes del descuento
HORA_APERTURA = time(11, 0)         # RN-002: valor por defecto; cada sucursal guarda el suyo
HORA_CIERRE = time(22, 0)
MAX_PRODUCTOS_DISTINTOS = 10        # RN-003
MAX_UNIDADES_POR_PRODUCTO = 5       # RN-003
ALERTA_PREPARACION_MIN = 45         # RN-006
FORMAS_PAGO = ('Efectivo', 'Tarjeta', 'Transferencia')  # RN-009
MAX_PEDIDOS_ACTIVOS_REPARTIDOR = 2  # RN-011
ALERTA_ENTREGA_MIN = 90             # RN-014
PLAZO_DEVOLUCION_HORAS = 2          # RN-015
ROLES = ('Cajero', 'Repartidor', 'Gerente')  # RN-016 (el cocinero no inicia sesión)
CONTRASENA_MIN_CARACTERES = 8       # RN-018
CONTRASENA_VIGENCIA_DIAS = 90       # RN-018
MAX_INTENTOS_LOGIN = 3              # RN-018
TIEMPOS_ESTIMADOS_MIN = (45, 60, 90)  # Boceto: 45 min / 1 h / 1 h 30
PLAZO_ACEPTAR_ASIGNACION_MIN = 5    # CU-002 FA-2
