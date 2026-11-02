"""Datos de demostración: sucursales de la zona Veracruz, menú, personal, clientes y pedidos.

Los pedidos NO se insertan directamente en su estado final: cada uno recorre su ciclo de vida
real (alta -> confirmación -> listo -> asignación -> aceptación -> confirmación del cliente ->
entrega) pasando por todos los triggers de db/02_funciones.sql, con la hora simulada de cada
paso (gpizza.ahora). Si una regla de la base de datos estuviera mal, la carga fallaría.

Todos los nombres, teléfonos y direcciones son ficticios.
"""
import base64
import random
from datetime import datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from flask import Flask
from sqlalchemy import Connection, Engine, text

from gpizza import reloj
from gpizza.bd import fijar_contexto
from gpizza.seguridad.cifrado import cifrar
from gpizza.seguridad.contrasenas import generar_hash

CONTRASENA_DEMO = 'Pizza2026'
DIAS_DE_HISTORIA = 14
# PNG de 1x1 px que hace de firma en los pedidos históricos.
FIRMA_DEMO = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=')

# (clave, nombre, dirección, ciudad, radio km, latitud, longitud, pedidos por día (min, max))
SUCURSALES = [
    ('coyol', 'Coyol (matriz)', 'Eje 1 Poniente #80, Col. Las Palmas', 'Veracruz', 5.0, 19.1563, -96.1590, (4, 7)),
    ('pmoreno', 'Puente Moreno', 'Av. Puente Moreno 210, Fracc. Puente Moreno', 'Medellín de Bravo', 4.5, 19.0930, -96.1660, (3, 5)),
    ('tejeria', 'Tejería', 'Carretera Veracruz–Xalapa km 7, Tejería', 'Veracruz', 4.0, 19.1840, -96.2420, (1, 3)),
    ('riviera', 'Riviera', 'Blvd. Riviera Veracruzana 1500, Fracc. Riviera Veracruzana', 'Alvarado', 4.0, 19.0690, -96.0890, (1, 3)),
    ('carranza', 'Carranza', 'Av. Venustiano Carranza 455, Col. Centro', 'Veracruz', 3.5, 19.1950, -96.1380, (1, 3)),
]

# (sucursal, puesto, usuario o None, nombre, apellidos)
PERSONAL = [
    ('coyol', 'Gerente', 'gerente.coyol', 'Mariana', 'Hernández Ruiz'),
    ('coyol', 'Cajero', 'cajero1.coyol', 'Luis', 'Pérez Domínguez'),
    ('coyol', 'Cajero', 'cajero2.coyol', 'Fernanda', 'Castro Lagunes'),      # contraseña vencida (RN-018)
    ('coyol', 'Cocinero', None, 'Jorge', 'Ramírez Solís'),
    ('coyol', 'Cocinero', None, 'Patricia', 'Molina Aguirre'),
    ('coyol', 'Repartidor', 'repartidor1.coyol', 'Carlos', 'Gómez Arano'),
    ('coyol', 'Repartidor', 'repartidor2.coyol', 'Daniel', 'Sánchez Mora'),
    ('coyol', 'Repartidor', 'repartidor3.coyol', 'Iván', 'Ortiz Vela'),     # cuenta bloqueada (RN-018)
    ('pmoreno', 'Gerente', 'gerente.pmoreno', 'Rosa', 'Lagunes Prieto'),
    ('pmoreno', 'Cajero', 'cajero1.pmoreno', 'Andrés', 'Vázquez León'),
    ('pmoreno', 'Cocinero', None, 'Miguel', 'Torres Cruz'),
    ('pmoreno', 'Repartidor', 'repartidor1.pmoreno', 'Ricardo', 'Flores Lara'),
    ('pmoreno', 'Repartidor', 'repartidor2.pmoreno', 'Omar', 'Jiménez Paz'),
]
# Decisión 19: el Administrador es de toda la cadena (sin sucursal).
ADMINISTRADOR = ('admin.yungla', 'Alejandra', 'Montes Rivera')
# Decisión 18: este cliente lo registró el cajero por teléfono y todavía no crea su cuenta en la app.
CLIENTE_SIN_CUENTA = '2295678901'
for _clave in ('tejeria', 'riviera', 'carranza'):
    PERSONAL += [
        (_clave, 'Gerente', f'gerente.{_clave}', 'Gerente', _clave.capitalize()),
        (_clave, 'Cajero', f'cajero1.{_clave}', 'Cajero', _clave.capitalize()),
        (_clave, 'Cocinero', None, 'Cocinero', _clave.capitalize()),
        (_clave, 'Repartidor', f'repartidor1.{_clave}', 'Repartidor', _clave.capitalize()),
    ]

