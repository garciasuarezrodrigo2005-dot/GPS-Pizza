"""Interfaz del cliente (bocetos, páginas 1 a 4): entra a su cuenta, arma su pedido y lo sigue.

Decisión 18: el cliente tiene cuenta con su teléfono (único) y una contraseña. La sesión vive en la
cookie firmada del navegador (id del cliente + huella de su contraseña) y solo ve sus propios pedidos.
"""
from flask import (Blueprint, abort, flash, g, jsonify, redirect, render_template, request, session,
                   url_for)

from gpizza import reglas, reloj
from gpizza.bd import fijar_contexto
from gpizza.extensiones import db
from gpizza.seguridad.acceso import destino_seguro
from gpizza.servicios import catalogo, ciclo, clientes, cuentas_cliente, entregas, notificaciones, pedidos

bp = Blueprint('cliente', __name__)
CLAVES_SESION = ('id_cliente', 'huella_cliente', 'telefono')


@bp.before_request
def _como_cliente():
    # Los triggers deben saber que quien actúa es el cliente (p. ej. solo él registra pedidos "APP").
    # g.rol_bd se aplica solo al abrir la primera transacción (bd._al_iniciar), así las pantallas que
    # no usan la BD, como el inicio, funcionan aunque PostgreSQL esté caído (RNF-002).
    g.rol_bd = 'Cliente'
    if g.usuario is not None:
        # Este navegador también tiene sesión de empleado: cargar_usuario() ya abrió la transacción
        # con su rol de personal, así que se reemplaza ahora.
        fijar_contexto(db.session, rol='Cliente', ahora=reloj.ahora() if reloj.simulada() else None)


def _iniciar_sesion_cliente(cliente):
    session['id_cliente'] = cliente.id_cliente
    session['huella_cliente'] = cuentas_cliente.huella(cliente)
    session['telefono'] = cliente.telefono


def _cerrar_sesion_cliente():
    for clave in CLAVES_SESION:
        session.pop(clave, None)


def _cliente_actual():
    """El cliente con sesión vigente, o None (y se borra una sesión que ya no vale)."""
    cliente = cuentas_cliente.de_la_sesion(session.get('id_cliente'), session.get('huella_cliente'))
    if cliente is None and session.get('id_cliente'):
        _cerrar_sesion_cliente()
        flash('Tu sesión se cerró: tu contraseña cambió o tu cuenta se bloqueó. Vuelve a entrar.', 'aviso')
    return cliente


def _pantalla_inicio(**datos):
    return render_template('cliente/inicio.html', en_horario=reloj.en_horario(), apertura=reglas.HORA_APERTURA,
                           cierre=reglas.HORA_CIERRE, **({'telefono': '', 'mensaje': ''} | datos))


@bp.get('/')
def inicio():
    if session.get('id_cliente'):
        return redirect(url_for('cliente.pedido'))
    return _pantalla_inicio(telefono=request.args.get('telefono', ''))


@bp.post('/entrar')
def entrar():
    telefono = clientes.normalizar_telefono(request.form.get('telefono'))
    if not clientes.telefono_valido(telefono):
        return _pantalla_inicio(telefono=telefono, mensaje='El teléfono debe tener 10 dígitos, solo números.'), 422
    cliente, mensaje = cuentas_cliente.entrar(telefono, request.form.get('contrasena', ''))
    if cliente is None:
        return _pantalla_inicio(telefono=telefono, mensaje=mensaje), 401
    _iniciar_sesion_cliente(cliente)
    return redirect(destino_seguro(request.args.get('siguiente')) or url_for('cliente.pedido'))


@bp.route('/crear-cuenta', methods=['GET', 'POST'])
def crear_cuenta():
    errores, valores = {}, {'telefono': clientes.normalizar_telefono(request.args.get('telefono', ''))}
    if request.method == 'POST':
        valores = request.form.to_dict()
        cliente, errores = cuentas_cliente.crear_cuenta(
            clientes.DatosCliente(nombre=valores.get('nombre', ''), telefono=valores.get('telefono', ''),
                                  direccion=valores.get('direccion', ''), colonia=valores.get('colonia', ''),
                                  codigo_postal=valores.get('codigo_postal', '')),
            valores.get('contrasena', ''), valores.get('confirmacion', ''))
        if cliente is not None:
            _iniciar_sesion_cliente(cliente)
            flash(f'¡Bienvenido, {cliente.nombre.split()[0]}! Tu cuenta quedó creada.', 'exito')
            return redirect(url_for('cliente.pedido'))
        valores.pop('contrasena', None)
        valores.pop('confirmacion', None)
    return render_template('cliente/crear_cuenta.html', errores=errores, valores=valores), 422 if errores else 200


@bp.post('/mi-cuenta/salir')
def salir():
    _cerrar_sesion_cliente()
    flash('Cerraste tu sesión.', 'exito')
    return redirect(url_for('cliente.inicio'))


@bp.route('/mi-cuenta', methods=['GET', 'POST'])
def mi_cuenta():
    cliente = _cliente_actual()
    if cliente is None:
        return redirect(url_for('cliente.inicio'))
    problema = None
    if request.method == 'POST':
        problema = cuentas_cliente.cambiar_contrasena(cliente, request.form.get('actual', ''),
                                                      request.form.get('nueva', ''), request.form.get('confirmacion', ''))
        if problema is None:
            session['huella_cliente'] = cuentas_cliente.huella(cliente)
            flash('Tu contraseña se cambió.', 'exito')
            return redirect(url_for('cliente.pedido'))
    return render_template('cliente/mi_cuenta.html', cliente=cliente, problema=problema), 422 if problema else 200


