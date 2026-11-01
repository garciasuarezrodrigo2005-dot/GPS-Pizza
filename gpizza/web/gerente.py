"""Panel administrativo del gerente (boceto 10). Siempre limitado a su sucursal (decisión 11)."""
from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from gpizza.seguridad.acceso import rol_requerido
from gpizza.servicios import asignacion, ciclo

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


@bp.post('/pedidos/<int:id_pedido>/cancelar')
@rol_requerido('Gerente')
def cancelar(id_pedido):
    problema = ciclo.cancelar_gerente(id_pedido, g.usuario.id_sucursal, request.form.get('motivo', ''))
    flash(problema or 'Pedido cancelado por el gerente (RN-005).', 'error' if problema else 'exito')
    return redirect(url_for('gerente.pedidos', estado=request.args.get('estado', 'Cancelado')))