PIZZAS = [  # nombre, descripción, precios Personal/Mediana/Grande/Familiar
    ('Pepperoni', 'Salsa de tomate, queso mozzarella y pepperoni', (89, 149, 199, 259)),
    ('Hawaiana', 'Jamón, piña y queso mozzarella', (99, 169, 219, 279)),
    ('Mexicana', 'Chorizo, jalapeño, cebolla y frijol', (105, 179, 229, 289)),
    ('Carnes frías', 'Pepperoni, jamón, salami y tocino', (105, 179, 229, 289)),
    ('Vegetariana', 'Pimiento, champiñón, cebolla, aceituna y elote', (95, 159, 209, 269)),
    ('Yungla Especial', 'La de la casa: carne molida, chorizo, tocino y chile güero', (115, 195, 249, 309)),
]
TAMANOS = ('Personal', 'Mediana', 'Grande', 'Familiar')
COMPLEMENTOS = [
    ('Papas gajo', 'Con sazonador de la casa', 65),
    ('Alitas BBQ (8 pzas)', 'Bañadas en salsa BBQ', 129),
    ('Pan de ajo', 'Con queso gratinado', 49),
    ('Refresco 2 L', 'Sabor a elegir', 45),
    ('Brownie', 'De chocolate con nuez', 39),
    ('Ensalada César', 'Lechuga, crutones y aderezo César', 79),
]
AGOTADOS = {('Yungla Especial', 'Familiar'), ('Ensalada César', None)}  # para la demo de CU-001 FA-2

# teléfono, nombre, calle, colonia, C.P., latitud, longitud
CLIENTES = [
    ('2295865835', 'Ana López Martínez', 'Calle Pino Suárez 120', 'Las Palmas', '91750', 19.1571, -96.1605),
    ('2291234567', 'Roberto Méndez Cruz', 'Av. Díaz Mirón 2045', 'Centro', '91700', 19.1880, -96.1370),
    ('2297654321', 'Sofía Ramírez Díaz', 'Calle Laurel 33', 'Floresta', '91940', 19.1660, -96.1290),
    ('2299871234', 'Héctor Aguilar Ríos', 'Calle Mangos 18', 'Puente Moreno', '94274', 19.0950, -96.1650),
    ('2293456789', 'Lucía Fernández Gil', 'Av. Ruiz Cortines 3500', 'Costa de Oro', '94299', 19.1450, -96.1050),
    ('2294567890', 'Jorge Castillo Ponce', 'Calle Colibrí 9', 'Reserva Tarimoya', '91855', 19.1700, -96.1780),
    ('2296789012', 'Paola Herrera Luna', 'Privada Arrecife 4', 'Riviera Veracruzana', '95264', 19.0700, -96.0900),
    ('2298901234', 'Miguel Ángel Soto', 'Calle Tejería Norte 51', 'Tejería', '91725', 19.1830, -96.2400),
    ('2292345678', 'Valeria Ortega Vidal', 'Calle Independencia 812', 'Centro', '91700', 19.1960, -96.1360),
    ('2295678901', 'Diego Navarro Báez', 'Calle Gaviota 27', 'Fracc. Virginia', '94294', 19.1400, -96.1150),
]

