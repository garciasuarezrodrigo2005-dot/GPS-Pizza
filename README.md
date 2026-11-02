# GPizza

Sistema de Gestión de Pedidos a Domicilio para **Yungla Pizza S.A. de C.V.**
Proyecto escolar del Instituto Tecnológico de Veracruz (Ingeniería en Sistemas Computacionales).

Es una **app móvil progresiva (PWA)**: en el celular se instala en la pantalla de inicio como una app y en la PC
funciona como página web. Tiene tres interfaces: **Cliente**, **Personal** (cajero y repartidor) y **Gerente**.

> Estado: **completo (Fases 0 a 7)**. Guion de la presentación: [docs/guion_demo.md](docs/guion_demo.md) (ver [docs/trazabilidad.md](docs/trazabilidad.md)).

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

## Cómo comprobar la Fase 4 (ciclo del pedido)

Abre tres navegadores: cliente, `cajero1.coyol` y `repartidor1.coyol` (y si quieres un cuarto con `gerente.coyol`).

1. **Listo y asignación automática (CU-002):** el cajero va a "Pedidos" → "En preparación" y pulsa "Marcar listo".
   El sistema elige al repartidor libre con menos carga y le avisa.
2. **Aceptar (CU-002 paso 5):** en "Mis entregas" el repartidor ve el pedido con su plazo de 5 min y pulsa
   "Aceptar entrega". El pedido pasa a "En camino" y el cliente ve su código de entrega. Si no acepta en 5 min, en la
   siguiente revisión se ofrece a otro repartidor (FA-2).
3. **Sin repartidor (FA-1) y asignación manual (FA-3):** desactiva a los repartidores con su interruptor y marca otro
   pedido como listo: el gerente recibe el aviso en su campana 🔔 y lo asigna en "Pedidos" → "Listo".
4. **Máximo 2 (RN-011):** con dos pedidos activos, un repartidor ya no aparece como opción.
5. **Cancelación de acuerdo mutuo (RN-005):** en "Tu pedido" el cliente pide cancelar; el cajero acepta o rechaza
   en su tarjeta. También al revés. Un pedido telefónico se cancela marcando "El cliente confirmó por teléfono".
   En "Listo" o "En camino" solo el gerente puede cancelar.
6. **Alertas (RN-006, RN-014):** las tarjetas se marcan en rojo al pasar 45 min en preparación o 90 en camino, y llega
   el aviso a la campana. Con los datos de demo y `GPIZZA_HORA_DEMO=14:00` ya hay un pedido de cada caso.
7. **Seguimiento (CU-003):** busca por folio (`YP-0225` o solo `225`) o por teléfono y abre "Ver detalle".

La revisión de alertas y reasignaciones corre sola mientras haya una pantalla del personal abierta (cada 10–15 s);
también se puede forzar con `flask --app gpizza alertas`. Las pruebas están en `tests/test_ciclo.py`.

## Cómo comprobar la Fase 5 (repartidor, mapas y firma)

1. **Mapa del repartidor (boceto 9):** entra como `repartidor1.coyol`. Cada entrega en camino muestra un mapa con 🛵 y 🏠,
   "Llamar" y "Abrir ruta" (OpenStreetMap). Los mapas necesitan internet para descargar los mosaicos.
2. **GPS:** con HTTPS (ver abajo) el navegador pide permiso y manda la posición cada 15 s, **solo mientras hay una entrega
   en camino** (boceto 5: "el GPS se activa solo cuando se asigna un repartidor y se apaga al entregar"). Sin GPS, el botón
   **"Simular recorrido"** mueve al repartidor hacia el domicilio en 30 s.
3. **Mapa del cliente (boceto 5):** con el teléfono del cliente de ese pedido, "Tu pedido" muestra el mapa en vivo, el nombre
   del repartidor, "Llega en ~N min", "Llamar" y el código de entrega.
4. **Entrega en dos pasos (RN-013, RF-010):** el cliente firma con el dedo en el recuadro **o** dicta su código de 4 dígitos
   → "Registrar confirmación del cliente"; después el repartidor pulsa "Marcar como entregado". Sin el paso 1 no se puede.
   Un código equivocado se rechaza.
5. **Evidencia:** cajero o gerente abren "Ver detalle" del pedido entregado: aparecen la firma, la hora de cada paso y quién
   entregó. El repartidor ve sus entregas del día en "Historial".

Las pruebas están en `tests/test_entregas.py`.

## Cómo comprobar la Fase 6 (panel del gerente)

Entra como `gerente.coyol`. Todo lo que ves es solo de tu sucursal.

