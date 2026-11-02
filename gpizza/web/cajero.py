"""Interfaz del cajero (bocetos 7 y 8): pedidos por confirmar, pedidos por teléfono y clientes."""
from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from gpizza.seguridad.acceso import rol_requerido
from gpizza.servicios import catalogo, ciclo, clientes, pedidos

bp = Blueprint('cajero', __name__, url_prefix='/cajero')

MOTIVOS_RECHAZO = ['La dirección queda fuera de nuestra zona de reparto.',
                   'Nos quedamos sin ingredientes para lo que pediste.',
                   'No pudimos comunicarnos contigo para confirmar el pedido.']


@bp.get('/')
@rol_requerido('Cajero')
def inicio():
    """Boceto 7: pedidos de la app que esperan confirmación (CU-001, pasos 10 y 11)."""
    lista = pedidos.por_confirmar(g.usuario.id_sucursal)
    return render_template('cajero/por_confirmar.html', pedidos=lista, conteo=len(lista),
                           cocineros=pedidos.cocineros(g.usuario.id_sucursal), motivos=MOTIVOS_RECHAZO)


@bp.get('/por-confirmar/aviso')
@rol_requerido('Cajero')
def aviso_nuevos():
    """La pantalla pregunta cada 10 s si llegaron pedidos (CU-007). No recarga la lista sola para
    no borrar lo que el cajero esté eligiendo; muestra un aviso para actualizarla."""
    conteo = pedidos.contar_por_confirmar(g.usuario.id_sucursal)
    return render_template('cajero/_aviso_nuevos.html', conteo=conteo,
                           mostrados=request.args.get('mostrados', type=int, default=0))


@bp.post('/pedidos/<int:id_pedido>/confirmar')
@rol_requerido('Cajero')
def confirmar(id_pedido):
    problema = pedidos.confirmar(id_pedido, g.usuario.id_sucursal, g.usuario.id_empleado,
                                 request.form.get('id_cocinero', type=int), request.form.get('tiempo', type=int))
    flash(problema or 'Pedido confirmado: pasó a cocina y el cliente ya ve su barra de progreso.',
          'error' if problema else 'exito')
    return redirect(url_for('cajero.inicio'))


@bp.post('/pedidos/<int:id_pedido>/rechazar')
@rol_requerido('Cajero')
def rechazar(id_pedido):
    problema = pedidos.rechazar(id_pedido, g.usuario.id_sucursal, g.usuario.id_empleado,
                                request.form.get('motivo', ''))
    flash(problema or 'Pedido rechazado: el cliente verá el motivo.', 'error' if problema else 'exito')
    return redirect(url_for('cajero.inicio'))


ESTADOS_CAJERO = [('En Preparación', 'En preparación'), ('Listo para Entrega', 'Listo'),
                  ('En Camino', 'En camino'), ('Entregado', 'Entregado')]


def _datos_lista(estado):
    estado = estado if estado in dict(ESTADOS_CAJERO) else 'En Preparación'
    lista = ciclo.por_estado(g.usuario.id_sucursal, estado)
    return {'estado': estado, 'pedidos': lista, 'vivas': ciclo.asignaciones_vivas(lista), 'modo': 'cajero',
            'url_lista': url_for('cajero.lista_pedidos', estado=estado)}


@bp.get('/pedidos')
@rol_requerido('Cajero')
def pedidos_por_estado():
    """Boceto 8: pedidos por estado, con alertas de tiempo (RN-006, RN-014)."""
    datos = _datos_lista(request.args.get('estado'))
    return render_template('cajero/pedidos.html', estados=ESTADOS_CAJERO, endpoint='cajero.pedidos_por_estado',
                           conteos=ciclo.conteos(g.usuario.id_sucursal), **datos)


@bp.get('/pedidos/lista')
@rol_requerido('Cajero')
def lista_pedidos():
    return render_template('parciales/_lista_pedidos.html', **_datos_lista(request.args.get('estado')))


@bp.post('/pedidos/<int:id_pedido>/listo')
@rol_requerido('Cajero')
def listo(id_pedido):
    mensaje = ciclo.marcar_listo(id_pedido, g.usuario.id_sucursal)
    flash(mensaje, 'exito' if mensaje.startswith('Pedido') else 'error')
    return redirect(url_for('cajero.pedidos_por_estado', estado='En Preparación'))


