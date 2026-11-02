-- =====================================================================================
-- GPizza · 01_esquema.sql
-- Tablas, llaves y restricciones (modelo de datos v2, docs/diseno.md §4).
-- Las restricciones que implementan una regla de negocio llevan el código de la regla
-- en su nombre (p. ej. rn001_...), así el error que devuelve PostgreSQL dice qué regla falló.
-- =====================================================================================
SET client_min_messages = warning;

-- -------------------------------------------------------------------------------------
-- Contexto de la transacción
-- La app ejecuta set_config('gpizza.rol', 'Cajero', true), etc. al iniciar cada
-- transacción. Estas funciones lo leen; el 'true' de set_config hace que el valor dure
-- solo esa transacción. Si la app no fija el rol, se toma 'Sistema' (el de menos permisos).
-- -------------------------------------------------------------------------------------
CREATE FUNCTION fn_ahora() RETURNS timestamptz LANGUAGE sql STABLE AS $$
    -- Hora oficial: la real, o la simulada por la app (GPIZZA_HORA_DEMO / datos de demo).
    SELECT coalesce(nullif(current_setting('gpizza.ahora', true), '')::timestamptz, now())
$$;

CREATE FUNCTION fn_rol() RETURNS text LANGUAGE sql STABLE AS $$
    SELECT coalesce(nullif(current_setting('gpizza.rol', true), ''), 'Sistema')
$$;

CREATE FUNCTION fn_id_empleado() RETURNS integer LANGUAGE sql STABLE AS $$
    SELECT nullif(current_setting('gpizza.id_empleado', true), '')::integer
$$;

CREATE SEQUENCE folio_seq;

-- -------------------------------------------------------------------------------------
CREATE TABLE sucursal (
    id_sucursal        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre             VARCHAR(80)  NOT NULL UNIQUE CHECK (btrim(nombre) <> ''),
    direccion          VARCHAR(200) NOT NULL CHECK (btrim(direccion) <> ''),
    ciudad             VARCHAR(60)  NOT NULL CHECK (btrim(ciudad) <> ''),
    estado             VARCHAR(60)  NOT NULL CHECK (btrim(estado) <> ''),
    radio_cobertura_km NUMERIC(5,2) NOT NULL CHECK (radio_cobertura_km > 0),  -- dato para RNF-009 (futuro)
    hora_apertura      TIME NOT NULL DEFAULT '11:00',
    hora_cierre        TIME NOT NULL DEFAULT '22:00',
    activa             BOOLEAN NOT NULL DEFAULT true,
    CONSTRAINT rn002_sucursal_horario CHECK (hora_apertura < hora_cierre)
);

-- -------------------------------------------------------------------------------------
CREATE TABLE empleado (
    id_empleado           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_sucursal           INTEGER REFERENCES sucursal,           -- NULL solo para el Administrador
    nombre                VARCHAR(60) NOT NULL CHECK (btrim(nombre) <> ''),
    apellidos             VARCHAR(80) NOT NULL CHECK (btrim(apellidos) <> ''),
    telefono              VARCHAR(10) NOT NULL CHECK (telefono ~ '^[0-9]{10}$'),
    -- RN-016: una sola columna de puesto = exactamente un rol por usuario.
    puesto                VARCHAR(13) NOT NULL
                          CHECK (puesto IN ('Cajero', 'Cocinero', 'Repartidor', 'Gerente', 'Administrador')),
    username              VARCHAR(40) UNIQUE CHECK (username ~ '^[a-z0-9._-]{4,40}$'),
    password_hash         VARCHAR(255),
    fecha_cambio_password DATE,
    intentos_fallidos     SMALLINT NOT NULL DEFAULT 0,
    bloqueado             BOOLEAN NOT NULL DEFAULT false,
    disponible            BOOLEAN,
    latitud_actual        NUMERIC(9,6) CHECK (latitud_actual BETWEEN -90 AND 90),
    longitud_actual       NUMERIC(9,6) CHECK (longitud_actual BETWEEN -180 AND 180),
    fecha_alta            DATE NOT NULL DEFAULT current_date,
    activo                BOOLEAN NOT NULL DEFAULT true,
    -- RN-016: el cocinero no inicia sesión; los demás puestos sí y necesitan credenciales.
    CONSTRAINT rn016_empleado_acceso CHECK (
        (puesto = 'Cocinero' AND username IS NULL AND password_hash IS NULL AND fecha_cambio_password IS NULL)
        OR (puesto <> 'Cocinero' AND username IS NOT NULL AND password_hash IS NOT NULL
            AND fecha_cambio_password IS NOT NULL)),
    CONSTRAINT rn018_intentos CHECK (intentos_fallidos BETWEEN 0 AND 3),
    -- Decisión 19: el Administrador es de toda la cadena (sin sucursal); los demás puestos, de una sucursal.
    CONSTRAINT rn016_administrador_sin_sucursal CHECK ((puesto = 'Administrador') = (id_sucursal IS NULL)),
    -- La disponibilidad (interruptor del boceto) solo aplica al repartidor.
    CONSTRAINT ck_empleado_disponible CHECK ((puesto = 'Repartidor') = (disponible IS NOT NULL))
);

