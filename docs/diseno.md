# GPizza: diseño técnico

> Documento de diseño previo al código. Fuente: `ANALISIS_2.docx` (ERS), `Modelo_Datos_Yungla_Pizza_Simplificado.drawio`,
> `Diagrama_CasosUso_YunglaPizza.drawio`, `Boceto_Yungla_Pizza2.pdf` y `Modelo_Negocios.docx`.
> Versión 2 (2026-11-01): incorpora las decisiones del equipo de la sección 7. Estado: **aprobado**.

## 1. Stack

| Capa | Herramienta | Por qué |
|---|---|---|
| Lenguaje | Python 3.14 (`.venv`) | Requisito del proyecto. |
| Tipo de app | **App web progresiva (PWA)** | Es la misma aplicación web, pero en el celular se "instala" en la pantalla de inicio con su icono y abre a pantalla completa, como una app móvil. En la PC funciona como página web normal. Requiere un `manifest.json` y un *service worker*. |
| Framework web | **Flask 3** con *blueprints* | Pequeño, se entiende de punta a punta en 2 semanas; cada interfaz (cliente, cajero, repartidor, gerente) es un *blueprint* (RNF-006). |
| Plantillas | Jinja2 (HTML generado en el servidor) | Una sola base de código, sin React. |
| Interactividad | **HTMX** + JavaScript simple | `hx-trigger="every 10s"` da el "se actualiza sola" de los bocetos. |
| Estilos | Bootstrap 5 + `gpizza.css` con los colores del boceto | Mobile-first (RNF-007), botones grandes (RNF-004). |
| BD | PostgreSQL 18 (`gpizza`; pruebas en `gpizza_test`) | Requisito del proyecto. |
| Acceso a BD | SQLAlchemy 2 (ORM) + psycopg 3 | Consultas parametrizadas, sin SQL concatenado (RNF-003). |
| Esquema | Archivos `.sql` escritos a mano (`db/*.sql`) | Las RN se leen directamente en SQL. Sin Alembic. |
| CSRF | Flask-WTF `CSRFProtect` | Token en formularios y en la cabecera `X-CSRFToken`. |
| Contraseñas | argon2-cffi (Argon2id) | Hash recomendado hoy. |
| Cifrado | `cryptography` (Fernet) | Cifra la dirección del cliente, la dirección de entrega y la referencia de pago (RNF-003). |
| Mapas | Leaflet + OpenStreetMap; `navigator.geolocation` | Gratuitos y sin clave de API. |
| Gráficas | Chart.js | Gráfica "Pedidos por día". |
| PDF / Excel | ReportLab / openpyxl | Python puro con *wheels* para Windows. |
| QR | `qrcode` (generar), `html5-qrcode` (escanear con la cámara) | RF-009. |
| Servidor | `flask run` (desarrollo), **waitress** ("producción") | waitress funciona en Windows y Linux (RNF-008). |
| Configuración | python-dotenv + `.env` | RNF-008. |
| Pruebas | pytest contra `gpizza_test` | Las pruebas borran y recrean datos sin tocar `gpizza`. |

## 2. Estructura de carpetas

