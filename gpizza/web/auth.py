"""Inicio de sesión del personal (boceto, página 6), cierre de sesión y cambio de contraseña."""
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from gpizza.extensiones import db
from gpizza.modelos import Empleado
from gpizza.seguridad.acceso import INICIO_POR_ROL, destino_seguro
from gpizza.servicios import autenticacion

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if g.usuario is not None:
        return redirect(url_for(INICIO_POR_ROL[g.usuario.rol]))
    usuario = ''
    if request.method == 'POST':
        usuario = request.form.get('usuario', '')
        resultado = autenticacion.iniciar_sesion(usuario, request.form.get('contrasena', ''),
                                                 request.user_agent.string or '')
        if resultado.ok:
            session.clear()  # cookie nueva en cada inicio de sesión
            session['token'] = resultado.token
            if autenticacion.contrasena_vencida(resultado.empleado):
                flash('Tu contraseña cumplió 90 días y debe cambiarse antes de continuar (RN-018).', 'aviso')
                return redirect(url_for('auth.cambiar_contrasena'))
            return redirect(destino_seguro(request.args.get('siguiente'))
                            or url_for(INICIO_POR_ROL[resultado.empleado.puesto]))
        flash(resultado.mensaje, 'error')
    return render_template('auth/login.html', usuario=usuario)


@bp.post('/salir')
def salir():
    token = session.pop('token', None)
    if token:
        autenticacion.cerrar_sesion(token)
    session.clear()
    flash('Cerraste sesión.', 'exito')
    return redirect(url_for('auth.login'))


@bp.route('/cambiar-contrasena', methods=['GET', 'POST'])
def cambiar_contrasena():
    if g.usuario is None:
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        empleado = db.session.get(Empleado, g.usuario.id_empleado)
        problema = autenticacion.cambiar_contrasena(
            empleado, request.form.get('actual', ''), request.form.get('nueva', ''),
            request.form.get('confirmacion', ''))
        if problema is None:
            flash('Contraseña actualizada.', 'exito')
            return redirect(url_for(INICIO_POR_ROL[g.usuario.rol]))
        flash(problema, 'error')
    return render_template('auth/cambiar_contrasena.html', obligatorio=g.usuario.debe_cambiar_contrasena)