-- -------------------------------------------------------------------------------------
CREATE TABLE sesion (
    id_sesion    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_empleado  INTEGER NOT NULL REFERENCES empleado,
    token_hash   CHAR(64) NOT NULL UNIQUE,  -- SHA-256 del token; el token mismo nunca se guarda
    dispositivo  VARCHAR(100),
    fecha_inicio TIMESTAMPTZ NOT NULL DEFAULT fn_ahora(),
    fecha_fin    TIMESTAMPTZ,
    activa       BOOLEAN NOT NULL DEFAULT true,
    CONSTRAINT ck_sesion_fin CHECK (activa OR fecha_fin IS NOT NULL)
);
-- RN-017: como máximo una sesión activa por empleado.
CREATE UNIQUE INDEX rn017_sesion_unica ON sesion (id_empleado) WHERE activa;

-- -------------------------------------------------------------------------------------
CREATE TABLE auditoria (
    id_log      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_empleado INTEGER REFERENCES empleado,  -- NULL: acción del cliente o del sistema
    accion      VARCHAR(40) NOT NULL,
    entidad     VARCHAR(40) NOT NULL,
    id_entidad  INTEGER,
    detalle     JSONB,
    fecha_hora  TIMESTAMPTZ NOT NULL DEFAULT fn_ahora()
);
CREATE INDEX ix_auditoria_entidad ON auditoria (entidad, id_entidad);
CREATE INDEX ix_auditoria_fecha ON auditoria (fecha_hora);

-- -------------------------------------------------------------------------------------
CREATE TABLE cliente (
    id_cliente     INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre         VARCHAR(100) NOT NULL CHECK (btrim(nombre) <> ''),
    -- RN-004 y decisión 14: teléfono obligatorio, numérico de 10 dígitos.
    telefono       VARCHAR(10) NOT NULL UNIQUE CONSTRAINT rn004_cliente_telefono CHECK (telefono ~ '^[0-9]{10}$'),
    -- Cifrada (RNF-003). Decisión 21: opcional; se guarda con el primer pedido (la cuenta se crea sin ella).
    -- Cada pedido lleva su propia dirección de destino (pedido.direccion_entrega, obligatoria).
    direccion      BYTEA CHECK (octet_length(direccion) > 0),
    colonia        VARCHAR(80),
    codigo_postal  CHAR(5) CHECK (codigo_postal ~ '^[0-9]{5}$'),
    latitud        NUMERIC(9,6) CHECK (latitud BETWEEN -90 AND 90),
    longitud       NUMERIC(9,6) CHECK (longitud BETWEEN -180 AND 180),
    fecha_registro TIMESTAMPTZ NOT NULL DEFAULT fn_ahora(),
    -- Decisión 18: cuenta del cliente. Un cliente dado de alta por el cajero (pedido por teléfono) no tiene
    -- contraseña hasta que él mismo crea su cuenta con ese teléfono. RN-018 también aplica: 3 intentos.
    password_hash      VARCHAR(255),
    fecha_alta_cuenta  TIMESTAMPTZ,
    intentos_fallidos  SMALLINT NOT NULL DEFAULT 0,
    bloqueado          BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT rn018_cliente_intentos CHECK (intentos_fallidos BETWEEN 0 AND 3),
    CONSTRAINT ck_cliente_cuenta CHECK ((password_hash IS NULL) = (fecha_alta_cuenta IS NULL))
);