```
Aplicacion/
├── .env.example            # plantilla de configuración (sí va en git)
├── .env                    # credenciales reales (NO va en git)
├── .gitignore
├── README.md               # instalación paso a paso (RNF-008)
├── requirements.txt
├── pytest.ini
├── run.py                  # arranque con waitress
├── db/
│   ├── 01_esquema.sql      # tablas, CHECK, UNIQUE, FK, índices
│   ├── 02_funciones.sql    # funciones y triggers de reglas de negocio
│   ├── 03_auditoria.sql    # triggers de auditoría inmutable
│   └── ejemplo_nueva_sucursal.sql   # demo RNF-005
├── gpizza/
│   ├── __init__.py         # create_app(): fábrica de la aplicación
│   ├── config.py           # lee .env
│   ├── extensiones.py      # db, csrf
│   ├── modelos.py          # clases SQLAlchemy de las 12 tablas
│   ├── reglas.py           # constantes de RN (MINIMO=100, MAX_DISTINTOS=10, …)
│   ├── cli.py              # flask db-reset, db-seed, alertas, desbloquear, nueva-sucursal
│   ├── seguridad/
│   │   ├── cifrado.py      # Fernet
│   │   ├── contrasenas.py  # Argon2 + política RN-018
│   │   └── acceso.py       # @rol_requerido, sesión única, sucursal del usuario, contexto de BD
│   ├── servicios/          # lógica de negocio (sin HTML)
│   │   ├── pedidos.py  cancelaciones.py  asignacion.py  entregas.py
│   │   ├── notificaciones.py  reportes.py  exportar.py  auditoria.py  catalogo.py  clientes.py
│   ├── web/                # blueprints (solo HTTP + plantillas)
│   │   ├── sistema.py      # /salud, errores 404/403/500, manifest y service worker
│   │   ├── cliente.py  auth.py  cajero.py  repartidor.py  gerente.py
│   │   └── api.py          # JSON para polling, GPS, notificaciones
│   ├── templates/          # base.html, cliente/, auth/, cajero/, repartidor/, gerente/, errores/
│   └── static/             # css/, js/{polling,firma,mapa,qr,borrador}.js, img/, manifest.json, sw.js
├── seed/
│   └── datos_demo.py       # sucursales Veracruz, menú, empleados, clientes, pedidos
├── tests/
│   ├── conftest.py         # usa gpizza_test
│   ├── test_rn_bd.py       # la BD rechaza datos inválidos aunque se salte el código
│   ├── test_rn_servicios.py
│   ├── test_auth.py        # RN-016..018, CSRF, acceso por rol y por sucursal
│   ├── test_seguridad.py   # inyección SQL, cifrado, auditoría inmutable
│   └── test_rendimiento.py # RNF-001
├── logs/                   # (ignorada en git)
└── docs/                   # documentación + diseno.md + trazabilidad.md + guion_demo.md
```

Las capas están separadas: `web/` recibe la petición y dibuja la pantalla, `servicios/` aplica las reglas y la base de datos las vuelve a validar.

## 3. Conversión MySQL → PostgreSQL

| En el modelo (MySQL) | En PostgreSQL | Motivo |
|---|---|---|
| `INT [PK]` | `INTEGER GENERATED ALWAYS AS IDENTITY` | Equivale a `AUTO_INCREMENT` y es el estándar SQL. |
| `BIGINT [PK]` (auditoría) | `BIGINT GENERATED ALWAYS AS IDENTITY` | Igual que arriba. |
| `TINYINT` | `SMALLINT` | PostgreSQL no tiene TINYINT. |
| `DATETIME` | `TIMESTAMPTZ` | Guarda la zona horaria; la BD usa `America/Mexico_City`. |
| `BLOB` | `BYTEA` | Binario de PostgreSQL (la firma se guarda como PNG). |
| `DECIMAL(p,s)` | `NUMERIC(p,s)` | Sinónimos; nunca `FLOAT` para dinero. |
| `TEXT` (detalle de auditoría) | `JSONB` | Guarda "antes / después" y se puede consultar. |
| `VARCHAR` + lista de valores | `VARCHAR` + `CHECK (… IN (…))` | Igual que el modelo; un `ENUM` es difícil de modificar. |
| `UNIQUE(nombre, tamano)` | `UNIQUE NULLS NOT DISTINCT (nombre, tamano)` | Para que dos complementos (sin tamaño) con el mismo nombre no se dupliquen. |
| `direccion`, `direccion_entrega`, `referencia_pago` VARCHAR | `BYTEA` cifrado | RNF-003. El teléfono se queda en texto para poder validarlo con `CHECK` y buscar por él (decisión 14). |