| Sección | Qué probar | Regla |
|---|---|---|
| Catálogo y precios | Cambia un precio o apaga "Disponible": el menú del cliente lo refleja al instante. "Imprimir etiquetas QR" genera una hoja con el QR de cada producto | RN-007, RF-002, RF-009 |
| Clientes | Busca por teléfono o nombre, edita la dirección y ve su historial | RF-005 |
| Personal | Da de alta un cajero: aparece su contraseña temporal, que deberá cambiar al entrar. Desbloquea a `repartidor3.coyol`. Intenta dar de baja a un repartidor en ruta | CU-009, 009a, 009b, RN-018 |
| Descuentos y devoluciones | Emite un código (p. ej. 15 %) y úsalo en un pedido: queda "Usado". Registra la devolución de un pedido entregado hace menos de 2 h | RN-008, RF-011, RN-015 |
| Reportes | Cambia el período o el repartidor y pulsa "Generar"; exporta a PDF y a Excel | CU-004, CU-008 |
| Auditoría | Filtra por acción (LOGIN, CANCELAR…) o por usuario; no hay forma de editar ni borrar | RN-019 |

**Escaneo (RF-009):** en "Nuevo pedido" del cajero, escribe `YP000002` y Enter (o escanéalo con un lector USB o con la
cámara del celular en HTTPS): la Pepperoni Mediana se suma al pedido. En el detalle de un pedido, "Imprimir comanda" genera
el ticket con el QR del folio; escanearlo en "Buscar pedido" abre su seguimiento.
Las pruebas están en `tests/test_gerente.py` y `tests/test_reportes.py`.

## Requisitos no funcionales (Fase 7)

| RNF | Cómo se demuestra |
|---|---|
| RNF-001 Rendimiento | `pytest -s tests/test_rendimiento.py` (20 pedidos, máximo ~0.03 s; límite 3 s). Cada respuesta trae `Server-Timing` y queda en `logs/rendimiento.log`. Los reportes muestran "Generado en X s" |
| RNF-002 Disponibilidad | `/salud`. Con PowerShell como administrador: `Stop-Service postgresql-x64-18` → `/salud` responde 503 y el inicio sigue abriendo; `Start-Service postgresql-x64-18` → se recupera sola. Ninguna ruta responde 500 (`tests/test_rnf.py`) |
| RNF-003 Seguridad | `pytest -v tests/test_rnf.py tests/test_auth.py`: 50 rutas × 4 perfiles; Argon2id, Fernet, CSRF, sesión única, inyección SQL, auditoría inmutable |
| RNF-004 Usabilidad / RNF-007 Compatibilidad | [docs/evidencias/](docs/evidencias/README.md): capturas en Chrome y Edge a 375 px y 1366 px, sin desborde horizontal |
| RNF-005 Escalabilidad | `flask --app gpizza nueva-sucursal --nombre "Boca del Río" --direccion "…" --ciudad "Boca del Río" --gerente gerente.bocadelrio --gerente-nombre Laura --gerente-apellidos "Mendoza Ruiz" --gerente-telefono 2291234500`, o `db/ejemplo_nueva_sucursal.sql` |
| RNF-006 Mantenibilidad | Estructura por capas (abajo), cada módulo documentado (`test_rnf006_*`), reglas centralizadas en `gpizza/reglas.py` |
| RNF-008 Portabilidad | Esta guía se probó clonando el repositorio en una carpeta vacía: venv, `pip install`, `.env`, `db-reset`, `db-seed`, waitress y `pytest` |

### Probar en el celular (HTTPS)

Los navegadores solo comparten la ubicación en páginas seguras (`https://` o `localhost`). Para usar el celular en la misma
red WiFi que la PC:

```powershell
flask --app gpizza run --cert=adhoc --host 0.0.0.0 --port 5443
```

y abre `https://IP-de-la-PC:5443` (la IP se ve con `ipconfig`). El certificado es autofirmado: el celular mostrará
"La conexión no es privada"; toca "Configuración avanzada → Continuar". Con eso funcionan la ubicación y la firma.
Con un certificado autofirmado Chrome no instala la app como PWA; para eso hace falta un certificado real (por ejemplo,
publicar la app con un túnel como `cloudflared` o en un servidor con HTTPS).

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
    img/logo.svg   ícono de la app (los PNG de la PWA salen de él)
    img/productos/ un dibujo SVG por producto; el nombre del archivo sale del nombre del producto
herramientas/      generadores de los íconos: iconos_productos.py e icono_app.py (con "png" crea los PNG)
tests/             pruebas automáticas (pytest)
docs/              documentación del proyecto, diseño y matriz de trazabilidad
run.py             arranque con waitress
```
