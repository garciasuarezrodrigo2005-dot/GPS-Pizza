"""Registros (logs), medición de tiempos y cabeceras de seguridad.

- RNF-001: cada petición se mide; el tiempo va en la cabecera Server-Timing (visible en las
  DevTools del navegador) y en logs/rendimiento.log.
- RNF-002: los errores se escriben en logs/app.log para revisarlos sin tumbar la app.
- RNF-003: cabeceras HTTP que endurecen el navegador.
"""
import logging
import time
from logging.handlers import RotatingFileHandler

from flask import Flask, g, request

log_rendimiento = logging.getLogger('gpizza.rendimiento')


def _archivo_log(ruta, nivel):
    manejador = RotatingFileHandler(ruta, maxBytes=1_000_000, backupCount=3, encoding='utf-8')
    manejador.setLevel(nivel)
    manejador.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    return manejador


def configurar_logs(app: Flask) -> None:
    carpeta = app.config['CARPETA_LOGS']
    carpeta.mkdir(exist_ok=True)
    # app.logger es el mismo objeto en cada create_app(); se agrega el archivo una sola vez.
    if not any(isinstance(h, RotatingFileHandler) for h in app.logger.handlers):
        app.logger.addHandler(_archivo_log(carpeta / 'app.log', logging.WARNING))
    if not log_rendimiento.handlers:
        log_rendimiento.addHandler(_archivo_log(carpeta / 'rendimiento.log', logging.INFO))
        log_rendimiento.setLevel(logging.INFO)


def registrar_medicion(app: Flask) -> None:
    @app.before_request
    def _iniciar_cronometro():
        g.inicio_peticion = time.perf_counter()

    @app.after_request
    def _medir_y_proteger(respuesta):
        inicio = g.pop('inicio_peticion', None)
        if inicio is not None:
            ms = (time.perf_counter() - inicio) * 1000
            respuesta.headers['Server-Timing'] = f'app;dur={ms:.1f}'
            if request.endpoint != 'static':
                log_rendimiento.info('%s %s -> %s en %.1f ms',
                                     request.method, request.path, respuesta.status_code, ms)
        respuesta.headers.setdefault('X-Content-Type-Options', 'nosniff')
        respuesta.headers.setdefault('X-Frame-Options', 'DENY')
        respuesta.headers.setdefault('Referrer-Policy', 'same-origin')
        return respuesta