@bp.route('/pedido', methods=['GET', 'POST'])
def pedido():
    cliente = _cliente_actual()
    if cliente is None:
        flash('Entra a tu cuenta para hacer tu pedido.', 'aviso')
        return redirect(url_for('cliente.inicio'))
    telefono = cliente.telefono
    sucursales = pedidos.sucursales_activas()
    errores, valores = {}, {}

    if request.method == 'POST':
        valores = request.form.to_dict()
        solicitud = pedidos.SolicitudPedido(
            id_sucursal=request.form.get('id_sucursal', type=int) or 0,
            cliente=clientes.DatosCliente(
                nombre=request.form.get('nombre', ''), telefono=telefono,
                direccion=request.form.get('direccion', ''), colonia=request.form.get('colonia', ''),
                codigo_postal=request.form.get('codigo_postal', ''),
                latitud=request.form.get('latitud', ''), longitud=request.form.get('longitud', '')),
            renglones=pedidos.leer_renglones(request.form), forma_pago=request.form.get('forma_pago', ''),
            codigo=request.form.get('codigo', ''), monto_recibido=request.form.get('monto_recibido', ''))
        resultado = pedidos.registrar(solicitud)
        if resultado.pedido:
            flash(f'Pedido {resultado.pedido.folio} enviado. Registrado en {resultado.segundos:.2f} s.', 'exito')
            return redirect(url_for('cliente.estado', folio=resultado.pedido.folio))
        errores = resultado.errores
    elif cliente:
        valores = {'nombre': cliente.nombre, 'direccion': cliente.direccion, 'colonia': cliente.colonia or '',
                   'codigo_postal': cliente.codigo_postal or ''}

    return render_template(
        'cliente/pedido.html', telefono=telefono, cliente=cliente, sucursales=sucursales,
        menu=catalogo.menu(), errores=errores, valores=valores,
        cantidades=pedidos.leer_renglones(valores), en_curso=pedidos.en_curso_del_cliente(telefono),
        sucursal_horario={s.id_sucursal: pedidos.en_horario(s) for s in sucursales}), 422 if errores else 200


@bp.post('/pedido/codigo')
def revisar_codigo():
    """El botón "Aplicar" consulta el código sin enviar el pedido (la validación final es al enviar)."""
    texto = request.form.get('codigo', '')
    try:
        subtotal = pedidos.dinero(request.form.get('subtotal', '0'))
    except Exception:
        subtotal = pedidos.dinero(0)
    codigo, descuento, problema = pedidos.validar_codigo(texto, subtotal)
    if problema:
        return jsonify(ok=False, mensaje=problema)
    return jsonify(ok=True, tipo=codigo.tipo, valor=str(codigo.valor), descuento=str(descuento),
                   mensaje=f'Código {codigo.codigo} aplicado.')


def _pedido_propio(folio):
    cliente = _cliente_actual()
    pedido = pedidos.del_cliente(folio, cliente.telefono) if cliente else None
    if pedido is None:
        abort(404)
    return pedido


@bp.get('/mi-pedido/<folio>')
def estado(folio):
    pedido = _pedido_propio(folio)
    return render_template('cliente/estado.html', pedido=pedido,
                           avisos=notificaciones.del_pedido_para_cliente(pedido))


@bp.get('/mi-pedido/<folio>/estado')
def estado_parcial(folio):
    """Fragmento que la pantalla vuelve a pedir cada 10 s (HTMX): "esta pantalla se actualiza sola"."""
    pedido = _pedido_propio(folio)
    return render_template('cliente/_estado.html', pedido=pedido,
                           avisos=notificaciones.del_pedido_para_cliente(pedido))


@bp.get('/mi-pedido/<folio>/ubicacion')
def ubicacion(folio):
    """Boceto 5: dónde va el repartidor. El mapa la pide cada 10 s mientras el pedido va en camino."""
    return jsonify(entregas.ubicacion_para_cliente(_pedido_propio(folio)))


@bp.post('/mi-pedido/<folio>/cancelacion')
def cancelacion(folio):
    """RN-005 (decisión 7): el cliente pide la cancelación o responde a la que pidió la sucursal."""
    pedido = _pedido_propio(folio)
    accion = request.form.get('accion')
    if accion == 'solicitar':
        problema = ciclo.solicitar_cancelacion(pedido, 'CLIENTE', request.form.get('motivo', ''))
        exito = 'Enviamos tu solicitud de cancelación a la sucursal.'
    else:
        problema = ciclo.responder_cancelacion(pedido, 'CLIENTE', aceptar=accion == 'aceptar')
        exito = 'Tu pedido fue cancelado.' if accion == 'aceptar' else 'Tu pedido continúa.'
    flash(problema or exito, 'error' if problema else 'exito')
    return redirect(url_for('cliente.estado', folio=folio))


@bp.post('/mi-pedido/<folio>/cancelar')
def cancelar(folio):
    problema = pedidos.retirar_por_cliente(_pedido_propio(folio))
    flash(problema or 'Cancelaste tu pedido.', 'error' if problema else 'exito')
    return redirect(url_for('cliente.estado', folio=folio))
