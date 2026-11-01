# GPizza

Sistema de Gestión de Pedidos a Domicilio para **Yungla Pizza S.A. de C.V.**
Proyecto escolar del Instituto Tecnológico de Veracruz (Ingeniería en Sistemas Computacionales).

Es una **app móvil progresiva (PWA)**: en el celular se instala en la pantalla de inicio como una app y en la PC
funciona como página web. Tiene tres interfaces: **Cliente**, **Personal** (cajero y repartidor) y **Gerente**.

> Estado: **Fase 3 – Pedidos (cliente y cajero)** (ver [docs/trazabilidad.md](docs/trazabilidad.md)).

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
   Haz lo mismo con `GPIZZA_CLAVE_CIFRADO` (ver el comando en `.env.example`).
   El archivo `.env` tiene contraseñas y **nunca** se sube a git (está en `.gitignore`).

4. **Crear las tablas y cargar los datos de demostración**
   ```powershell
   flask --app gpizza db-reset      # borra y recrea tablas, funciones y triggers (pide confirmación)
   flask --app gpizza db-seed       # sucursales, menú, personal, clientes y 229 pedidos de ejemplo
   ```
   Los pedidos de "hoy" se cargan alrededor de la hora actual. Si la cargas antes de las 14:00 o después de
   las 22:00, se cargan como si fueran las 14:00. En ese caso pon `GPIZZA_HORA_DEMO=14:00` en `.env`
   para que la app use la misma hora.

## Usuarios de demostración

Contraseña de todos: **`Pizza2026`**

| Usuario | Rol | Sucursal | Nota |
|---|---|---|---|
| `gerente.coyol` | Gerente | Coyol (matriz) | |
| `cajero1.coyol` | Cajero | Coyol | |
| `cajero2.coyol` | Cajero | Coyol | contraseña vencida (RN-018: pedirá cambiarla) |
| `repartidor1.coyol`, `repartidor2.coyol` | Repartidor | Coyol | cada uno lleva 1 pedido en camino |
| `repartidor3.coyol` | Repartidor | Coyol | cuenta bloqueada por 3 intentos fallidos (RN-018) |
| `gerente.pmoreno`, `cajero1.pmoreno`, `repartidor1.pmoreno`, `repartidor2.pmoreno` | | Puente Moreno | |
| `gerente.X`, `cajero1.X`, `repartidor1.X` con X = `tejeria`, `riviera`, `carranza` | | | |

Los cocineros no inician sesión (RN-016); el cajero los asigna a cada pedido.
Clientes de prueba (entran con su teléfono): `2295865835` (el del boceto), `2291234567`, `2297654321`…
Códigos de descuento: `BIENVENIDA10` (10 %) y `PROMO50` ($50) están vigentes; `VENCIDO20` está vencido y
`USADO15` ya se usó (RN-008: cada código sirve una vez).

## Uso

| Para… | Comando | Dirección |
|---|---|---|
| Desarrollar (se recarga al guardar) | `flask --app gpizza run --debug` | http://localhost:5000 |
| Servidor tipo producción (waitress) | `python run.py` | http://localhost:8000 |
| Abrirlo desde el celular en la misma red WiFi | `python run.py 0.0.0.0` | http://IP-de-la-PC:8000 |
| Correr las pruebas | `pytest -v` | — |
| Generar las alertas de 45 y 90 min a mano | `flask --app gpizza alertas` | — |
| Desbloquear una cuenta (p. ej. la de un gerente) | `flask --app gpizza desbloquear gerente.coyol` | — |

Las pruebas usan la base `gpizza_test`: la borran, la recrean y cargan los datos de demo en cada corrida,
y cada prueba deshace sus cambios al terminar. La base `gpizza` nunca se toca.

## Cómo comprobar la Fase 1 (base de datos)

Las reglas de negocio viven también en PostgreSQL (`db/02_funciones.sql`), así que se pueden demostrar
**escribiendo SQL directo, sin la app**. Abre `psql -U gpizza_user -d gpizza` y prueba, por ejemplo:

```sql
-- RN-007: un cajero no puede cambiar precios
SELECT set_config('gpizza.rol', 'Cajero', false);
UPDATE producto SET precio = 1 WHERE id_producto = 1;
--> ERROR: RN-007 (solo el gerente edita precios): acción no permitida para el rol Cajero (requiere Gerente).

-- RN-019: la bitácora no se puede borrar
DELETE FROM auditoria;
--> ERROR: permiso denegado a la tabla auditoria

-- RNF-003: la dirección del cliente está cifrada
SELECT telefono, direccion FROM cliente LIMIT 2;
--> \x6741414141... (bytes ilegibles sin la clave del .env)

-- CU-007: notificaciones generadas por los triggers
SELECT tipo_evento, mensaje FROM notificacion ORDER BY id_notificacion DESC LIMIT 5;
```