## 4. Esquema (12 tablas del modelo; los cambios van marcados **[NUEVO]**)

Convenciones: todas las fechas son `TIMESTAMPTZ DEFAULT now()`; todos los textos obligatorios llevan `CHECK (btrim(x) <> '')`.

### sucursal
`id_sucursal` PK · `nombre` VARCHAR(80) UNIQUE · `direccion` · `ciudad` · `estado` · `radio_cobertura_km` NUMERIC(5,2) `CHECK > 0` (se guarda, pero no se valida; ver decisión 5) · `hora_apertura` TIME DEFAULT '11:00' · `hora_cierre` TIME DEFAULT '22:00' · `CHECK (hora_apertura < hora_cierre)` · `activa` BOOLEAN.

### empleado
`id_empleado` PK · `id_sucursal` FK · `nombre` · `apellidos` · `telefono` `CHECK ~ '^[0-9]{10}$'` · `puesto` `CHECK IN ('Cajero','Cocinero','Repartidor','Gerente')` · `username` UNIQUE NULL · `password_hash` NULL · `fecha_cambio_password` DATE NULL · `intentos_fallidos` SMALLINT `CHECK 0..3` · `bloqueado` · `disponible` NULL · `latitud_actual`, `longitud_actual` · `fecha_alta` · `activo`.
- `ck_acceso`: si es Cocinero, `username` y `password_hash` son NULL (no entra al sistema); si no, ambos son obligatorios, además de `fecha_cambio_password`.
- `ck_disponible`: `disponible` tiene valor solo si es Repartidor.

### sesion
`id_sesion` PK · `id_empleado` FK · `token_hash` CHAR(64) UNIQUE (SHA-256 del token) · `dispositivo` · `fecha_inicio` · `fecha_fin` · `activa`.
- Índice único parcial `ON sesion(id_empleado) WHERE activa`.

### auditoria
`id_log` PK · `id_empleado` FK **NULL** (el cliente y el sistema no son empleados) · `accion` · `entidad` · `id_entidad` · `detalle` JSONB · `fecha_hora`.

### notificacion
`id_notificacion` PK · `id_pedido` FK NULL · `id_empleado` FK NULL · `id_cliente` FK NULL · **`rol_destino` NULL [NUEVO]** · `tipo_evento` `CHECK IN ('CAMBIO_ESTADO','ALERTA_45','ALERTA_90','ASIGNACION','SIN_REPARTIDOR','SOLICITUD_CANCELACION')` · `mensaje` · `canal` DEFAULT 'APP' · `fecha_envio` · `leida`.
- `CHECK (num_nonnulls(id_empleado, id_cliente, rol_destino) >= 1)`.
- Índice único parcial `(id_pedido, tipo_evento) WHERE tipo_evento IN ('ALERTA_45','ALERTA_90')`: la misma alerta no se repite.

### cliente
`id_cliente` PK · `nombre` · `telefono` VARCHAR(10) UNIQUE **`CHECK ~ '^[0-9]{10}$'`** · `direccion` BYTEA cifrado · `colonia` · `codigo_postal` CHAR(5) `CHECK ~ '^[0-9]{5}$'` · `latitud`, `longitud` NULL · `fecha_registro`.

### producto
`id_producto` PK · `nombre` · `descripcion` · `categoria` `CHECK IN ('Pizza','Complemento')` · `tamano` `CHECK IN ('Personal','Mediana','Grande','Familiar')` · `CHECK ((categoria='Pizza') = (tamano IS NOT NULL))` · `precio` NUMERIC(8,2) `CHECK > 0` · `codigo_qr_barras` UNIQUE NULL · `disponible` · `activo` · `UNIQUE NULLS NOT DISTINCT (nombre, tamano)`.

