"""CU-007 Notificar Estado: la campana del personal y su lista de avisos.

La campana se vuelve a pedir cada 10 s desde cualquier pantalla del personal. Esa misma petición
dispara la revisión periódica (alertas de 45 y 90 min, asignaciones vencidas, reasignación), así no
hace falta un proceso aparte corriendo en el servidor.
"""
from flask import Blueprint, g, render_template

from gpizza.seguridad.acceso import rol_requerido
from gpizza.servicios import ciclo, notificaciones

bp = Blueprint('notificaciones', __name__, url_prefix='/notificaciones')


@bp.get('/campana')
@rol_requerido('Cajero', 'Repartidor', 'Gerente')
def campana():
    ciclo.revisar_tiempos()
    return render_template('parciales/_campana.html', no_leidas=notificaciones.no_leidas(g.usuario))


@bp.get('/')
@rol_requerido('Cajero', 'Repartidor', 'Gerente')
def lista():
    avisos = notificaciones.recientes(g.usuario)
    ids_nuevos = {a.id_notificacion for a in avisos if not a.leida}
    notificaciones.marcar_leidas(g.usuario)
    return render_template('notificaciones.html', avisos=avisos, ids_nuevos=ids_nuevos)