-- -------------------------------------------------------------------------------------
CREATE TABLE producto (
    id_producto      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre           VARCHAR(80) NOT NULL CHECK (btrim(nombre) <> ''),
    descripcion      VARCHAR(200),
    categoria        VARCHAR(12) NOT NULL CHECK (categoria IN ('Pizza', 'Complemento')),
    tamano           VARCHAR(10) CHECK (tamano IN ('Personal', 'Mediana', 'Grande', 'Familiar')),
    precio           NUMERIC(8,2) NOT NULL CHECK (precio > 0),
    codigo_qr_barras VARCHAR(50) UNIQUE,
    disponible       BOOLEAN NOT NULL DEFAULT true,
    activo           BOOLEAN NOT NULL DEFAULT true,
    CONSTRAINT ck_producto_tamano CHECK ((categoria = 'Pizza') = (tamano IS NOT NULL)),
    CONSTRAINT uq_producto_nombre_tamano UNIQUE NULLS NOT DISTINCT (nombre, tamano)
);

-- -------------------------------------------------------------------------------------
CREATE TABLE codigo_descuento (
    id_codigo       INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo          VARCHAR(20) NOT NULL UNIQUE CHECK (codigo ~ '^[A-Z0-9-]{4,20}$'),
    id_gerente      INTEGER NOT NULL REFERENCES empleado,  -- RN-008: lo emite un gerente
    tipo            VARCHAR(12) NOT NULL CHECK (tipo IN ('PORCENTAJE', 'MONTO')),
    valor           NUMERIC(8,2) NOT NULL CHECK (valor > 0),
    vigencia_inicio TIMESTAMPTZ NOT NULL,
    vigencia_fin    TIMESTAMPTZ NOT NULL,
    usado           BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT ck_descuento_porcentaje CHECK (tipo <> 'PORCENTAJE' OR valor <= 100),
    CONSTRAINT ck_descuento_vigencia CHECK (vigencia_fin > vigencia_inicio)
);