### codigo_descuento
`id_codigo` PK · `codigo` UNIQUE · `id_gerente` FK · `tipo` `CHECK IN ('PORCENTAJE','MONTO')` · `valor` `CHECK > 0` · `CHECK (tipo <> 'PORCENTAJE' OR valor <= 100)` · `vigencia_inicio` · `vigencia_fin` · `CHECK (vigencia_fin > vigencia_inicio)` · `usado`.

### pedido
`id_pedido` PK · `folio` UNIQUE DEFAULT `'YP-' || lpad(nextval('folio_seq')::text, 4, '0')` · `id_sucursal` FK · `id_cliente` FK ·
`id_cajero` FK **NULL** (el cajero que atiende: el que confirma el pedido en línea, el que toma la llamada o el que vende en la sucursal; solo está vacío mientras el pedido espera confirmación) ·
**`id_cocinero` FK NULL [NUEVO]** (el cajero lo elige al confirmar) ·
`id_codigo_descuento` FK NULL **UNIQUE** (un código sirve para un solo pedido) ·
**`origen` `CHECK IN ('APP','TELEFONO','SUCURSAL')` [NUEVO]** ·
`direccion_entrega` BYTEA cifrado · **`latitud_entrega`, `longitud_entrega` NULL [NUEVO]** (solo para dibujar "Tu casa" en el mapa) ·
`estado` `CHECK IN ('Por Confirmar','Rechazado','En Preparación','Listo para Entrega','En Camino','Entregado','Cancelado')` (los dos primeros son **[NUEVO]**) ·
`subtotal` **`CHECK (subtotal >= 100)`** · `descuento` `CHECK (descuento >= 0 AND descuento <= subtotal)` · `total` `CHECK (total = subtotal - descuento)` ·
`forma_pago` `CHECK IN ('Efectivo','Tarjeta','Transferencia')` · `monto_recibido` · `cambio` · `referencia_pago` BYTEA cifrado ·
**`tiempo_estimado_min` `CHECK IN (45,60,90)` [NUEVO]** · **`codigo_entrega` CHAR(4) [NUEVO]** ·
`fecha_registro` · **`fecha_preparacion` [NUEVO]** (inicio del conteo de 45 min) · `fecha_listo` · `fecha_en_camino` · `fecha_entrega` ·
**`cancelacion_solicitada_por` `CHECK IN ('CLIENTE','CAJERO')` NULL [NUEVO]** · **`fecha_solicitud_cancelacion` [NUEVO]** · **`cancelacion_confirmada_por_telefono` BOOLEAN [NUEVO]** ·
`motivo_cancelacion` · `sincronizado`.
- `ck_efectivo`: si es Efectivo → `monto_recibido >= total` y `cambio = monto_recibido - total`; si no → ambos NULL.
- `ck_motivo`: si es Cancelado o Rechazado → `motivo_cancelacion` NOT NULL.
- `ck_personal`: si el estado no es Por Confirmar, ni Rechazado, ni Cancelado → `id_cajero` e `id_cocinero` NOT NULL.

### detalle_pedido
`id_detalle` PK · `id_pedido` FK `ON DELETE CASCADE` · `id_producto` FK · `cantidad` SMALLINT `CHECK 1..5` · `precio_unitario` · `subtotal` `CHECK (subtotal = cantidad * precio_unitario)` · `UNIQUE (id_pedido, id_producto)`.

### asignacion_entrega
`id_asignacion` PK · `id_pedido` FK · `id_repartidor` FK · `id_gerente` FK NULL · `tipo` `CHECK IN ('AUTOMATICA','MANUAL')` · `CHECK (tipo <> 'MANUAL' OR id_gerente IS NOT NULL)` · `estado` `CHECK IN ('PENDIENTE','CONFIRMADA','EXPIRADA','ENTREGADA','CANCELADA')` · `fecha_asignacion` · `fecha_confirmacion` (el repartidor pulsa "Aceptar") · `fecha_limite_entrega` (+90 min) · `firma_digital` BYTEA · `codigo_confirmacion` VARCHAR(10) · **`fecha_confirmacion_cliente` [NUEVO]** · `fecha_hora_entrega`.
- `ck_entregada`: si está ENTREGADA → `fecha_confirmacion_cliente` y `fecha_hora_entrega` NOT NULL, (`firma_digital` o `codigo_confirmacion`) NOT NULL y `fecha_hora_entrega >= fecha_confirmacion_cliente`.
- Índice único parcial `(id_pedido) WHERE estado IN ('PENDIENTE','CONFIRMADA')`: un pedido solo tiene una asignación viva.

