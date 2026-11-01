# GPizza

Sistema de Gestión de Pedidos a Domicilio para **Yungla Pizza S.A. de C.V.**
Proyecto escolar del Instituto Tecnológico de Veracruz (Ingeniería en Sistemas Computacionales).

Es una **app móvil progresiva (PWA)**: en el celular se instala en la pantalla de inicio como una app y en la PC
funciona como página web. Tiene tres interfaces: **Cliente**, **Personal** (cajero y repartidor) y **Gerente**.

> Estado: **Fase 0 – Esqueleto** (ver [docs/trazabilidad.md](docs/trazabilidad.md)).

## Tecnologías

Python 3.14 · Flask 3 · Jinja2 + HTMX · Bootstrap 5 · PostgreSQL 18 · SQLAlchemy 2 + psycopg 3 · pytest.
El porqué de cada elección está en [docs/diseno.md](docs/diseno.md).

## Instalación en una computadora nueva (Windows)

Requisitos: Python 3.14, PostgreSQL 18 y Git.

1. **Clonar y crear el entorno virtual**
   ```powershell
   git clone <url-del-repositorio> Aplicacion
   cd Aplicacion
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Base de datos.** Con el usuario `postgres` de PostgreSQL, crea el usuario y las dos bases (la de la app y la de pruebas):
   ```powershell
   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres
   ```
   ```sql
   CREATE USER gpizza_user WITH PASSWORD 'tu_contrasena';
   CREATE DATABASE gpizza OWNER gpizza_user;
   CREATE DATABASE gpizza_test OWNER gpizza_user;
   ```

3. **Configuración.** Copia `.env.example` como `.env` y llena los valores:
   ```powershell
   copy .env.example .env
   python -c "import secrets; print(secrets.token_hex(32))"   # pega el resultado en GPIZZA_SECRET_KEY
   ```
   El archivo `.env` tiene contraseñas y **nunca** se sube a git (está en `.gitignore`).

## Uso

| Para… | Comando | Dirección |
|---|---|---|
| Desarrollar (se recarga al guardar) | `flask --app gpizza run --debug` | http://localhost:5000 |
| Servidor tipo producción (waitress) | `python run.py` | http://localhost:8000 |
| Abrirlo desde el celular en la misma red WiFi | `python run.py 0.0.0.0` | http://IP-de-la-PC:8000 |
| Correr las pruebas | `pytest -v` | — |

## Cómo comprobar la Fase 0

- **Pantalla de inicio del cliente:** abre http://localhost:5000. Muestra el horario de pedidos (RN-002).
  Con `GPIZZA_HORA_DEMO=08:30` en `.env` aparece el aviso "Fuera de horario".
- **Chequeo de salud (RNF-002):** abre http://localhost:5000/salud y verás `{"estado": "ok", "bd": "ok", ...}`.
  Si detienes PostgreSQL (servicio `postgresql-x64-18`), responde `503` con `"bd": "caida"` y la app sigue atendiendo.
- **Tiempo de cada petición (RNF-001):** en las DevTools (F12 → Network → Timing) aparece la cabecera `Server-Timing`.
  Todas las peticiones quedan anotadas en `logs/rendimiento.log`.
- **Errores amables:** http://localhost:5000/no-existe muestra una página 404 en español.
- **PWA (RNF-007):** en Chrome, F12 → Application → Manifest / Service workers.
- **Pruebas:** `pytest -v`.

## Estructura

```
gpizza/            código de la aplicación
  config.py        lee el .env
  reglas.py        constantes de las reglas de negocio (RN)
  reloj.py         hora oficial (zona horaria y hora simulada)
  monitoreo.py     logs, medición de tiempos y cabeceras de seguridad
  web/             rutas: sistema (salud, errores, PWA) y cliente
  templates/       pantallas HTML (Jinja2)
  static/          CSS, JS, iconos y librerías (Bootstrap, HTMX) incluidas para funcionar sin internet
tests/             pruebas automáticas (pytest)
docs/              documentación del proyecto, diseño y matriz de trazabilidad
run.py             arranque con waitress
```