-- -------------------------------------------------------------------------------------
CREATE TABLE pedido (
    id_pedido           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    folio               VARCHAR(20) NOT NULL UNIQUE DEFAULT ('YP-' || lpad(nextval('folio_seq')::text, 4, '0')),
    id_sucursal         INTEGER NOT NULL REFERENCES sucursal,
    id_cliente          INTEGER NOT NULL REFERENCES cliente,       -- RN-004
    id_cajero           INTEGER REFERENCES empleado,               -- quien lo atiende
    id_cocinero         INTEGER REFERENCES empleado,               -- quien lo prepara
    id_codigo_descuento INTEGER UNIQUE REFERENCES codigo_descuento, -- RN-008: un código, un pedido
    origen              VARCHAR(10) NOT NULL CHECK (origen IN ('APP', 'TELEFONO', 'SUCURSAL')),
    direccion_entrega   BYTEA NOT NULL CHECK (octet_length(direccion_entrega) > 0),  -- cifrada; RN-004
    latitud_entrega     NUMERIC(9,6) CHECK (latitud_entrega BETWEEN -90 AND 90),
    longitud_entrega    NUMERIC(9,6) CHECK (longitud_entrega BETWEEN -180 AND 180),
    estado              VARCHAR(20) NOT NULL DEFAULT 'Por Confirmar' CHECK (estado IN (
                            'Por Confirmar', 'Rechazado', 'En Preparación', 'Listo para Entrega',
                            'En Camino', 'Entregado', 'Cancelado')),
    subtotal            NUMERIC(10,2) NOT NULL,
    descuento           NUMERIC(10,2) NOT NULL DEFAULT 0,
    total               NUMERIC(10,2) NOT NULL,
    -- RN-009: una sola columna = un solo método de pago por pedido.
    forma_pago          VARCHAR(15) NOT NULL CONSTRAINT rn009_forma_pago
                            CHECK (forma_pago IN ('Efectivo', 'Tarjeta', 'Transferencia')),
    monto_recibido      NUMERIC(10,2),
    cambio              NUMERIC(10,2),
    referencia_pago     BYTEA,                                      -- cifrada
    tiempo_estimado_min SMALLINT CHECK (tiempo_estimado_min IN (45, 60, 90)),
    codigo_entrega      CHAR(4) CHECK (codigo_entrega ~ '^[0-9]{4}$'),
    fecha_registro      TIMESTAMPTZ NOT NULL DEFAULT fn_ahora(),
    fecha_preparacion   TIMESTAMPTZ,  -- inicio del conteo de 45 min (RN-006)
    fecha_listo         TIMESTAMPTZ,
    fecha_en_camino     TIMESTAMPTZ,  -- inicio del conteo de 90 min (RN-014)
    fecha_entrega       TIMESTAMPTZ,  -- inicio del plazo de 2 h para devoluciones (RN-015)
    cancelacion_solicitada_por          VARCHAR(8) CHECK (cancelacion_solicitada_por IN ('CLIENTE', 'CAJERO')),
    fecha_solicitud_cancelacion         TIMESTAMPTZ,
    cancelacion_confirmada_por_telefono BOOLEAN NOT NULL DEFAULT false,
    motivo_cancelacion  VARCHAR(200),
    sincronizado        BOOLEAN NOT NULL DEFAULT true,

    CONSTRAINT rn001_pedido_minimo CHECK (subtotal >= 100),
    CONSTRAINT rn008_descuento_rango CHECK (descuento >= 0 AND descuento <= subtotal),
    CONSTRAINT ck_pedido_total CHECK (total = subtotal - descuento),
    -- RN-010: en efectivo se registra con cuánto paga el cliente y el cambio debe cuadrar.
    CONSTRAINT rn010_cambio CHECK (
        (forma_pago = 'Efectivo' AND monto_recibido IS NOT NULL AND monto_recibido >= total
            AND cambio = monto_recibido - total)
        OR (forma_pago <> 'Efectivo' AND monto_recibido IS NULL AND cambio IS NULL)),
    CONSTRAINT ck_pedido_motivo CHECK (
        estado NOT IN ('Cancelado', 'Rechazado') OR btrim(coalesce(motivo_cancelacion, '')) <> ''),
    -- Decisión 10: un pedido en curso siempre tiene cajero y cocinero.
    CONSTRAINT ck_pedido_personal CHECK (
        estado IN ('Por Confirmar', 'Cancelado')
        OR (estado = 'Rechazado' AND id_cajero IS NOT NULL)
        OR (id_cajero IS NOT NULL AND id_cocinero IS NOT NULL)),
    CONSTRAINT ck_pedido_confirmado CHECK (
        estado IN ('Por Confirmar', 'Rechazado', 'Cancelado')
        OR (tiempo_estimado_min IS NOT NULL AND codigo_entrega IS NOT NULL AND fecha_preparacion IS NOT NULL)),
    CONSTRAINT ck_pedido_solicitud CHECK (
        (cancelacion_solicitada_por IS NULL) = (fecha_solicitud_cancelacion IS NULL))
);
CREATE INDEX ix_pedido_sucursal_estado ON pedido (id_sucursal, estado);
CREATE INDEX ix_pedido_cliente ON pedido (id_cliente);
CREATE INDEX ix_pedido_fecha ON pedido (fecha_registro);

-- -------------------------------------------------------------------------------------
CREATE TABLE detalle_pedido (
    id_detalle      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_pedido       INTEGER NOT NULL REFERENCES pedido ON DELETE CASCADE,
    id_producto     INTEGER NOT NULL REFERENCES producto,
    cantidad        SMALLINT NOT NULL CONSTRAINT rn003_unidades CHECK (cantidad BETWEEN 1 AND 5),
    precio_unitario NUMERIC(8,2) NOT NULL CHECK (precio_unitario > 0),
    subtotal        NUMERIC(10,2) NOT NULL,
    CONSTRAINT ck_detalle_subtotal CHECK (subtotal = cantidad * precio_unitario),
    -- RN-003: cada producto aparece una vez; así "productos distintos" = renglones del pedido.
    CONSTRAINT rn003_producto_unico UNIQUE (id_pedido, id_producto)
);