### devolucion
`id_devolucion` PK · `id_pedido` FK UNIQUE · `id_gerente` FK · `fecha_hora` · `motivo` · `accion_correctiva`.

### Relaciones
SUCURSAL 1–N EMPLEADO, PEDIDO · EMPLEADO 1–N SESION, AUDITORIA, CODIGO_DESCUENTO (gerente), ASIGNACION (repartidor y gerente), DEVOLUCION (gerente), PEDIDO (cajero **y cocinero**) · CLIENTE 1–N PEDIDO · PEDIDO 1–N DETALLE, ASIGNACION, NOTIFICACION; 1–0..1 DEVOLUCION · PRODUCTO 1–N DETALLE · CODIGO_DESCUENTO 1–0..1 PEDIDO.

## 5. Funciones y triggers (reglas en la BD)

**¿Cómo sabe la BD quién está actuando?** Al inicio de cada transacción la app ejecuta
`set_config('gpizza.id_empleado', '7', true)`, `set_config('gpizza.rol', 'Cajero', true)` y `set_config('gpizza.id_sucursal', '1', true)`
(para el cliente: `rol = 'Cliente'`). Los triggers leen esos valores con `current_setting('gpizza.rol', true)`.
El `true` final hace que el valor dure solo esa transacción.

| Trigger / función | Tabla | Regla |
|---|---|---|
| `trg_pedido_validar_alta` BEFORE INSERT | pedido | RN-002: la hora de `fecha_registro` debe estar dentro del horario de la sucursal. |
| `trg_pedido_verificar_detalle` CONSTRAINT TRIGGER **DEFERRABLE INITIALLY DEFERRED** | pedido / detalle | RN-003 (≤10 distintos) y `subtotal` = suma del detalle. Se revisa al hacer COMMIT, porque el detalle se inserta después del pedido. |
| `trg_detalle_precio` BEFORE INSERT | detalle_pedido | RN-007: `precio_unitario` = precio vigente del producto. CU-001 FA-2: el producto debe estar disponible. |
| `trg_producto_precio` BEFORE UPDATE OF precio | producto | RN-007: solo si `gpizza.rol = 'Gerente'`. |
| `trg_descuento_emisor` BEFORE INSERT | codigo_descuento | RN-008: el emisor tiene puesto Gerente. |
| `trg_pedido_descuento` BEFORE INSERT/UPDATE | pedido | RN-008: código vigente y sin usar; lo marca como usado. |
| `trg_pedido_personal` BEFORE INSERT/UPDATE | pedido | `id_cajero` es un Cajero e `id_cocinero` es un Cocinero activo, ambos de la misma sucursal del pedido. |
| `trg_pedido_transicion` BEFORE UPDATE OF estado | pedido | Máquina de estados (abajo); RN-005 con cancelación de acuerdo mutuo; RN-013 (Entregado solo si la asignación está ENTREGADA). Llena `fecha_preparacion`, `fecha_listo`, `fecha_en_camino` y `fecha_entrega`. |
| `trg_asignacion_limite` BEFORE INSERT/UPDATE | asignacion_entrega | RN-011: máx. 2 activas; bloquea la fila del repartidor con `FOR UPDATE` para que dos asignaciones simultáneas no pasen el límite. También exige un Repartidor activo, disponible y de la misma sucursal. |
| `trg_devolucion_validar` BEFORE INSERT | devolucion | RN-015: emisor Gerente de esa sucursal, pedido Entregado, ≤ 2 h desde `fecha_entrega`. |
| `trg_sesion_unica` BEFORE INSERT | sesion | RN-017: cierra la sesión activa anterior. |
| `trg_empleado_bloqueo` BEFORE UPDATE | empleado | RN-018: al llegar a 3 intentos → `bloqueado = true`. |
| `trg_auditar_*` AFTER INSERT/UPDATE | pedido, producto, empleado, asignacion, devolucion, codigo_descuento | RN-019: registro automático con el usuario de `gpizza.id_empleado`. |
| `trg_auditoria_inmutable` BEFORE UPDATE/DELETE + BEFORE TRUNCATE | auditoria | RN-019: lanza un error. Además, `REVOKE UPDATE, DELETE, TRUNCATE`. |
| `fn_generar_alertas()` | notificacion | RN-006 (45 min desde `fecha_preparacion`) y RN-014 (90 min desde `fecha_en_camino`), con `ON CONFLICT DO NOTHING`. También expira asignaciones PENDIENTE de más de 5 min (CU-002 FA-2). La llama la app en cada ciclo de *polling* y también `flask alertas`. |