@bp.post('/pedidos/<int:id_pedido>/cancelacion')
@rol_requerido('Cajero')
def cancelacion(id_pedido):
    """RN-005: el cajero pide la cancelación (pedido de la app), responde a la del cliente, o cancela
    un pedido telefónico con la confirmación del cliente."""
    accion, motivo = request.form.get('accion'), request.form.get('motivo', '')
    if accion == 'telefono':
        problema = ciclo.cancelar_por_telefono(id_pedido, g.usuario.id_sucursal, motivo)
        exito = 'Pedido cancelado; quedó registrado que el cliente lo confirmó por teléfono.'
    else:
        pedido = pedidos.del_sucursal(id_pedido, g.usuario.id_sucursal)
        if pedido is None:
            problema = 'Ese pedido no existe en tu sucursal.'
        elif accion == 'solicitar':
            problema = ciclo.solicitar_cancelacion(pedido, 'CAJERO', motivo)
        else:
            problema = ciclo.responder_cancelacion(pedido, 'CAJERO', aceptar=accion == 'aceptar')
        exito = {'solicitar': 'Se le pidió al cliente que acepte la cancelación.',
                 'aceptar': 'Pedido cancelado de común acuerdo con el cliente.',
                 'rechazar': 'Rechazaste la solicitud; el pedido continúa.'}.get(accion, 'Listo.')
    flash(problema or exito, 'error' if problema else 'exito')
    return redirect(url_for('cajero.pedidos_por_estado', estado='En Preparación'))


@bp.route('/nuevo', methods=['GET', 'POST'])
@rol_requerido('Cajero')
def nuevo():
    """CU-001 por teléfono o en sucursal: el cajero captura y confirma el pedido en un solo paso."""
    errores, valores = {}, {'origen': 'TELEFONO', 'forma_pago': 'Efectivo'}
    telefono = clientes.normalizar_telefono(request.values.get('telefono', ''))
    cliente = clientes.por_telefono(telefono) if clientes.telefono_valido(telefono) else None

    if request.method == 'POST':
        valores = request.form.to_dict()
        solicitud = pedidos.SolicitudPedido(
            id_sucursal=g.usuario.id_sucursal,
            cliente=clientes.DatosCliente(
                nombre=request.form.get('nombre', ''), telefono=telefono,
                direccion=request.form.get('direccion', ''), colonia=request.form.get('colonia', ''),
                codigo_postal=request.form.get('codigo_postal', '')),
            renglones=pedidos.leer_renglones(request.form), forma_pago=request.form.get('forma_pago', ''),
            codigo=request.form.get('codigo', ''), monto_recibido=request.form.get('monto_recibido', ''),
            referencia_pago=request.form.get('referencia_pago', ''),
            origen='SUCURSAL' if request.form.get('origen') == 'SUCURSAL' else 'TELEFONO',
            id_cocinero=request.form.get('id_cocinero', type=int), tiempo_estimado_min=request.form.get('tiempo', type=int))
        resultado = pedidos.registrar(solicitud, id_cajero=g.usuario.id_empleado)
        if resultado.pedido:
            flash(f'Pedido {resultado.pedido.folio} registrado en {resultado.segundos:.2f} s; ya está en preparación.',
                  'exito')
            return redirect(url_for('cajero.inicio'))
        errores = resultado.errores
    elif cliente:
        valores |= {'nombre': cliente.nombre, 'direccion': cliente.direccion or '', 'colonia': cliente.colonia or '',
                    'codigo_postal': cliente.codigo_postal or ''}
    elif telefono:
        flash('Cliente nuevo: captura sus datos y quedará registrado con el pedido (CU-005).', 'aviso')

    return render_template('cajero/nuevo.html', telefono=telefono, cliente=cliente, valores=valores,
                           errores=errores, menu=catalogo.menu(), cantidades=pedidos.leer_renglones(valores),
                           cocineros=pedidos.cocineros(g.usuario.id_sucursal)), 422 if errores else 200


@bp.get('/clientes')
@rol_requerido('Cajero')
def lista_clientes():
    texto = request.args.get('q', '')
    return render_template('cajero/clientes.html', clientes=clientes.buscar(texto), q=texto)


@bp.route('/clientes/nuevo', methods=['GET', 'POST'])
@rol_requerido('Cajero')
def cliente_nuevo():
    """CU-005 Registrar Perfil de Cliente, fuera de un pedido."""
    from gpizza.extensiones import db
    errores, valores = {}, {}
    if request.method == 'POST':
        valores = request.form.to_dict()
        datos = clientes.DatosCliente(nombre=valores.get('nombre', ''), telefono=valores.get('telefono', ''),
                                      direccion=valores.get('direccion', ''), colonia=valores.get('colonia', ''),
                                      codigo_postal=valores.get('codigo_postal', ''))
        if clientes.por_telefono(datos.telefono):
            errores['telefono'] = 'Ya existe un cliente con ese teléfono.'
        else:
            cliente, errores = clientes.registrar_o_actualizar(datos)
            if cliente:
                db.session.commit()
                flash(f'Cliente {cliente.nombre} registrado.', 'exito')
                return redirect(url_for('cajero.lista_clientes', q=cliente.telefono))
    return render_template('cajero/cliente_nuevo.html', errores=errores, valores=valores), 422 if errores else 200