-- -------------------------------------------------------------------------------------
CREATE TABLE asignacion_entrega (
    id_asignacion              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_pedido                  INTEGER NOT NULL REFERENCES pedido,
    id_repartidor              INTEGER NOT NULL REFERENCES empleado,
    id_gerente                 INTEGER REFERENCES empleado,  -- solo en asignación manual
    tipo                       VARCHAR(10) NOT NULL CHECK (tipo IN ('AUTOMATICA', 'MANUAL')),
    estado                     VARCHAR(12) NOT NULL DEFAULT 'PENDIENTE'
                                   CHECK (estado IN ('PENDIENTE', 'CONFIRMADA', 'EXPIRADA', 'ENTREGADA', 'CANCELADA')),
    fecha_asignacion           TIMESTAMPTZ NOT NULL DEFAULT fn_ahora(),
    fecha_confirmacion         TIMESTAMPTZ,  -- el repartidor pulsa "Aceptar"
    fecha_limite_entrega       TIMESTAMPTZ,  -- aceptación + 90 min (RN-014)
    firma_digital              BYTEA,        -- PNG del canvas
    codigo_confirmacion        VARCHAR(10),
    fecha_confirmacion_cliente TIMESTAMPTZ,  -- paso 1 de la entrega
    fecha_hora_entrega         TIMESTAMPTZ,  -- paso 2 de la entrega
    CONSTRAINT ck_asignacion_manual CHECK (tipo <> 'MANUAL' OR id_gerente IS NOT NULL),
    CONSTRAINT ck_asignacion_aceptada CHECK (
        estado NOT IN ('CONFIRMADA', 'ENTREGADA') OR (fecha_confirmacion IS NOT NULL AND fecha_limite_entrega IS NOT NULL)),
    -- RN-013 paso 1: la confirmación del cliente es una firma o un código.
    CONSTRAINT rn013_confirmacion_cliente CHECK (
        (fecha_confirmacion_cliente IS NULL) = (firma_digital IS NULL AND codigo_confirmacion IS NULL)),
    -- RN-013 paso 2: no hay entrega sin confirmación previa del cliente.
    CONSTRAINT rn013_entrega CHECK (
        estado <> 'ENTREGADA' OR (fecha_confirmacion_cliente IS NOT NULL AND fecha_hora_entrega IS NOT NULL
                                  AND fecha_hora_entrega >= fecha_confirmacion_cliente))
);
-- Un pedido tiene a lo más una asignación viva.
CREATE UNIQUE INDEX uq_asignacion_viva ON asignacion_entrega (id_pedido) WHERE estado IN ('PENDIENTE', 'CONFIRMADA');
CREATE INDEX ix_asignacion_repartidor_viva ON asignacion_entrega (id_repartidor) WHERE estado IN ('PENDIENTE', 'CONFIRMADA');

-- -------------------------------------------------------------------------------------
CREATE TABLE devolucion (
    id_devolucion     INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_pedido         INTEGER NOT NULL UNIQUE REFERENCES pedido,
    id_gerente        INTEGER NOT NULL REFERENCES empleado,  -- RN-015
    fecha_hora        TIMESTAMPTZ NOT NULL DEFAULT fn_ahora(),
    motivo            VARCHAR(200) NOT NULL CHECK (btrim(motivo) <> ''),
    accion_correctiva VARCHAR(200) NOT NULL CHECK (btrim(accion_correctiva) <> '')
);

-- -------------------------------------------------------------------------------------
CREATE TABLE notificacion (
    id_notificacion INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_pedido       INTEGER REFERENCES pedido,
    id_empleado     INTEGER REFERENCES empleado,
    id_cliente      INTEGER REFERENCES cliente,
    rol_destino     VARCHAR(12) CHECK (rol_destino IN ('Cajero', 'Repartidor', 'Gerente')),
    tipo_evento     VARCHAR(30) NOT NULL CHECK (tipo_evento IN (
                        'CAMBIO_ESTADO', 'ALERTA_45', 'ALERTA_90', 'ASIGNACION', 'SIN_REPARTIDOR',
                        'SOLICITUD_CANCELACION')),
    mensaje         VARCHAR(255) NOT NULL,
    canal           VARCHAR(15) NOT NULL DEFAULT 'APP',
    fecha_envio     TIMESTAMPTZ NOT NULL DEFAULT fn_ahora(),
    leida           BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT ck_notificacion_destino CHECK (num_nonnulls(id_empleado, id_cliente, rol_destino) >= 1),
    -- Avisar "a todos los gerentes" solo tiene sentido si se sabe de qué pedido (y de qué sucursal).
    CONSTRAINT ck_notificacion_rol CHECK (rol_destino IS NULL OR id_pedido IS NOT NULL)
);
-- RN-006 / RN-014: cada alerta se genera una sola vez por pedido y destinatario.
CREATE UNIQUE INDEX uq_notificacion_alerta ON notificacion (id_pedido, tipo_evento, rol_destino)
    WHERE tipo_evento IN ('ALERTA_45', 'ALERTA_90');
CREATE INDEX ix_notificacion_cliente ON notificacion (id_cliente) WHERE NOT leida;
CREATE INDEX ix_notificacion_empleado ON notificacion (id_empleado) WHERE NOT leida;
