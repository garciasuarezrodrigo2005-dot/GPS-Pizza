"""Panel administrativo del gerente (boceto 10). Siempre limitado a su sucursal (decisión 11)."""
from flask import Blueprint, Response, abort, flash, g, redirect, render_template, request, url_for

from gpizza.extensiones import db
from gpizza.modelos import Cliente, Producto
from gpizza.seguridad.acceso import rol_requerido
from gpizza.servicios import administracion, asignacion, ciclo, clientes, personal, qr

bp = Blueprint('gerente', __name__, url_prefix='/gerente')

ESTADOS_GERENTE = [('En Preparación', 'En preparación'), ('Listo para Entrega', 'Listo'), ('En Camino', 'En camino'),
                   ('Entregado', 'Entregado'), ('Cancelado', 'Cancelado')]


@bp.get('/')
@rol_requerido('Gerente')
def inicio():
    return render_template('gerente/inicio.html', conteos=ciclo.conteos(g.usuario.id_sucursal), activa='inicio')


def _datos_lista(estado):
    estado = estado if estado in dict(ESTADOS_GERENTE) else 'Listo para Entrega'
    lista = ciclo.por_estado(g.usuario.id_sucursal, estado)
    return {'estado': estado, 'pedidos': lista, 'vivas': ciclo.asignaciones_vivas(lista), 'modo': 'gerente',
            'candidatos': asignacion.candidatos(g.usuario.id_sucursal),
            'url_lista': url_for('gerente.lista_pedidos', estado=estado)}


@bp.get('/pedidos')
@rol_requerido('Gerente')
def pedidos():
    datos = _datos_lista(request.args.get('estado'))
    return render_template('gerente/pedidos.html', estados=ESTADOS_GERENTE, endpoint='gerente.pedidos',
                           conteos=ciclo.conteos(g.usuario.id_sucursal), activa='pedidos', **datos)


@bp.get('/pedidos/lista')
@rol_requerido('Gerente')
def lista_pedidos():
    return render_template('parciales/_lista_pedidos.html', **_datos_lista(request.args.get('estado')))


@bp.post('/pedidos/<int:id_pedido>/asignar')
@rol_requerido('Gerente')
def asignar(id_pedido):
    """CU-002 FA-3: asignación manual (RN-011 la vuelve a revisar la BD)."""
    problema = asignacion.asignar_manual(id_pedido, g.usuario.id_sucursal, request.form.get('id_repartidor', type=int),
                                         g.usuario.id_empleado)
    flash(problema or 'Repartidor asignado; tiene 5 minutos para aceptar.', 'error' if problema else 'exito')
    return redirect(url_for('gerente.pedidos', estado='Listo para Entrega'))


# ------------------------------------------------------------------------------ catálogo y precios (RN-007)

@bp.get('/catalogo')
@rol_requerido('Gerente')
def catalogo():
    return render_template('gerente/catalogo.html', productos=administracion.productos(), tamanos=administracion.TAMANOS,
                           errores={}, valores={}, activa='catalogo')


@bp.post('/catalogo/<int:id_producto>')
@rol_requerido('Gerente')
def actualizar_producto(id_producto):
    problema = administracion.actualizar_producto(id_producto, request.form.get('precio', ''),
                                                  disponible='disponible' in request.form, activo='activo' in request.form)
    flash(problema or 'Producto actualizado; el menú ya muestra el cambio.', 'error' if problema else 'exito')
    return redirect(url_for('gerente.catalogo') + f'#producto-{id_producto}')


@bp.get('/catalogo/<int:id_producto>/qr.png')
@rol_requerido('Gerente')
def qr_producto(id_producto):
    """RF-009: el QR de un producto (su código YP000001...)."""
    producto = db.session.get(Producto, id_producto) or abort(404)
    return Response(qr.png(producto.codigo_qr_barras), mimetype='image/png')


@bp.get('/catalogo/etiquetas')
@rol_requerido('Gerente')
def etiquetas_qr():
    """RF-009: hoja imprimible con el QR de cada producto disponible, para escanearlos en caja."""
    return render_template('gerente/etiquetas.html', productos=[p for p in administracion.productos() if p.activo])


@bp.post('/catalogo/nuevo')
@rol_requerido('Gerente')
def nuevo_producto():
    valores = request.form.to_dict()
    errores = administracion.crear_producto(valores.get('nombre', ''), valores.get('descripcion', ''),
                                            valores.get('categoria', ''), valores.get('tamano', ''), valores.get('precio', ''))
    if not errores:
        flash(f'Producto "{valores["nombre"].strip()}" agregado al menú.', 'exito')
        return redirect(url_for('gerente.catalogo'))
    return render_template('gerente/catalogo.html', productos=administracion.productos(), tamanos=administracion.TAMANOS,
                           errores=errores, valores=valores, activa='catalogo'), 422


# ------------------------------------------------------------------------------ clientes (RF-005)

@bp.get('/clientes')
@rol_requerido('Gerente')
def lista_clientes():
    texto = request.args.get('q', '')
    return render_template('gerente/clientes.html', clientes=clientes.buscar(texto, limite=100), q=texto, activa='clientes')