**Máquina de estados del pedido**

```
Por Confirmar ──► En Preparación ──► Listo para Entrega ──► En Camino ──► Entregado
   │   │                 │                    │                 │
   │   └► Rechazado      └► Cancelado         └► Cancelado*      └► Cancelado*
   │      (cajero,          (acuerdo mutuo:      (* solo Gerente, RN-005)
   │       con motivo)       cliente + cajero)
   └► Cancelado (el cliente retira su pedido antes de que un cajero lo tome)
```

**Cancelación de acuerdo mutuo en "En Preparación" (decisión 7)**
1. El cliente (desde la app) o el cajero pide la cancelación con un motivo → se llenan `cancelacion_solicitada_por` y `fecha_solicitud_cancelacion`, y se notifica a la otra parte.
2. La otra parte acepta → "Cancelado"; si la rechaza, la solicitud se borra y el pedido sigue.
3. Pedido por teléfono o en sucursal (el cliente no usa la app): el cajero marca "El cliente confirmó la cancelación por teléfono" (`cancelacion_confirmada_por_telefono = true`) y se cancela en un paso. Queda en la auditoría.
4. El trigger exige que quien confirma sea la parte contraria a la que pidió (por `gpizza.rol`), o que exista la confirmación telefónica, o que sea el Gerente.

**Entrega en dos pasos (decisión 3)**
1. **Confirma el cliente:** firma en el canvas del celular del repartidor, o el repartidor escribe el código de 4 dígitos que el cliente ve en su app. Se valida contra `pedido.codigo_entrega` y se guardan `firma_digital` o `codigo_confirmacion`, más `fecha_confirmacion_cliente`.
2. **Confirma el repartidor:** pulsa "Confirmar entrega" con su sesión iniciada. Se guardan `fecha_hora_entrega` y su usuario en la auditoría; la asignación pasa a ENTREGADA y el pedido a Entregado.

## 6. Funcionamiento