Todas las reglas tienen su prueba automática en `tests/test_rn_bd.py` (`pytest -v tests/test_rn_bd.py`).

## Cómo comprobar la Fase 2 (autenticación y roles)

Abre http://localhost:5000/login (o "Entrar como empleado" desde el inicio):

| Prueba | Qué debe pasar | Regla |
|---|---|---|
| Entrar con `cajero1.coyol`, `repartidor1.coyol` o `gerente.coyol` | Cada uno llega a su propio panel | RF-012, RN-016 |
| Siendo cajero, abrir http://localhost:5000/gerente/ | "Acceso no permitido" (403) | RF-012 |
| Contraseña equivocada | "Usuario o contraseña incorrectos. Intento 1 de 3." | RN-018 |
| Tres contraseñas equivocadas | La cuenta se bloquea; ni la correcta funciona. Se desbloquea con `flask --app gpizza desbloquear <usuario>` | RN-018 |
| Entrar con `repartidor3.coyol` | Ya está bloqueado en la demo | RN-018 |
| Entrar con `cajero2.coyol` | Obliga a cambiar la contraseña (tiene 95 días) y valida la política | RN-018 |
| Entrar con el mismo usuario en dos navegadores | El primero queda fuera con un aviso al siguiente clic | RN-017 |

Todo queda en la bitácora: `SELECT accion, entidad, id_empleado, fecha_hora FROM auditoria ORDER BY id_log DESC LIMIT 10;`
Las pruebas están en `tests/test_auth.py`.

## Cómo comprobar la Fase 3 (pedidos)

Usa dos navegadores (o uno normal y uno en modo incógnito): uno para el cliente y otro para el cajero.

1. **Cliente** (de preferencia en tamaño celular, F12 → icono de celular): abre http://localhost:5000, escribe
   `2297654321` y continúa. Los datos de Sofía se autocompletan (CU-005).
2. Elige tamaños con los botones, súmalos con "+" y prueba los límites: "+" se apaga en 5 unidades (RN-003) y el
   total avisa cuánto falta para los $100 (RN-001).
3. Escribe `BIENVENIDA10` y pulsa "Aplicar" (RN-008). Elige "Efectivo", escribe con cuánto pagas y mira el cambio (RN-010).
   *Ojo: cada código sirve una sola vez; si lo usas, recarga la demo para recuperarlo.*
4. Recarga la página antes de enviar: el pedido se recupera del dispositivo (CU-001 FA-5). Envíalo: la pantalla
   "Tu pedido" muestra el folio y "Registrado en 0.0X s" (RNF-001), y se actualiza sola.
5. **Cajero**: entra como `cajero1.coyol`. En "Por confirmar" aparece el aviso del pedido nuevo; elige el tiempo
   (45 min / 1 h / 1 h 30) y el cocinero y confirma, o recházalo con un motivo.
6. Regresa al cliente: en menos de 10 s ve "Pedido confirmado" con su tiempo estimado o el motivo del rechazo.
7. **Pedido por teléfono**: el cajero va a "Nuevo", busca un teléfono (uno nuevo crea el cliente), arma el pedido y
   lo manda directo a cocina con su cocinero.

Fuera de 11:00–22:00 los pedidos se rechazan (RN-002); para presentar a otra hora usa `GPIZZA_HORA_DEMO`.
Las pruebas están en `tests/test_pedidos.py` y `tests/test_rendimiento.py` (`pytest -s tests/test_rendimiento.py`
imprime los tiempos medidos).

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
db/                esquema de PostgreSQL: tablas (01), triggers de reglas de negocio (02), auditoría (03)
seed/              datos de demostración
gpizza/            código de la aplicación
  config.py        lee el .env
  reglas.py        constantes de las reglas de negocio (RN)
  reloj.py         hora oficial (zona horaria y hora simulada)
  bd.py            aplica el esquema y le dice a los triggers quién actúa (rol, empleado, hora)
  modelos.py       clases de SQLAlchemy de las 12 tablas
  cli.py           comandos flask db-reset, db-seed, desbloquear y alertas
  seguridad/       cifrado (Fernet), contraseñas (Argon2id) y control de acceso por rol
  servicios/       lógica de negocio sin HTML (autenticación, catálogo, clientes, pedidos, errores de la BD)
  monitoreo.py     logs, medición de tiempos y cabeceras de seguridad
  web/             rutas: sistema, cliente, auth, cajero, repartidor y gerente
  templates/       pantallas HTML (Jinja2)
  static/          CSS, JS, iconos y librerías (Bootstrap, HTMX) incluidas para funcionar sin internet
tests/             pruebas automáticas (pytest)
docs/              documentación del proyecto, diseño y matriz de trazabilidad
run.py             arranque con waitress
```