@bp.route('/clientes/<int:id_cliente>', methods=['GET', 'POST'])
@rol_requerido('Gerente')
def cliente(id_cliente):
    registro = db.session.get(Cliente, id_cliente) or abort(404)
    errores = {}
    if request.method == 'POST':
        datos = clientes.DatosCliente(nombre=request.form.get('nombre', ''), telefono=registro.telefono,
                                      direccion=request.form.get('direccion', ''), colonia=request.form.get('colonia', ''),
                                      codigo_postal=request.form.get('codigo_postal', ''))
        _, errores = clientes.registrar_o_actualizar(datos)
        if not errores:
            db.session.commit()
            flash('Datos del cliente actualizados.', 'exito')
            return redirect(url_for('gerente.cliente', id_cliente=id_cliente))
    historial = ciclo.del_cliente_en_sucursal(id_cliente, g.usuario.id_sucursal)
    return render_template('gerente/cliente.html', cliente=registro, historial=historial, errores=errores,
                           activa='clientes'), 422 if errores else 200


# ------------------------------------------------------------------------------ personal (CU-009, 009a, 009b)

@bp.get('/personal')
@rol_requerido('Gerente')
def personal_lista():
    puesto = request.args.get('puesto')
    return render_template('gerente/personal.html', empleados=personal.listar(g.usuario.id_sucursal, puesto),
                           puesto=puesto, errores={}, valores={}, activa='personal')


@bp.post('/personal/nuevo')
@rol_requerido('Gerente')
def personal_nuevo():
    valores = request.form.to_dict()
    empleado, temporal, errores = personal.crear(g.usuario.id_sucursal, personal.DatosEmpleado(
        nombre=valores.get('nombre', ''), apellidos=valores.get('apellidos', ''), telefono=valores.get('telefono', ''),
        puesto=valores.get('puesto', ''), username=valores.get('username', '')))
    if errores:
        return render_template('gerente/personal.html', empleados=personal.listar(g.usuario.id_sucursal), puesto=None,
                               errores=errores, valores=valores, activa='personal'), 422
    if temporal:
        flash(f'{empleado.nombre_completo} dado de alta. Usuario: {empleado.username} · contraseña temporal: '
              f'{temporal} (deberá cambiarla al entrar).', 'exito')
    else:
        flash(f'{empleado.nombre_completo} dado de alta como cocinero (no inicia sesión).', 'exito')
    return redirect(url_for('gerente.personal_lista'))


@bp.post('/personal/<int:id_empleado>/<accion>')
@rol_requerido('Gerente')
def personal_accion(id_empleado, accion):
    empleado = personal.del_sucursal(id_empleado, g.usuario.id_sucursal) or abort(404)
    if accion == 'editar':
        errores = personal.editar(empleado, personal.DatosEmpleado(
            nombre=request.form.get('nombre', ''), apellidos=request.form.get('apellidos', ''),
            telefono=request.form.get('telefono', '')))
        problema, exito = (next(iter(errores.values())) if errores else None), 'Datos actualizados.'
    elif accion == 'baja':
        problema, exito = personal.dar_de_baja(empleado), f'{empleado.nombre_completo} dado de baja; ya no puede entrar.'
    elif accion == 'reactivar':
        problema, exito = personal.reactivar(empleado), f'{empleado.nombre_completo} está activo otra vez.'
    elif accion == 'desbloquear':
        problema, exito = personal.desbloquear(empleado), f'Cuenta de {empleado.nombre_completo} desbloqueada (RN-018).'
    elif accion == 'contrasena':
        temporal, problema = personal.reiniciar_contrasena(empleado)
        exito = f'Contraseña temporal de {empleado.username}: {temporal} (deberá cambiarla al entrar).'
    else:
        abort(404)
    flash(problema or exito, 'error' if problema else 'exito')
    return redirect(url_for('gerente.personal_lista') + f'#empleado-{id_empleado}')


# ------------------------------------------------------------------------------ descuentos y devoluciones

def _datos_descuentos(errores=None, valores=None):
    return {'codigos': administracion.codigos(g.usuario.id_sucursal), 'estado_codigo': administracion.estado_codigo,
            'devolvibles': administracion.pedidos_devolvibles(g.usuario.id_sucursal),
            'devoluciones': administracion.devoluciones(g.usuario.id_sucursal),
            'errores': errores or {}, 'valores': valores or {}, 'activa': 'descuentos'}


@bp.get('/descuentos')
@rol_requerido('Gerente')
def descuentos():
    return render_template('gerente/descuentos.html', **_datos_descuentos())


@bp.post('/descuentos/codigos')
@rol_requerido('Gerente')
def emitir_codigo():
    valores = request.form.to_dict()
    codigo, errores = administracion.emitir_codigo(g.usuario.id_empleado, valores.get('tipo', ''), valores.get('valor', ''),
                                                   valores.get('dias', ''), valores.get('codigo', ''))
    if errores:
        return render_template('gerente/descuentos.html', **_datos_descuentos(errores, valores)), 422
    flash(f'Código {codigo} emitido. Sirve para un solo pedido (RN-008).', 'exito')
    return redirect(url_for('gerente.descuentos'))


@bp.post('/devoluciones')
@rol_requerido('Gerente')
def registrar_devolucion():
    problema = administracion.registrar_devolucion(request.form.get('id_pedido', type=int) or 0, g.usuario.id_sucursal,
                                                   g.usuario.id_empleado, request.form.get('motivo', ''),
                                                   request.form.get('accion', ''))
    flash(problema or 'Devolución registrada (RN-015).', 'error' if problema else 'exito')
    return redirect(url_for('gerente.descuentos') + '#devoluciones')


@bp.post('/pedidos/<int:id_pedido>/cancelar')
@rol_requerido('Gerente')
def cancelar(id_pedido):
    problema = ciclo.cancelar_gerente(id_pedido, g.usuario.id_sucursal, request.form.get('motivo', ''))
    flash(problema or 'Pedido cancelado por el gerente (RN-005).', 'error' if problema else 'exito')
    return redirect(url_for('gerente.pedidos', estado=request.args.get('estado', 'Cancelado')))