- **Sucursal del pedido:** en el paso "1. Tus datos" el cliente elige su sucursal de una lista que se arma desde la tabla `sucursal` (RNF-005). Los pedidos por teléfono o en sucursal toman la sucursal del cajero.
- **Cada usuario ve solo su sucursal:** cajero, repartidor y gerente ven únicamente pedidos, personal, reportes, devoluciones y auditoría de su sucursal. En Reportes, el filtro "Sucursal" del boceto aparece fijo en la suya. El catálogo y los precios son de toda la cadena (como en el modelo); los clientes también, porque un cliente puede pedir a cualquier sucursal.
- **Alertas sin un proceso aparte:** cada vez que una pantalla del personal pregunta por novedades (cada 10 s) se llama a `fn_generar_alertas()`, que no duplica alertas.
- **Asignación automática:** al marcar "Listo para Entrega" se eligen los repartidores de la sucursal que estén activos, disponibles y con menos de 2 pedidos. Gana el de menor carga y, si hay empate, el que lleva más tiempo sin entregar (ya no se usa la distancia). Se crea la asignación PENDIENTE. El repartidor pulsa **"Aceptar"** (botón agregado) y el pedido pasa a "En Camino". Si no acepta en 5 min, se reasigna. El gerente puede asignar a mano.
- **Horario:** fuera de 11:00–22:00 no se pueden registrar pedidos, ni en la app ni en la BD. La pantalla de inicio del cliente muestra "Recibimos pedidos de 11:00 a 22:00". El personal sí puede iniciar sesión fuera de ese horario. `GPIZZA_HORA_DEMO` en `.env` (vacía por defecto) permite simular la hora en pruebas o en una presentación antes de las 11:00.
- **Borrador en el navegador (CU-001 FA-5):** el pedido en armado se guarda en `localStorage`; si se cae la red o se cierra la página, se recupera y se puede reenviar.
- **GPS en el celular:** la geolocalización solo funciona con HTTPS o en `localhost`. Para el celular por WiFi se usa `flask run --cert=adhoc`, y hay un botón "Simular recorrido" por si falla el GPS.
- **Desbloqueo de cuentas:** el gerente desbloquea a cajeros y repartidores desde Personal. Para desbloquear a un gerente, el administrador del servidor usa `flask desbloquear <usuario>`.
- **Medición de rendimiento (RNF-001):** un *middleware* mide cada petición y la anota en `logs/rendimiento.log` y en la cabecera `Server-Timing`. Al registrar un pedido se muestra "Registrado en X s".

## 7. Decisiones del equipo (2026-11-01)

| # | Tema | Decisión |
|---|---|---|
| 1 | Tipo de app | App móvil que también funciona en la web → PWA responsiva. |
| 2 | "Listo para Entrega" | Lo marca el cajero. |
| 3 | Confirmación de entrega | En dos pasos: primero el cliente (firma o código) y después el repartidor (botón con su sesión). |
| 4 | Flujo de los bocetos | Se agregan "Por Confirmar", "Rechazado", tiempo estimado y código de entrega. |
| 5 | Cobertura (RN-012) | **No se valida la distancia.** Se pasa a requisito no funcional futuro (RNF-009); la sucursal solo guarda `radio_cobertura_km`. El conteo de 45 min empieza en "En Preparación". El cajero del pedido es el que lo atiende (en línea, por teléfono o en sucursal). |
| 6 | Pedido mínimo (RN-001) | Se mide sobre el valor de los productos (`subtotal ≥ 100`), antes del descuento. |
| 7 | Cancelación | De acuerdo mutuo entre cliente y cajero; en pedidos telefónicos, el cajero registra la confirmación del cliente. Después de "En Preparación", solo el gerente. |
| 8 | CU-004 «include» CU-007 | Se elimina: un reporte no cambia el estado de un pedido. |
| 9 | Diagrama de casos de uso | Se corrige y se ajusta al Word (sección 8). |
| 10 | Cocineros | Cada pedido registra a su cocinero y a su cajero; ambos se ven en el detalle del pedido. |
| 11 | Gerente | Solo ve y administra su sucursal. |
| 12 | Aceptar asignación | Se agrega el botón "Aceptar" para el repartidor. |
| 13 | Sin conexión | El borrador del pedido se guarda en el navegador. |
| 14 | Teléfono del cliente | Se valida que sea numérico (10 dígitos) en la app y con `CHECK` en la BD. |
| 15 | Horario del personal | El personal puede entrar antes de las 11:00. |
| 16 | Horario de pedidos | Se bloquean fuera de 11:00–22:00 y el horario se le muestra al cliente. |
| 17 | BD de pruebas | `gpizza_test`, separada de `gpizza`. |

