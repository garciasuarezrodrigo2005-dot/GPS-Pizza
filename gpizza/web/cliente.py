"""Interfaz del cliente (bocetos, páginas 1 a 4): entra con su teléfono, arma su pedido y lo sigue.

El cliente no tiene contraseña (decisión 14): su teléfono queda en la cookie firmada de su
navegador y solo puede ver los pedidos de ese teléfono.
"""
from flask import (Blueprint, abort, flash, g, jsonify, redirect, render_template, request, session,
                   url_for)

from gpizza import reglas, reloj
from gpizza.bd import fijar_contexto
from gpizza.extensiones import db
from gpizza.servicios import catalogo, ciclo, clientes, entregas, notificaciones, pedidos

bp = Blueprint('cliente', __name__)


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


def _telefono_o_inicio():
    telefono = session.get('telefono')
    if not telefono:
        flash('Escribe tu número de teléfono para continuar.', 'aviso')
    return telefono


@bp.get('/')
def inicio():
    return render_template('cliente/inicio.html', en_horario=reloj.en_horario(),
                           apertura=reglas.HORA_APERTURA, cierre=reglas.HORA_CIERRE,
                           telefono=session.get('telefono', ''))


@bp.post('/continuar')
def continuar():
    telefono = clientes.normalizar_telefono(request.form.get('telefono'))
    if not clientes.telefono_valido(telefono):
        flash('El teléfono debe tener 10 dígitos, solo números.', 'error')
        return redirect(url_for('cliente.inicio'))
    session['telefono'] = telefono
    return redirect(url_for('cliente.pedido'))


@bp.post('/cambiar-telefono')
def cambiar_telefono():
    session.pop('telefono', None)
    return redirect(url_for('cliente.inicio'))


@bp.route('/pedido', methods=['GET', 'POST'])
def pedido():
    telefono = _telefono_o_inicio()
    if not telefono:
        return redirect(url_for('cliente.inicio'))
    cliente = clientes.por_telefono(telefono)
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
    telefono = session.get('telefono')
    pedido = pedidos.del_cliente(folio, telefono) if telefono else None
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