MOTIVOS_RECHAZO = ['La dirección queda fuera de nuestra zona de reparto.', 'Nos quedamos sin ingredientes para la pizza solicitada.']
MOTIVOS_CANCELACION = ['El cliente ya no estará en casa.', 'El cliente pidió por error.', 'El cliente cambió de opinión.']
MOTIVOS_DEVOLUCION = [('La pizza llegó fría.', 'Se repuso el pedido sin costo y se revisó el empaque térmico.'),
                      ('Llegó una pizza equivocada.', 'Se entregó la pizza correcta y se reforzó la verificación en caja.')]


def _dinero(valor) -> Decimal:
    return Decimal(valor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class Cargador:
    """Ejecuta cada paso con el rol, el empleado y la hora que le corresponden."""

    def __init__(self, conexion: Connection, base: datetime):
        self.c = conexion
        self.base = base
        self.azar = random.Random(2026)  # semilla fija: los mismos datos en cada carga
        self.suc, self.emp, self.prod, self.cli, self.codigos = {}, {}, {}, {}, {}

    def sql(self, consulta: str, **parametros):
        return self.c.execute(text(consulta), parametros)

    def como(self, rol: str | None, t: datetime, id_empleado: int | None = None):
        fijar_contexto(self.c, rol=rol, id_empleado=id_empleado, ahora=t)

    def personal(self, clave: str, puesto: str, *, todos=False) -> list[int]:
        return [e['id'] for e in self.emp.values()
                if e['suc'] == clave and e['puesto'] == puesto and (todos or e['usable'])]

    # ------------------------------------------------------------------ catálogos
    def catalogos(self):
        t = self.base - timedelta(days=DIAS_DE_HISTORIA + 30)
        self.como(None, t)
        for clave, nombre, direccion, ciudad, radio, lat, lon, _ in SUCURSALES:
            self.suc[clave] = {'id': self.sql(
                'INSERT INTO sucursal (nombre, direccion, ciudad, estado, radio_cobertura_km) '
                "VALUES (:n, :d, :c, 'Veracruz', :r) RETURNING id_sucursal",
                n=nombre, d=direccion, c=ciudad, r=radio).scalar_one(), 'lat': lat, 'lon': lon}

        hoy = self.base.date()
        for clave, puesto, usuario, nombre, apellidos in PERSONAL:
            bloqueado = usuario == 'repartidor3.coyol'
            cambio = hoy - timedelta(days=95) if usuario == 'cajero2.coyol' else hoy - timedelta(days=10)
            s = self.suc[clave]
            id_emp = self.sql(
                'INSERT INTO empleado (id_sucursal, nombre, apellidos, telefono, puesto, username, password_hash, '
                'fecha_cambio_password, intentos_fallidos, bloqueado, disponible, latitud_actual, longitud_actual, '
                'fecha_alta) VALUES (:s, :n, :a, :tel, :p, :u, :h, :fc, :i, :b, :disp, :lat, :lon, :alta) '
                'RETURNING id_empleado',
                s=s['id'], n=nombre, a=apellidos, tel=f'229{self.azar.randint(1000000, 9999999)}', p=puesto,
                u=usuario, h=generar_hash(CONTRASENA_DEMO) if usuario else None, fc=cambio if usuario else None,
                i=3 if bloqueado else 0, b=bloqueado, disp=(puesto == 'Repartidor') or None,
                lat=s['lat'] + self.azar.uniform(-0.01, 0.01) if puesto == 'Repartidor' else None,
                lon=s['lon'] + self.azar.uniform(-0.01, 0.01) if puesto == 'Repartidor' else None,
                alta=hoy - timedelta(days=120)).scalar_one()
            self.emp[usuario or f'{nombre}.{apellidos}'] = {
                'id': id_emp, 'suc': clave, 'puesto': puesto, 'usable': not bloqueado}

        usuario, nombre, apellidos = ADMINISTRADOR
        self.emp[usuario] = {'id': self.sql(
            "INSERT INTO empleado (id_sucursal, nombre, apellidos, telefono, puesto, username, password_hash, "
            "fecha_cambio_password, fecha_alta) VALUES (NULL, :n, :a, '2290000001', 'Administrador', :u, :h, :fc, :alta) "
            'RETURNING id_empleado', n=nombre, a=apellidos, u=usuario, h=generar_hash(CONTRASENA_DEMO),
            fc=hoy - timedelta(days=10), alta=hoy - timedelta(days=200)).scalar_one(),
            'suc': None, 'puesto': 'Administrador', 'usable': True}

        # RN-007: el catálogo lo da de alta el gerente.
        gerente = self.emp['gerente.coyol']['id']
        self.como('Gerente', t, gerente)
        numero = 0
        filas = [(n, d, 'Pizza', tam, p) for n, d, precios in PIZZAS for tam, p in zip(TAMANOS, precios)]
        filas += [(n, d, 'Complemento', None, p) for n, d, p in COMPLEMENTOS]
        for nombre, descripcion, categoria, tamano, precio in filas:
            numero += 1
            id_prod = self.sql(
                'INSERT INTO producto (nombre, descripcion, categoria, tamano, precio, codigo_qr_barras, disponible) '
                'VALUES (:n, :d, :c, :t, :p, :qr, :disp) RETURNING id_producto',
                n=nombre, d=descripcion, c=categoria, t=tamano, p=precio, qr=f'YP{numero:06d}',
                disp=(nombre, tamano) not in AGOTADOS).scalar_one()
            self.prod[id_prod] = {'precio': _dinero(precio), 'disponible': (nombre, tamano) not in AGOTADOS}

        self.como(None, t)
        hash_clientes = generar_hash(CONTRASENA_DEMO)
        for tel, nombre, calle, colonia, cp, lat, lon in CLIENTES:
            direccion = f'{calle}, Col. {colonia}, C.P. {cp}'
            con_cuenta = tel != CLIENTE_SIN_CUENTA
            self.cli[tel] = {'id': self.sql(
                'INSERT INTO cliente (nombre, telefono, direccion, colonia, codigo_postal, latitud, longitud, '
                'password_hash, fecha_alta_cuenta) VALUES (:n, :tel, :d, :col, :cp, :lat, :lon, :h, :alta) '
                'RETURNING id_cliente',
                n=nombre, tel=tel, d=cifrar(calle), col=colonia, cp=cp, lat=lat, lon=lon,
                h=hash_clientes if con_cuenta else None, alta=t if con_cuenta else None).scalar_one(),
                'direccion': direccion, 'lat': lat, 'lon': lon}

        # RN-008: códigos emitidos por el gerente.
        self.como('Gerente', t, gerente)
        inicio = self.base - timedelta(days=DIAS_DE_HISTORIA + 1)
        for codigo, tipo, valor, desde, hasta in [
                ('BIENVENIDA10', 'PORCENTAJE', 10, inicio, self.base + timedelta(days=30)),
                ('PROMO50', 'MONTO', 50, inicio, self.base + timedelta(days=30)),
                ('USADO15', 'PORCENTAJE', 15, inicio, self.base + timedelta(days=30)),
                ('MARTES10', 'PORCENTAJE', 10, inicio, self.base + timedelta(days=30)),  # se usan en los
                ('COMBO50', 'MONTO', 50, inicio, self.base + timedelta(days=30)),        # pedidos de hoy
                ('VENCIDO20', 'PORCENTAJE', 20, inicio, self.base - timedelta(days=1))]:
            self.codigos[codigo] = {'id': self.sql(
                'INSERT INTO codigo_descuento (codigo, id_gerente, tipo, valor, vigencia_inicio, vigencia_fin) '
                'VALUES (:c, :g, :t, :v, :i, :f) RETURNING id_codigo',
                c=codigo, g=gerente, t=tipo, v=valor, i=desde, f=hasta).scalar_one(), 'tipo': tipo, 'valor': Decimal(valor)}
        self.c.commit()

    # ------------------------------------------------------------------ ciclo de vida de un pedido
    def productos_al_azar(self) -> list[tuple[int, int]]:
        disponibles = [p for p, d in self.prod.items() if d['disponible']]
        while True:
            elegidos = self.azar.sample(disponibles, self.azar.randint(1, 3))
            renglones = [(p, self.azar.choice((1, 1, 1, 2))) for p in elegidos]
            if sum(self.prod[p]['precio'] * q for p, q in renglones) >= 100:  # RN-001
                return renglones

    def alta(self, *, suc: str, tel: str, t: datetime, origen='APP', renglones=None, pago=None,
             codigo=None, tiempo=None) -> dict:
        """CU-001: registra el pedido. Por APP queda "Por Confirmar"; por teléfono, "En Preparación"."""
        renglones = renglones or self.productos_al_azar()
        pago = pago or self.azar.choice(('Efectivo', 'Efectivo', 'Tarjeta', 'Transferencia'))
        cliente = self.cli[tel]
        subtotal = sum(self.prod[p]['precio'] * q for p, q in renglones)
        descuento = Decimal('0.00')
        if codigo:
            c = self.codigos[codigo]
            descuento = _dinero(subtotal * c['valor'] / 100) if c['tipo'] == 'PORCENTAJE' else min(c['valor'], subtotal)
        total = subtotal - descuento
        recibido = cambio = referencia = None
        if pago == 'Efectivo':  # RN-010
            recibido = Decimal((int(total) // 100 + 1) * 100 + self.azar.choice((0, 0, 100, 400)))
            cambio = recibido - total
        else:
            referencia = cifrar(f'Tarjeta ****{self.azar.randint(1000, 9999)}' if pago == 'Tarjeta'
                                else f'SPEI {self.azar.randint(10**7, 10**8 - 1)}')
        cajero = cocinero = None
        if origen == 'APP':
            self.como('Cliente', t)
        else:
            cajero = self.azar.choice(self.personal(suc, 'Cajero'))
            cocinero = self.azar.choice(self.personal(suc, 'Cocinero'))
            tiempo = tiempo or self.azar.choice((45, 60))
            self.como('Cajero', t, cajero)
        id_pedido, folio = self.sql(
            'INSERT INTO pedido (id_sucursal, id_cliente, id_cajero, id_cocinero, id_codigo_descuento, origen, '
            'direccion_entrega, latitud_entrega, longitud_entrega, subtotal, descuento, total, forma_pago, '
            'monto_recibido, cambio, referencia_pago, tiempo_estimado_min) VALUES (:s, :cl, :caj, :coc, :cod, :o, '
            ':dir, :lat, :lon, :sub, :desc, :tot, :pago, :rec, :cam, :ref, :tiempo) RETURNING id_pedido, folio',
            s=self.suc[suc]['id'], cl=cliente['id'], caj=cajero, coc=cocinero,
            cod=self.codigos[codigo]['id'] if codigo else None, o=origen, dir=cifrar(cliente['direccion']),
            lat=cliente['lat'], lon=cliente['lon'], sub=subtotal, desc=descuento, tot=total, pago=pago,
            rec=recibido, cam=cambio, ref=referencia, tiempo=tiempo).one()
        for producto, cantidad in renglones:
            precio = self.prod[producto]['precio']
            self.sql('INSERT INTO detalle_pedido (id_pedido, id_producto, cantidad, precio_unitario, subtotal) '
                     'VALUES (:p, :prod, :q, :pr, :sub)', p=id_pedido, prod=producto, q=cantidad, pr=precio,
                     sub=precio * cantidad)
        return {'id': id_pedido, 'folio': folio, 'suc': suc, 'cajero': cajero}

    def confirmar(self, p: dict, t: datetime, tiempo=None):
        p['cajero'] = self.azar.choice(self.personal(p['suc'], 'Cajero'))
        self.como('Cajero', t, p['cajero'])
        self.sql("UPDATE pedido SET estado = 'En Preparación', id_cajero = :caj, id_cocinero = :coc, "
                 'tiempo_estimado_min = :t WHERE id_pedido = :p',
                 caj=p['cajero'], coc=self.azar.choice(self.personal(p['suc'], 'Cocinero')),
                 t=tiempo or self.azar.choice((45, 60, 90)), p=p['id'])

    def rechazar(self, p: dict, t: datetime):
        cajero = self.azar.choice(self.personal(p['suc'], 'Cajero'))
        self.como('Cajero', t, cajero)
        self.sql("UPDATE pedido SET estado = 'Rechazado', id_cajero = :caj, motivo_cancelacion = :m WHERE id_pedido = :p",
                 caj=cajero, m=self.azar.choice(MOTIVOS_RECHAZO), p=p['id'])

    def listo(self, p: dict, t: datetime):
        self.como('Cajero', t, p['cajero'])
        self.sql("UPDATE pedido SET estado = 'Listo para Entrega' WHERE id_pedido = :p", p=p['id'])

    def asignar_y_aceptar(self, p: dict, t: datetime, repartidor: int | None = None) -> dict:
        """CU-002: asignación automática y aceptación del repartidor (el pedido pasa a "En Camino")."""
        repartidor = repartidor or self.azar.choice(self.personal(p['suc'], 'Repartidor'))
        self.como(None, t)
        p['asignacion'] = self.sql(
            "INSERT INTO asignacion_entrega (id_pedido, id_repartidor, tipo) VALUES (:p, :r, 'AUTOMATICA') "
            'RETURNING id_asignacion', p=p['id'], r=repartidor).scalar_one()
        p['repartidor'] = repartidor
        self.como('Repartidor', t + timedelta(minutes=self.azar.randint(1, 3)), repartidor)
        self.sql("UPDATE asignacion_entrega SET estado = 'CONFIRMADA' WHERE id_asignacion = :a", a=p['asignacion'])
        return p

    def entregar(self, p: dict, t: datetime):
        """RN-013: paso 1 (firma o código del cliente) y paso 2 (confirma el repartidor)."""
        self.como('Repartidor', t, p['repartidor'])
        if self.azar.random() < 0.5:
            self.sql('UPDATE asignacion_entrega SET firma_digital = :f WHERE id_asignacion = :a',
                     f=FIRMA_DEMO, a=p['asignacion'])
        else:
            self.sql('UPDATE asignacion_entrega SET codigo_confirmacion = '
                     '(SELECT codigo_entrega FROM pedido WHERE id_pedido = :p) WHERE id_asignacion = :a',
                     p=p['id'], a=p['asignacion'])
        self.como('Repartidor', t + timedelta(minutes=1), p['repartidor'])
        self.sql("UPDATE asignacion_entrega SET estado = 'ENTREGADA' WHERE id_asignacion = :a", a=p['asignacion'])

    def cancelar_mutuo(self, p: dict, t: datetime):
        """RN-005: el cliente lo pide y el cajero lo acepta."""
        self.como('Cliente', t)
        self.sql("UPDATE pedido SET cancelacion_solicitada_por = 'CLIENTE', motivo_cancelacion = :m WHERE id_pedido = :p",
                 m=self.azar.choice(MOTIVOS_CANCELACION), p=p['id'])
        self.como('Cajero', t + timedelta(minutes=2), p['cajero'])
        self.sql("UPDATE pedido SET estado = 'Cancelado' WHERE id_pedido = :p", p=p['id'])

    def cancelar_gerente(self, p: dict, t: datetime):
        self.como('Gerente', t, self.personal(p['suc'], 'Gerente')[0])
        self.sql("UPDATE pedido SET estado = 'Cancelado', motivo_cancelacion = :m WHERE id_pedido = :p",
                 m='El cliente no respondió en el domicilio.', p=p['id'])

    def devolucion(self, p: dict, t: datetime):
        motivo, accion = self.azar.choice(MOTIVOS_DEVOLUCION)
        gerente = self.personal(p['suc'], 'Gerente')[0]
        self.como('Gerente', t, gerente)
        self.sql('INSERT INTO devolucion (id_pedido, id_gerente, motivo, accion_correctiva) VALUES (:p, :g, :m, :a)',
                 p=p['id'], g=gerente, m=motivo, a=accion)

    def minutos(self, a: int, b: int) -> timedelta:
        return timedelta(minutes=self.azar.randint(a, b))

    # ------------------------------------------------------------------ historia (reportes)
    def historia(self) -> int:
        agenda = []
        for clave, *_, (minimo, maximo) in SUCURSALES:
            for dias in range(DIAS_DE_HISTORIA, 0, -1):
                dia = (self.base - timedelta(days=dias)).date()
                for _ in range(self.azar.randint(minimo, maximo)):
                    hora = time(self.azar.randint(11, 19), self.azar.randint(0, 59))
                    agenda.append((datetime.combine(dia, hora, self.base.tzinfo), clave))
        agenda.sort()
        codigo_usado = False
        for t, clave in agenda:
            origen = self.azar.choice(('APP', 'APP', 'APP', 'TELEFONO', 'SUCURSAL'))
            codigo = None
            if not codigo_usado and clave == 'coyol':
                codigo, codigo_usado = 'USADO15', True
            p = self.alta(suc=clave, tel=self.azar.choice(list(self.cli)), t=t, origen=origen, codigo=codigo)
            suerte = self.azar.random()
            if origen == 'APP':
                t += self.minutos(1, 4)
                if suerte < 0.03:
                    self.rechazar(p, t)
                    self.c.commit()
                    continue
                self.confirmar(p, t)
            if 0.03 <= suerte < 0.06:
                self.cancelar_mutuo(p, t + self.minutos(3, 10))
                self.c.commit()
                continue
            t += self.minutos(46, 58) if self.azar.random() < 0.08 else self.minutos(15, 35)  # algunos tardan (RN-006)
            self.listo(p, t)
            t += self.minutos(2, 8)
            self.asignar_y_aceptar(p, t)
            t += self.minutos(4, 6)
            if 0.06 <= suerte < 0.08:
                self.cancelar_gerente(p, t + self.minutos(20, 40))
                self.c.commit()
                continue
            t += self.minutos(92, 100) if self.azar.random() < 0.05 else self.minutos(12, 40)  # algunos tardan (RN-014)
            self.entregar(p, t)
            if self.azar.random() < 0.04:
                self.devolucion(p, t + self.minutos(20, 100))
            self.c.commit()
        return len(agenda)

    # ------------------------------------------------------------------ escenario de hoy (demo en vivo)
    def hoy(self):
        """Pedidos de hoy en Coyol en todos los estados, como en los bocetos."""
        b = self.base
        r1, r2 = self.personal('coyol', 'Repartidor')[:2]
        tel_boceto = '2295865835'
        ana = list(self.cli)

        def ciclo(minutos_atras, *, hasta, tel, origen='APP', **extra):
            t = b - timedelta(minutes=minutos_atras)
            p = self.alta(suc='coyol', tel=tel, t=t, origen=origen, **extra)
            if hasta == 'Por Confirmar':
                return p, t
            if origen == 'APP':
                t += timedelta(minutes=2)
                self.confirmar(p, t, tiempo=extra.get('tiempo'))
            return p, t

        # Por confirmar (boceto, pág. 7): hace 1 y 4 minutos.
        ciclo(1, hasta='Por Confirmar', tel=tel_boceto, pago='Efectivo')
        ciclo(4, hasta='Por Confirmar', tel=ana[1], pago='Tarjeta')
        self.c.commit()
        # En preparación: uno con 47 min (dispara la alerta de 45 min, RN-006) y dos recientes.
        ciclo(49, hasta='En Preparación', tel=ana[2])
        ciclo(14, hasta='En Preparación', tel=ana[3], codigo='COMBO50')
        ciclo(5, hasta='En Preparación', tel=ana[4], origen='TELEFONO')
        self.c.commit()
        # En preparación con solicitud de cancelación del cliente pendiente (RN-005, acuerdo mutuo).
        p, t = ciclo(20, hasta='En Preparación', tel=ana[5])
        self.como('Cliente', b - timedelta(minutes=2))
        self.sql("UPDATE pedido SET cancelacion_solicitada_por = 'CLIENTE', "
                 "motivo_cancelacion = 'Me equivoqué de dirección.' WHERE id_pedido = :p", p=p['id'])
        self.c.commit()
        # Listo para entrega, todavía sin repartidor (para la asignación automática de la Fase 4).
        p, t = ciclo(32, hasta='En Preparación', tel=ana[6])
        self.listo(p, b - timedelta(minutes=3))
        self.c.commit()
        # En camino: 38 min (boceto, pág. 9) y 95 min (dispara la alerta de 90 min, RN-014).
        p, t = ciclo(75, hasta='En Preparación', tel=ana[7])
        self.listo(p, b - timedelta(minutes=42))
        self.asignar_y_aceptar(p, b - timedelta(minutes=40), repartidor=r1)
        self.c.commit()
        p, t = ciclo(140, hasta='En Preparación', tel=ana[8])
        self.listo(p, b - timedelta(minutes=99))
        self.asignar_y_aceptar(p, b - timedelta(minutes=97), repartidor=r2)
        self.c.commit()
        # Entregado hace 10 min (se le puede registrar devolución en la demo, RN-015).
        p, t = ciclo(70, hasta='En Preparación', tel=ana[9], codigo='MARTES10')
        self.listo(p, b - timedelta(minutes=40))
        self.asignar_y_aceptar(p, b - timedelta(minutes=38), repartidor=r2)
        self.entregar(p, b - timedelta(minutes=11))
        self.c.commit()
        # Entregado hace 2 h 30 min, con devolución ya registrada.
        p, t = ciclo(170, hasta='En Preparación', tel=ana[0])
        self.listo(p, b - timedelta(minutes=140))
        self.asignar_y_aceptar(p, b - timedelta(minutes=138), repartidor=r1)
        self.entregar(p, b - timedelta(minutes=110))
        self.devolucion(p, b - timedelta(minutes=80))
        self.c.commit()
        # Rechazado y cancelado de acuerdo mutuo.
        p, t = ciclo(25, hasta='Por Confirmar', tel=ana[2])
        self.rechazar(p, t + timedelta(minutes=3))
        p, t = ciclo(90, hasta='En Preparación', tel=ana[4])
        self.cancelar_mutuo(p, t + timedelta(minutes=6))
        self.c.commit()
        # Alertas de tiempo a la hora actual.
        self.como(None, b)
        self.sql('SELECT fn_generar_alertas()')
        self.c.commit()


def _hora_base(app: Flask) -> tuple[datetime, str | None]:
    """El escenario de hoy necesita ~3 h de historia dentro del horario (11:00–22:00)."""
    with app.app_context():
        ahora = reloj.ahora()
    if time(14, 0) <= ahora.time() < time(22, 0):
        return ahora, None
    base = ahora.replace(hour=14, minute=0, second=0, microsecond=0)
    return base, ('Aviso: la hora actual está fuera del rango de la demo; los pedidos de hoy se cargaron como si '
                  'fueran las 14:00. Pon GPIZZA_HORA_DEMO=14:00 en el .env para que la app use esa misma hora.')


def cargar(motor: Engine, app: Flask) -> list[str]:
    base, aviso = _hora_base(app)
    with motor.connect() as conexion:
        if conexion.execute(text('SELECT count(*) FROM sucursal')).scalar_one():
            raise SystemExit('La base ya tiene datos. Ejecuta primero:  flask --app gpizza db-reset')
        cargador = Cargador(conexion, base)
        cargador.catalogos()
        historicos = cargador.historia()
        cargador.hoy()
        conteos = conexion.execute(text(
            'SELECT (SELECT count(*) FROM pedido), (SELECT count(*) FROM devolucion), '
            '(SELECT count(*) FROM notificacion), (SELECT count(*) FROM auditoria)')).one()
    resumen = [
        f'Sucursales: {len(SUCURSALES)} · Empleados: {len(PERSONAL)} · Productos: {len(cargador.prod)} · '
        f'Clientes: {len(CLIENTES)} · Códigos de descuento: {len(cargador.codigos)}',
        f'Pedidos: {conteos[0]} ({historicos} de los últimos {DIAS_DE_HISTORIA} días) · Devoluciones: {conteos[1]} · '
        f'Notificaciones: {conteos[2]} · Registros de auditoría: {conteos[3]}',
        f'Contraseña de todos los usuarios de demo: {CONTRASENA_DEMO}',
    ]
    if aviso:
        resumen.append(aviso)
    return resumen