## 8. Cambios a la documentación (2026-11-01)

Los documentos de `docs/` ya concuerdan con este diseño. Los originales de `Desktop/Proyecto Pizza/` y `Descargas/` **no se modificaron**, por si hace falta compararlos.

### Diagrama_CasosUso_YunglaPizza.drawio
1. La flecha «extend» de CU-005 estaba invertida; ahora va de CU-005 → CU-001, como dicta UML.
2. Etiquetas en notación UML (`<<include>>` / `<<extend>>`), también en la leyenda, donde antes se veía "(<>)".
3. Se eliminó «include» CU-004 → CU-007 (decisión 8).
4. Nuevas asociaciones: Gerente–CU-009, Cajero–CU-005, Cajero–CU-010 y Cliente–CU-001/CU-005/CU-010.
5. Se reacomodaron los casos de uso para reducir cruces de líneas, y la leyenda quedó fuera del límite del sistema.

### Modelo_Datos_Yungla_Pizza_Simplificado.drawio
1. Tipos convertidos a PostgreSQL (INTEGER IDENTITY, SMALLINT, TIMESTAMPTZ, NUMERIC, BYTEA, JSONB) y nota de versión en el diagrama.
2. Columnas nuevas de la sección 4 (cocinero, origen, coordenadas de entrega, tiempo estimado, código de entrega, fecha de preparación, cancelación de acuerdo mutuo, confirmación del cliente, rol destino).
3. Nueva relación PEDIDO → EMPLEADO (`id_cocinero`); `id_cajero` e `id_cocinero` pasan a ser opcionales (0..1).
4. Restricciones nuevas en las etiquetas (subtotal ≥ 100, teléfono de 10 dígitos, `UNIQUE (id_pedido, id_producto)`, etc.).

### BPMN_Proceso_GPizza.drawio (nuevo)
Rediseño del BPMN con 5 carriles (Cliente, Sistema, Cajero, Cocina, Repartidor) y el flujo acordado: confirmación o rechazo del cajero, cocinero, "Listo para Entrega" marcado por el cajero, aceptación del repartidor y entrega en dos pasos. El BPMN anterior solo existía como imagen.

### ANALISIS_2.docx (ERS)
- 1.2, 3.1.1, 3.1.3, 3.1.4 y 9.1: app móvil progresiva (PWA) también accesible por web; notificaciones dentro de la app; stack.
- 2.3: nueva línea "Cocinero"; el gerente solo ve su sucursal; actualizados Cajero, Repartidor y Cliente.
- RF-001, 003, 004, 005, 006, 007, 008 y 010: descripciones y RN asociadas.
- RNF-003, 007 y 008 actualizados; **nuevo RNF-009** (cobertura geográfica, antes RN-012).
- RN-001, 002, 004, 005, 006, 012, 013, 015, 016 y 018 según las decisiones 5–16.
- Fichas CU-001, 002, 003, 004, 005, 006, 007, 009, 009b y 010; CU-007 ya no se incluye en CU-004.
- Matriz actor × CU: el Cliente participa en CU-001, CU-005 y CU-010.
- Figura 3 reemplazada por el diagrama corregido.

### Modelo_Negocios.docx
- §1 y 1.2: app móvil progresiva, también accesible por web.
- Stakeholders: gerentes, cajeros, cocineros, repartidores, clientes y sistema de notificaciones.
- §4.2: texto y Figura 2 con el BPMN nuevo.
- §5: Figura 3 con el diagrama corregido; actores y casos de uso con la numeración y los nombres vigentes (CU-010 en lugar del CU-002 duplicado) y sin «include» CU-004 → CU-007.

**No se tocaron:** el Business Model Canvas (Figura 1), la entrevista, el análisis costo-beneficio ni la duración de 6 meses de la sección 8 del ERS, porque describen el negocio y el proyecto comercial, no el software que vamos a construir.
