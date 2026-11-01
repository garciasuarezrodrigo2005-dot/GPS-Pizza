"""Arranque de GPizza con waitress, servidor de producción que funciona en Windows y Linux (RNF-008).

Uso:  python run.py            -> http://localhost:8000
      python run.py 0.0.0.0    -> accesible desde otros equipos de la red (p. ej. el celular)
Para desarrollo con recarga automática, usa:  flask --app gpizza run --debug
"""
import sys

from waitress import serve

from gpizza import create_app

if __name__ == '__main__':
    host = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
    print(f'GPizza escuchando en http://{host}:8000  (Ctrl+C para detener)')
    serve(create_app(), host=host, port=8000, threads=8)
