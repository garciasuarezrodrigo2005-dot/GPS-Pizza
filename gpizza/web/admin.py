"""Zona del Administrador (CU-011, decisiones 19 y 20): sucursales, gerentes y auditoría de toda la cadena.

El Administrador no tiene sucursal. Da de alta sucursales y gerentes (cada gerente da de alta a su
propio personal en su panel) y es el único que consulta la bitácora de auditoría (RN-019). El primer
administrador se crea desde la consola: flask crear-admin.
"""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func, select

from gpizza.extensiones import db
from gpizza.modelos import Cliente, Empleado, Sucursal
from gpizza.seguridad.acceso import rol_requerido
from gpizza.servicios import auditoria, personal, sucursales

bp = Blueprint('admin', __name__, url_prefix='/admin')


@bp.before_request
@rol_requerido('Administrador')
def _solo_administrador():
    return None


@bp.get('/')
def inicio():
    contar = lambda consulta: db.session.scalar(select(func.count()).select_from(consulta.subquery()))  # noqa: E731
    resumen = {
        'sucursales': contar(select(Sucursal.id_sucursal).where(Sucursal.activa)),
        'gerentes': contar(select(Empleado.id_empleado).where(Empleado.puesto == 'Gerente', Empleado.activo)),
        'bloqueados': contar(select(Empleado.id_empleado).where(Empleado.bloqueado, Empleado.activo)),
        'clientes_bloqueados': contar(select(Cliente.id_cliente).where(Cliente.bloqueado)),
    }
    sin_gerente = [s for s, _ in sucursales.listar() if s.activa and not personal.gerentes(s.id_sucursal)]
    return render_template('admin/inicio.html', resumen=resumen, sin_gerente=sin_gerente, activa='inicio')


# ------------------------------------------------------------------------------ sucursales

def _datos_sucursal(formulario) -> sucursales.DatosSucursal:
    return sucursales.DatosSucursal(
        nombre=formulario.get('nombre', ''), direccion=formulario.get('direccion', ''),
        ciudad=formulario.get('ciudad', ''), estado=formulario.get('estado', '') or 'Veracruz',
        radio=formulario.get('radio', ''), apertura=formulario.get('apertura', ''), cierre=formulario.get('cierre', ''),
        latitud=formulario.get('latitud', ''), longitud=formulario.get('longitud', ''))


def _pantalla_sucursales(errores=None, valores=None, codigo=200):
    return render_template('admin/sucursales.html', lista=sucursales.listar(), errores=errores or {},
                           valores=valores or {}, activa='sucursales'), codigo


@bp.get('/sucursales')
def sucursales_lista():
    return _pantalla_sucursales()


@bp.post('/sucursales/nueva')
def sucursal_nueva():
    sucursal, errores = sucursales.crear(_datos_sucursal(request.form))
    if errores:
        return _pantalla_sucursales(errores, request.form.to_dict(), 422)
    flash(f'Sucursal "{sucursal.nombre}" creada; ya aparece para los clientes. Ahora dale un gerente.', 'exito')
    return redirect(url_for('admin.gerentes_lista', sucursal=sucursal.id_sucursal) + '#alta')


@bp.post('/sucursales/<int:id_sucursal>/<accion>')
def sucursal_accion(id_sucursal, accion):
    sucursal = db.session.get(Sucursal, id_sucursal) or abort(404)
    if accion == 'editar':
        errores = sucursales.editar(sucursal, _datos_sucursal(request.form))
        problema, exito = (next(iter(errores.values())) if errores else None), f'Sucursal "{sucursal.nombre}" actualizada.'
    elif accion in ('activar', 'desactivar'):
        problema = sucursales.cambiar_activa(sucursal, accion == 'activar')
        exito = (f'"{sucursal.nombre}" vuelve a recibir pedidos.' if accion == 'activar'
                 else f'"{sucursal.nombre}" ya no aparece para los clientes; su historial se conserva.')
    else:
        abort(404)
    if problema:
        db.session.rollback()
    flash(problema or exito, 'error' if problema else 'exito')
    return redirect(url_for('admin.sucursales_lista') + f'#sucursal-{id_sucursal}')


# ------------------------------------------------------------------------------ gerentes

def _pantalla_gerentes(errores=None, valores=None, codigo=200):
    filtro = request.args.get('sucursal', type=int)
    return render_template('admin/gerentes.html', gerentes=personal.gerentes(filtro), filtro=filtro,
                           sucursales=sucursales.activas(), errores=errores or {}, valores=valores or {},
                           activa='gerentes'), codigo


@bp.get('/gerentes')
def gerentes_lista():
    return _pantalla_gerentes()


@bp.post('/gerentes/nuevo')
def gerente_nuevo():
    valores = request.form.to_dict()
    id_sucursal = request.form.get('id_sucursal', type=int)
    if not id_sucursal or db.session.get(Sucursal, id_sucursal) is None:
        return _pantalla_gerentes({'id_sucursal': 'Elige la sucursal del gerente.'}, valores, 422)
    empleado, temporal, errores = personal.crear(id_sucursal, personal.DatosEmpleado(
        nombre=valores.get('nombre', ''), apellidos=valores.get('apellidos', ''), telefono=valores.get('telefono', ''),
        puesto='Gerente', username=valores.get('username', '')), puestos=('Gerente',))
    if errores:
        return _pantalla_gerentes(errores, valores, 422)
    flash(f'{empleado.nombre_completo} es gerente de {empleado.sucursal.nombre}. Usuario: {empleado.username} · '
          f'contraseña temporal: {temporal} (deberá cambiarla al entrar).', 'exito')
    return redirect(url_for('admin.gerentes_lista'))


@bp.post('/gerentes/<int:id_empleado>/<accion>')
def gerente_accion(id_empleado, accion):
    empleado = personal.gerente(id_empleado) or abort(404)
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
    return redirect(url_for('admin.gerentes_lista') + f'#empleado-{id_empleado}')


# ------------------------------------------------------------------------------ auditoría (RN-019, decisión 20)

@bp.get('/auditoria')
def auditoria_vista():
    filtros = auditoria.leer_filtros(request.args)
    registros, total = auditoria.consultar(filtros)
    paginas = max(1, -(-total // auditoria.POR_PAGINA))
    return render_template('admin/auditoria.html', registros=registros, total=total, f=filtros, paginas=paginas,
                           acciones=auditoria.ACCIONES, entidades=auditoria.ENTIDADES, resumen=auditoria.resumen,
                           sucursales=[s for s, _ in sucursales.listar()], activa='auditoria')
