-- =====================================================================================
-- GPizza · 02_funciones.sql
-- Triggers que hacen cumplir las reglas de negocio dentro de la base de datos.
-- La app valida lo mismo antes (para dar mensajes claros); esto es la segunda capa:
-- aunque alguien se salte el código Python y escriba SQL directo, la regla se respeta.
-- Cada error empieza con el código de la regla (p. ej. "RN-005: ...").
-- =====================================================================================
SET client_min_messages = warning;

-- Atajo para lanzar errores con mensaje en español.
CREATE FUNCTION fn_error(mensaje text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '%', mensaje USING ERRCODE = 'check_violation';
END $$;

-- Verifica que el usuario de la transacción tenga uno de los roles permitidos.
CREATE FUNCTION fn_exigir_rol(permitidos text[], regla text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    IF NOT fn_rol() = ANY (permitidos) THEN
        PERFORM fn_error(format('%s: acción no permitida para el rol %s (requiere %s).',
                                regla, fn_rol(), array_to_string(permitidos, ' o ')));
    END IF;
END $$;

-- Verifica que un empleado exista, esté activo, tenga el puesto indicado y sea de la sucursal.
CREATE FUNCTION fn_exigir_empleado(p_id integer, puestos text[], p_sucursal integer, que text)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE e empleado%ROWTYPE;
BEGIN
    SELECT * INTO e FROM empleado WHERE id_empleado = p_id;
    IF NOT FOUND OR NOT e.activo THEN
        PERFORM fn_error(format('El %s indicado no existe o está dado de baja.', que));
    ELSIF NOT e.puesto = ANY (puestos) THEN
        PERFORM fn_error(format('El %s debe tener puesto %s (tiene %s).', que, array_to_string(puestos, ' o '), e.puesto));
    ELSIF p_sucursal IS NOT NULL AND e.id_sucursal <> p_sucursal THEN
        PERFORM fn_error(format('El %s pertenece a otra sucursal.', que));
    END IF;
END $$;

-- Notificación dentro de la app (CU-007).
CREATE FUNCTION fn_notificar(p_pedido integer, p_tipo text, p_mensaje text,
                             p_cliente integer DEFAULT NULL, p_empleado integer DEFAULT NULL,
                             p_rol text DEFAULT NULL)
RETURNS void LANGUAGE sql AS $$
    INSERT INTO notificacion (id_pedido, tipo_evento, mensaje, id_cliente, id_empleado, rol_destino)
    VALUES (p_pedido, p_tipo, left(p_mensaje, 255), p_cliente, p_empleado, p_rol)
$$;

-- =====================================================================================
-- PEDIDO: alta (RN-002, RN-008, origen y estado inicial)
-- =====================================================================================
CREATE FUNCTION fn_pedido_alta() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    s sucursal%ROWTYPE;
    c codigo_descuento%ROWTYPE;
    v_esperado numeric;
BEGIN
    SELECT * INTO s FROM sucursal WHERE id_sucursal = NEW.id_sucursal;
    IF NOT s.activa THEN
        PERFORM fn_error('La sucursal no está activa.');
    END IF;
    -- RN-002: horario de la sucursal, con la hora oficial (real o simulada).
    IF NOT (fn_ahora()::time >= s.hora_apertura AND fn_ahora()::time < s.hora_cierre) THEN
        PERFORM fn_error(format('RN-002: los pedidos se reciben de %s a %s h.',
                                to_char(s.hora_apertura, 'HH24:MI'), to_char(s.hora_cierre, 'HH24:MI')));
    END IF;

    -- Estado inicial según quién registra el pedido.
    IF NEW.origen = 'APP' THEN
        PERFORM fn_exigir_rol(ARRAY['Cliente'], 'CU-001');
        NEW.estado := 'Por Confirmar';
        NEW.id_cajero := NULL;
        NEW.id_cocinero := NULL;
        NEW.tiempo_estimado_min := NULL;
        NEW.codigo_entrega := NULL;
        NEW.fecha_preparacion := NULL;
    ELSE
        -- Por teléfono o en sucursal, el cajero lo confirma al registrarlo.
        PERFORM fn_exigir_rol(ARRAY['Cajero', 'Gerente'], 'CU-001');
        NEW.estado := 'En Preparación';
        NEW.fecha_preparacion := fn_ahora();
        NEW.codigo_entrega := coalesce(NEW.codigo_entrega, lpad((floor(random() * 10000))::int::text, 4, '0'));
    END IF;
    NEW.fecha_registro := fn_ahora();
    NEW.fecha_listo := NULL;
    NEW.fecha_en_camino := NULL;
    NEW.fecha_entrega := NULL;
    NEW.cancelacion_solicitada_por := NULL;
    NEW.fecha_solicitud_cancelacion := NULL;
    NEW.cancelacion_confirmada_por_telefono := false;
    NEW.motivo_cancelacion := NULL;

    -- RN-008: sin código no hay descuento; con código, el descuento debe ser exactamente el del código.
    IF NEW.id_codigo_descuento IS NULL THEN
        IF NEW.descuento <> 0 THEN
            PERFORM fn_error('RN-008: no se aplican descuentos manuales; se requiere un código del gerente.');
        END IF;
    ELSE
        SELECT * INTO c FROM codigo_descuento WHERE id_codigo = NEW.id_codigo_descuento FOR UPDATE;
        IF c.usado THEN
            PERFORM fn_error('RN-008: el código de descuento ya fue usado.');
        ELSIF NOT (fn_ahora() >= c.vigencia_inicio AND fn_ahora() < c.vigencia_fin) THEN
            PERFORM fn_error('RN-008: el código de descuento no está vigente.');
        END IF;
        v_esperado := CASE c.tipo WHEN 'PORCENTAJE' THEN round(NEW.subtotal * c.valor / 100, 2)
                                  ELSE least(c.valor, NEW.subtotal) END;
        IF NEW.descuento <> v_esperado THEN
            PERFORM fn_error(format('RN-008: el descuento debe ser %s según el código.', v_esperado));
        END IF;
        UPDATE codigo_descuento SET usado = true WHERE id_codigo = c.id_codigo;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_pedido_alta BEFORE INSERT ON pedido
    FOR EACH ROW EXECUTE FUNCTION fn_pedido_alta();

-- =====================================================================================
-- PEDIDO: cambios (máquina de estados, RN-005, RN-013, datos protegidos)
-- =====================================================================================
CREATE FUNCTION fn_pedido_cambio() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_rol text := fn_rol();
    v_transicion text := OLD.estado || ' -> ' || NEW.estado;
BEGIN
    -- Datos que no cambian una vez registrado el pedido.
    IF (NEW.folio, NEW.id_sucursal, NEW.id_cliente, NEW.origen, NEW.subtotal, NEW.descuento, NEW.total,
        NEW.forma_pago, NEW.monto_recibido, NEW.cambio, NEW.id_codigo_descuento, NEW.fecha_registro,
        NEW.direccion_entrega, NEW.referencia_pago)
       IS DISTINCT FROM
       (OLD.folio, OLD.id_sucursal, OLD.id_cliente, OLD.origen, OLD.subtotal, OLD.descuento, OLD.total,
        OLD.forma_pago, OLD.monto_recibido, OLD.cambio, OLD.id_codigo_descuento, OLD.fecha_registro,
        OLD.direccion_entrega, OLD.referencia_pago) THEN
        PERFORM fn_error('Los datos de un pedido registrado (cliente, productos, montos y pago) no se modifican.');
    END IF;

    -- Las fechas de cada estado las pone la base de datos, no la app.
    NEW.fecha_preparacion := OLD.fecha_preparacion;
    NEW.fecha_listo := OLD.fecha_listo;
    NEW.fecha_en_camino := OLD.fecha_en_camino;
    NEW.fecha_entrega := OLD.fecha_entrega;

    -- Cajero, cocinero, tiempo y código de entrega se fijan solo al confirmar o rechazar.
    IF OLD.estado <> 'Por Confirmar'
       AND (NEW.id_cajero, NEW.id_cocinero, NEW.tiempo_estimado_min, NEW.codigo_entrega)
           IS DISTINCT FROM (OLD.id_cajero, OLD.id_cocinero, OLD.tiempo_estimado_min, OLD.codigo_entrega) THEN
        PERFORM fn_error('El cajero, el cocinero y el tiempo estimado se asignan al confirmar el pedido.');
    END IF;

    IF NEW.estado = OLD.estado THEN
        -- ---- Solicitud de cancelación de acuerdo mutuo (RN-005, decisión 7) ----
        IF NEW.cancelacion_solicitada_por IS DISTINCT FROM OLD.cancelacion_solicitada_por THEN
            IF OLD.estado <> 'En Preparación' THEN
                PERFORM fn_error('RN-005: solo se puede solicitar la cancelación de un pedido "En Preparación".');
            END IF;
            IF NEW.cancelacion_solicitada_por IS NOT NULL THEN
                IF OLD.cancelacion_solicitada_por IS NOT NULL THEN
                    PERFORM fn_error('RN-005: ya hay una solicitud de cancelación pendiente.');
                ELSIF NOT ((NEW.cancelacion_solicitada_por = 'CLIENTE' AND v_rol = 'Cliente')
                        OR (NEW.cancelacion_solicitada_por = 'CAJERO' AND v_rol = 'Cajero')) THEN
                    PERFORM fn_error('RN-005: la solicitud de cancelación debe hacerla la parte que la pide.');
                ELSIF btrim(coalesce(NEW.motivo_cancelacion, '')) = '' THEN
                    PERFORM fn_error('RN-005: la solicitud de cancelación requiere un motivo.');
                END IF;
                NEW.fecha_solicitud_cancelacion := fn_ahora();
            ELSE
                -- La otra parte (o el gerente) rechaza la solicitud: el pedido sigue.
                IF NOT ((OLD.cancelacion_solicitada_por = 'CLIENTE' AND v_rol IN ('Cajero', 'Gerente'))
                     OR (OLD.cancelacion_solicitada_por = 'CAJERO' AND v_rol IN ('Cliente', 'Gerente'))) THEN
                    PERFORM fn_error('RN-005: solo la otra parte puede rechazar la solicitud de cancelación.');
                END IF;
                NEW.fecha_solicitud_cancelacion := NULL;
                NEW.motivo_cancelacion := NULL;
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    -- ---- Máquina de estados ----
    CASE v_transicion
    WHEN 'Por Confirmar -> En Preparación' THEN
        PERFORM fn_exigir_rol(ARRAY['Cajero', 'Gerente'], 'CU-001');
        NEW.fecha_preparacion := fn_ahora();
        NEW.codigo_entrega := coalesce(NEW.codigo_entrega, lpad((floor(random() * 10000))::int::text, 4, '0'));

    WHEN 'Por Confirmar -> Rechazado' THEN
        PERFORM fn_exigir_rol(ARRAY['Cajero', 'Gerente'], 'CU-001');

    WHEN 'Por Confirmar -> Cancelado' THEN
        -- El cliente retira su pedido antes de que un cajero lo tome.
        PERFORM fn_exigir_rol(ARRAY['Cliente', 'Gerente'], 'RN-005');

    WHEN 'En Preparación -> Listo para Entrega' THEN
        PERFORM fn_exigir_rol(ARRAY['Cajero', 'Gerente'], 'CU-002');
        IF OLD.cancelacion_solicitada_por IS NOT NULL THEN
            PERFORM fn_error('RN-005: hay una solicitud de cancelación pendiente; resuélvela primero.');
        END IF;
        NEW.fecha_listo := fn_ahora();

    WHEN 'En Preparación -> Cancelado' THEN
        -- RN-005: acuerdo mutuo cliente–cajero, confirmación telefónica, o el gerente.
        IF v_rol = 'Gerente' THEN
            NULL;
        ELSIF OLD.cancelacion_solicitada_por = 'CLIENTE' AND v_rol = 'Cajero' THEN
            NULL;
        ELSIF OLD.cancelacion_solicitada_por = 'CAJERO' AND v_rol = 'Cliente' THEN
            NULL;
        ELSIF v_rol = 'Cajero' AND OLD.origen IN ('TELEFONO', 'SUCURSAL')
              AND NEW.cancelacion_confirmada_por_telefono THEN
            NEW.cancelacion_solicitada_por := 'CAJERO';
            NEW.fecha_solicitud_cancelacion := fn_ahora();
        ELSE
            PERFORM fn_error('RN-005: cancelar un pedido "En Preparación" requiere el acuerdo del cliente y del cajero.');
        END IF;

    WHEN 'Listo para Entrega -> En Camino' THEN
        PERFORM fn_exigir_rol(ARRAY['Repartidor'], 'CU-002');
        IF NOT EXISTS (SELECT 1 FROM asignacion_entrega
                       WHERE id_pedido = NEW.id_pedido AND estado = 'CONFIRMADA') THEN
            PERFORM fn_error('CU-002: el pedido sale "En Camino" cuando un repartidor acepta la asignación.');
        END IF;
        NEW.fecha_en_camino := fn_ahora();

    WHEN 'Listo para Entrega -> Cancelado', 'En Camino -> Cancelado' THEN
        PERFORM fn_exigir_rol(ARRAY['Gerente'], 'RN-005');

    WHEN 'En Camino -> Entregado' THEN
        PERFORM fn_exigir_rol(ARRAY['Repartidor'], 'RN-013');
        IF NOT EXISTS (SELECT 1 FROM asignacion_entrega
                       WHERE id_pedido = NEW.id_pedido AND estado = 'ENTREGADA') THEN
            PERFORM fn_error('RN-013: la entrega requiere la confirmación del cliente y del repartidor.');
        END IF;
        NEW.fecha_entrega := fn_ahora();

    ELSE
        PERFORM fn_error(format('Cambio de estado no permitido: %s.', v_transicion));
    END CASE;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_pedido_cambio BEFORE UPDATE ON pedido
    FOR EACH ROW EXECUTE FUNCTION fn_pedido_cambio();

-- Cajero y cocinero válidos y de la sucursal del pedido (decisión 10).
CREATE FUNCTION fn_pedido_personal() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.id_cajero IS NOT NULL AND (TG_OP = 'INSERT' OR NEW.id_cajero IS DISTINCT FROM OLD.id_cajero) THEN
        PERFORM fn_exigir_empleado(NEW.id_cajero, ARRAY['Cajero', 'Gerente'], NEW.id_sucursal, 'cajero');
    END IF;
    IF NEW.id_cocinero IS NOT NULL AND (TG_OP = 'INSERT' OR NEW.id_cocinero IS DISTINCT FROM OLD.id_cocinero) THEN
        PERFORM fn_exigir_empleado(NEW.id_cocinero, ARRAY['Cocinero'], NEW.id_sucursal, 'cocinero');
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_pedido_personal BEFORE INSERT OR UPDATE ON pedido
    FOR EACH ROW EXECUTE FUNCTION fn_pedido_personal();

-- Los pedidos no se borran: se cancelan (trazabilidad, RN-019).
CREATE FUNCTION fn_no_borrar() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_error(format('Los registros de %s no se borran.', TG_TABLE_NAME));
    RETURN NULL;
END $$;

CREATE TRIGGER trg_pedido_no_borrar BEFORE DELETE ON pedido
    FOR EACH ROW EXECUTE FUNCTION fn_no_borrar();

-- Efectos de cada cambio de estado: notificaciones (CU-007) y asignaciones canceladas.
CREATE FUNCTION fn_pedido_despues() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.origen = 'APP' THEN
            PERFORM fn_notificar(NEW.id_pedido, 'CAMBIO_ESTADO',
                format('Nuevo pedido %s por confirmar.', NEW.folio), p_rol => 'Cajero');
        END IF;
        RETURN NULL;
    END IF;

    -- Solicitudes de cancelación: se avisa a la otra parte.
    IF NEW.estado = OLD.estado AND NEW.cancelacion_solicitada_por IS DISTINCT FROM OLD.cancelacion_solicitada_por THEN
        IF NEW.cancelacion_solicitada_por = 'CLIENTE' THEN
            PERFORM fn_notificar(NEW.id_pedido, 'SOLICITUD_CANCELACION',
                format('El cliente pide cancelar el pedido %s: %s', NEW.folio, NEW.motivo_cancelacion), p_rol => 'Cajero');
        ELSIF NEW.cancelacion_solicitada_por = 'CAJERO' THEN
            PERFORM fn_notificar(NEW.id_pedido, 'SOLICITUD_CANCELACION',
                format('La sucursal pide cancelar tu pedido %s: %s. ¿Estás de acuerdo?', NEW.folio, NEW.motivo_cancelacion),
                p_cliente => NEW.id_cliente);
        ELSE
            PERFORM fn_notificar(NEW.id_pedido, 'SOLICITUD_CANCELACION',
                format('La solicitud de cancelación del pedido %s fue rechazada; el pedido continúa.', NEW.folio),
                p_cliente => NEW.id_cliente);
        END IF;
    END IF;

    IF NEW.estado IS DISTINCT FROM OLD.estado THEN
        PERFORM fn_notificar(NEW.id_pedido, 'CAMBIO_ESTADO', CASE NEW.estado
            WHEN 'En Preparación' THEN format('Tu pedido %s fue confirmado. Tiempo estimado: %s min.', NEW.folio, NEW.tiempo_estimado_min)
            WHEN 'Rechazado' THEN format('Tu pedido %s no pudo aceptarse: %s', NEW.folio, NEW.motivo_cancelacion)
            WHEN 'Listo para Entrega' THEN format('Tu pedido %s está listo y espera repartidor.', NEW.folio)
            WHEN 'En Camino' THEN format('Tu pedido %s va en camino. Tu código de entrega es %s.', NEW.folio, NEW.codigo_entrega)
            WHEN 'Entregado' THEN format('Tu pedido %s fue entregado. ¡Buen provecho!', NEW.folio)
            WHEN 'Cancelado' THEN format('Tu pedido %s fue cancelado: %s', NEW.folio, NEW.motivo_cancelacion)
            END, p_cliente => NEW.id_cliente);
        IF NEW.estado IN ('En Camino', 'Cancelado') AND OLD.estado <> 'Por Confirmar' THEN
            PERFORM fn_notificar(NEW.id_pedido, 'CAMBIO_ESTADO',
                format('El pedido %s cambió a "%s".', NEW.folio, NEW.estado), p_rol => 'Cajero');
        END IF;
        IF NEW.estado = 'Cancelado' THEN
            UPDATE asignacion_entrega SET estado = 'CANCELADA'
             WHERE id_pedido = NEW.id_pedido AND estado IN ('PENDIENTE', 'CONFIRMADA');
        END IF;
    END IF;
    RETURN NULL;
END $$;

CREATE TRIGGER trg_pedido_despues AFTER INSERT OR UPDATE ON pedido
    FOR EACH ROW EXECUTE FUNCTION fn_pedido_despues();

-- =====================================================================================
-- DETALLE DEL PEDIDO: precio de lista (RN-007), disponibilidad, RN-003
-- =====================================================================================
CREATE FUNCTION fn_detalle_alta() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p producto%ROWTYPE;
BEGIN
    SELECT * INTO p FROM producto WHERE id_producto = NEW.id_producto;
    IF NOT p.activo OR NOT p.disponible THEN
        PERFORM fn_error(format('El producto "%s" no está disponible.', p.nombre));
    END IF;
    IF NEW.precio_unitario <> p.precio THEN
        PERFORM fn_error(format('RN-007: el precio de "%s" es %s; no se puede cambiar al registrar el pedido.',
                                p.nombre, p.precio));
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_detalle_alta BEFORE INSERT ON detalle_pedido
    FOR EACH ROW EXECUTE FUNCTION fn_detalle_alta();

CREATE FUNCTION fn_detalle_inmutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_error('Los productos de un pedido registrado no se modifican.');
    RETURN NULL;
END $$;

CREATE TRIGGER trg_detalle_inmutable BEFORE UPDATE OR DELETE ON detalle_pedido
    FOR EACH ROW EXECUTE FUNCTION fn_detalle_inmutable();

-- Se revisa al hacer COMMIT (DEFERRABLE INITIALLY DEFERRED): el pedido se inserta primero
-- y sus productos después, así que antes del COMMIT el pedido todavía no está completo.
CREATE FUNCTION fn_pedido_verificar_detalle() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_subtotal numeric;
    v_renglones integer;
    v_suma numeric;
BEGIN
    SELECT subtotal INTO v_subtotal FROM pedido WHERE id_pedido = NEW.id_pedido;
    SELECT count(*), coalesce(sum(subtotal), 0) INTO v_renglones, v_suma
      FROM detalle_pedido WHERE id_pedido = NEW.id_pedido;
    IF v_renglones = 0 THEN
        PERFORM fn_error('El pedido no tiene productos.');
    ELSIF v_renglones > 10 THEN
        PERFORM fn_error(format('RN-003: un pedido admite máximo 10 productos distintos (tiene %s).', v_renglones));
    ELSIF v_suma <> v_subtotal THEN
        PERFORM fn_error(format('El subtotal del pedido (%s) no coincide con la suma de sus productos (%s).',
                                v_subtotal, v_suma));
    END IF;
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER trg_pedido_verificar_detalle AFTER INSERT ON pedido
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION fn_pedido_verificar_detalle();
CREATE CONSTRAINT TRIGGER trg_detalle_verificar_pedido AFTER INSERT ON detalle_pedido
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION fn_pedido_verificar_detalle();

-- =====================================================================================
-- PRODUCTO: catálogo y precios solo los administra el gerente (RN-007)
-- =====================================================================================
CREATE FUNCTION fn_producto_gerente() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.precio IS DISTINCT FROM OLD.precio THEN
        PERFORM fn_exigir_rol(ARRAY['Gerente'], 'RN-007 (solo el gerente edita precios)');
    ELSE
        PERFORM fn_exigir_rol(ARRAY['Gerente'], 'RN-007 (catálogo del gerente)');
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_producto_gerente BEFORE INSERT OR UPDATE ON producto
    FOR EACH ROW EXECUTE FUNCTION fn_producto_gerente();

-- =====================================================================================
-- CÓDIGO DE DESCUENTO: lo emite un gerente (RN-008)
-- =====================================================================================
CREATE FUNCTION fn_descuento_validar() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        PERFORM fn_exigir_rol(ARRAY['Gerente'], 'RN-008');
        PERFORM fn_exigir_empleado(NEW.id_gerente, ARRAY['Gerente'], NULL, 'emisor del código');
        NEW.usado := false;
    ELSIF (NEW.codigo, NEW.id_gerente, NEW.tipo, NEW.valor) IS DISTINCT FROM
          (OLD.codigo, OLD.id_gerente, OLD.tipo, OLD.valor) THEN
        PERFORM fn_error('RN-008: un código emitido no se modifica; emite uno nuevo.');
    ELSIF OLD.usado AND NOT NEW.usado THEN
        PERFORM fn_error('RN-008: un código usado no puede volver a usarse.');
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_descuento_validar BEFORE INSERT OR UPDATE ON codigo_descuento
    FOR EACH ROW EXECUTE FUNCTION fn_descuento_validar();

-- =====================================================================================
-- ASIGNACIÓN DE REPARTIDOR (CU-002, RN-011) Y ENTREGA EN DOS PASOS (RN-013)
-- =====================================================================================
CREATE FUNCTION fn_asignacion_validar() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    p pedido%ROWTYPE;
    v_activas integer;
    r empleado%ROWTYPE;
BEGIN
    SELECT * INTO p FROM pedido WHERE id_pedido = NEW.id_pedido;

    IF TG_OP = 'INSERT' THEN
        IF p.estado <> 'Listo para Entrega' THEN
            PERFORM fn_error('CU-002: solo se asignan pedidos "Listo para Entrega".');
        END IF;
        -- Se bloquea la fila del repartidor: si dos asignaciones llegan al mismo tiempo,
        -- la segunda espera a la primera y ve su conteo actualizado (RN-011).
        SELECT * INTO r FROM empleado WHERE id_empleado = NEW.id_repartidor FOR UPDATE;
        PERFORM fn_exigir_empleado(NEW.id_repartidor, ARRAY['Repartidor'], p.id_sucursal, 'repartidor');
        IF NOT r.disponible OR r.bloqueado THEN
            PERFORM fn_error('CU-002: el repartidor no está disponible.');
        END IF;
        SELECT count(*) INTO v_activas FROM asignacion_entrega
         WHERE id_repartidor = NEW.id_repartidor AND estado IN ('PENDIENTE', 'CONFIRMADA');
        IF v_activas >= 2 THEN
            PERFORM fn_error('RN-011: el repartidor ya tiene 2 pedidos activos.');
        END IF;
        IF NEW.tipo = 'MANUAL' THEN
            PERFORM fn_exigir_rol(ARRAY['Gerente'], 'CU-002 (asignación manual)');
            PERFORM fn_exigir_empleado(NEW.id_gerente, ARRAY['Gerente'], p.id_sucursal, 'gerente');
        END IF;
        NEW.estado := 'PENDIENTE';
        NEW.fecha_asignacion := fn_ahora();
        NEW.fecha_confirmacion := NULL;
        NEW.fecha_limite_entrega := NULL;
        NEW.firma_digital := NULL;
        NEW.codigo_confirmacion := NULL;
        NEW.fecha_confirmacion_cliente := NULL;
        NEW.fecha_hora_entrega := NULL;
        RETURN NEW;
    END IF;

    -- UPDATE
    IF (NEW.id_pedido, NEW.id_repartidor, NEW.id_gerente, NEW.tipo, NEW.fecha_asignacion)
       IS DISTINCT FROM (OLD.id_pedido, OLD.id_repartidor, OLD.id_gerente, OLD.tipo, OLD.fecha_asignacion) THEN
        PERFORM fn_error('Los datos de una asignación no se modifican; se cancela y se crea otra.');
    END IF;
    NEW.fecha_confirmacion := OLD.fecha_confirmacion;
    NEW.fecha_limite_entrega := OLD.fecha_limite_entrega;
    NEW.fecha_hora_entrega := OLD.fecha_hora_entrega;

    -- Paso 1 de la entrega: confirma el cliente (firma o código). Solo una vez.
    IF (NEW.firma_digital, NEW.codigo_confirmacion) IS DISTINCT FROM (OLD.firma_digital, OLD.codigo_confirmacion) THEN
        IF OLD.fecha_confirmacion_cliente IS NOT NULL THEN
            PERFORM fn_error('RN-013: el cliente ya confirmó la recepción.');
        ELSIF OLD.estado <> 'CONFIRMADA' OR p.estado <> 'En Camino' THEN
            PERFORM fn_error('RN-013: el cliente confirma cuando el pedido está "En Camino".');
        END IF;
        PERFORM fn_exigir_rol(ARRAY['Repartidor'], 'RN-013');
        IF NEW.codigo_confirmacion IS NOT NULL AND NEW.codigo_confirmacion <> p.codigo_entrega THEN
            PERFORM fn_error('RN-013: el código de confirmación no coincide con el del cliente.');
        END IF;
        NEW.fecha_confirmacion_cliente := fn_ahora();
    ELSE
        NEW.fecha_confirmacion_cliente := OLD.fecha_confirmacion_cliente;
    END IF;

    IF NEW.estado IS DISTINCT FROM OLD.estado THEN
        CASE OLD.estado || ' -> ' || NEW.estado
        WHEN 'PENDIENTE -> CONFIRMADA' THEN
            PERFORM fn_exigir_rol(ARRAY['Repartidor'], 'CU-002');
            IF fn_id_empleado() IS DISTINCT FROM NEW.id_repartidor THEN
                PERFORM fn_error('CU-002: solo el repartidor asignado puede aceptar.');
            END IF;
            NEW.fecha_confirmacion := fn_ahora();
            NEW.fecha_limite_entrega := fn_ahora() + interval '90 minutes';
        WHEN 'PENDIENTE -> EXPIRADA' THEN
            -- CU-002 FA-2: vence a los 5 minutos sin aceptar (o el gerente la retira).
            IF fn_ahora() - OLD.fecha_asignacion < interval '5 minutes' AND fn_rol() <> 'Gerente' THEN
                PERFORM fn_error('CU-002: la asignación todavía no vence (5 min).');
            END IF;
        WHEN 'PENDIENTE -> CANCELADA', 'CONFIRMADA -> CANCELADA' THEN
            -- La cancela el gerente (reasignación) o la cancelación del pedido.
            IF fn_rol() <> 'Gerente' AND p.estado <> 'Cancelado' THEN
                PERFORM fn_error('CU-002: solo el gerente cancela una asignación.');
            END IF;
        WHEN 'CONFIRMADA -> ENTREGADA' THEN
            -- Paso 2 de la entrega: confirma el repartidor con su sesión.
            PERFORM fn_exigir_rol(ARRAY['Repartidor'], 'RN-013');
            IF fn_id_empleado() IS DISTINCT FROM NEW.id_repartidor THEN
                PERFORM fn_error('RN-013: solo el repartidor asignado confirma la entrega.');
            END IF;
            NEW.fecha_hora_entrega := fn_ahora();
        ELSE
            PERFORM fn_error(format('Cambio de asignación no permitido: %s -> %s.', OLD.estado, NEW.estado));
        END CASE;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_asignacion_validar BEFORE INSERT OR UPDATE ON asignacion_entrega
    FOR EACH ROW EXECUTE FUNCTION fn_asignacion_validar();

-- El pedido sigue a su asignación: aceptada -> "En Camino"; entregada -> "Entregado".
CREATE FUNCTION fn_asignacion_despues() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_folio text;
BEGIN
    SELECT folio INTO v_folio FROM pedido WHERE id_pedido = NEW.id_pedido;
    IF TG_OP = 'INSERT' THEN
        PERFORM fn_notificar(NEW.id_pedido, 'ASIGNACION',
            format('Se te asignó el pedido %s. Acéptalo en los próximos 5 minutos.', v_folio),
            p_empleado => NEW.id_repartidor);
    ELSIF NEW.estado IS DISTINCT FROM OLD.estado THEN
        CASE NEW.estado
        WHEN 'CONFIRMADA' THEN
            UPDATE pedido SET estado = 'En Camino' WHERE id_pedido = NEW.id_pedido;
        WHEN 'ENTREGADA' THEN
            UPDATE pedido SET estado = 'Entregado' WHERE id_pedido = NEW.id_pedido;
        WHEN 'EXPIRADA' THEN
            PERFORM fn_notificar(NEW.id_pedido, 'SIN_REPARTIDOR',
                format('El repartidor no aceptó el pedido %s a tiempo; se debe reasignar.', v_folio),
                p_rol => 'Gerente');
        ELSE NULL;
        END CASE;
    END IF;
    RETURN NULL;
END $$;

CREATE TRIGGER trg_asignacion_despues AFTER INSERT OR UPDATE ON asignacion_entrega
    FOR EACH ROW EXECUTE FUNCTION fn_asignacion_despues();

-- =====================================================================================
-- DEVOLUCIÓN: solo el gerente y dentro de 2 h tras la entrega (RN-015)
-- =====================================================================================
CREATE FUNCTION fn_devolucion_validar() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p pedido%ROWTYPE;
BEGIN
    PERFORM fn_exigir_rol(ARRAY['Gerente'], 'RN-015');
    SELECT * INTO p FROM pedido WHERE id_pedido = NEW.id_pedido;
    PERFORM fn_exigir_empleado(NEW.id_gerente, ARRAY['Gerente'], p.id_sucursal, 'gerente');
    IF p.estado <> 'Entregado' THEN
        PERFORM fn_error('RN-015: solo se registran devoluciones de pedidos entregados.');
    END IF;
    NEW.fecha_hora := fn_ahora();
    IF NEW.fecha_hora > p.fecha_entrega + interval '2 hours' THEN
        PERFORM fn_error(format('RN-015: el plazo de devolución venció (entregado el %s).',
                                to_char(p.fecha_entrega, 'DD/MM/YYYY HH24:MI')));
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_devolucion_validar BEFORE INSERT ON devolucion
    FOR EACH ROW EXECUTE FUNCTION fn_devolucion_validar();
CREATE TRIGGER trg_devolucion_no_borrar BEFORE UPDATE OR DELETE ON devolucion
    FOR EACH ROW EXECUTE FUNCTION fn_no_borrar();

-- =====================================================================================
-- USUARIOS: sesión única (RN-017) y bloqueo a los 3 intentos (RN-018)
-- =====================================================================================
CREATE FUNCTION fn_sesion_unica() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE e empleado%ROWTYPE;
BEGIN
    SELECT * INTO e FROM empleado WHERE id_empleado = NEW.id_empleado;
    IF e.username IS NULL THEN
        PERFORM fn_error('RN-016: este puesto no inicia sesión.');
    ELSIF e.bloqueado THEN
        PERFORM fn_error('RN-018: la cuenta está bloqueada.');
    ELSIF NOT e.activo THEN
        PERFORM fn_error('La cuenta está dada de baja.');
    END IF;
    -- RN-017: al entrar desde otro dispositivo, la sesión anterior se cierra.
    UPDATE sesion SET activa = false, fecha_fin = fn_ahora()
     WHERE id_empleado = NEW.id_empleado AND activa;
    NEW.activa := true;
    NEW.fecha_inicio := fn_ahora();
    NEW.fecha_fin := NULL;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_sesion_unica BEFORE INSERT ON sesion
    FOR EACH ROW EXECUTE FUNCTION fn_sesion_unica();

CREATE FUNCTION fn_empleado_bloqueo() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    -- El orden importa: primero el desbloqueo (que reinicia el contador) y después la regla
    -- de los 3 intentos; al revés, una cuenta con 3 intentos se volvería a bloquear al instante.
    IF OLD.bloqueado AND NOT NEW.bloqueado THEN
        NEW.intentos_fallidos := 0;
    END IF;
    IF NEW.intentos_fallidos >= 3 THEN
        NEW.bloqueado := true;
    END IF;
    IF NEW.bloqueado AND NOT OLD.bloqueado THEN
        UPDATE sesion SET activa = false, fecha_fin = fn_ahora() WHERE id_empleado = NEW.id_empleado AND activa;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_empleado_bloqueo BEFORE UPDATE ON empleado
    FOR EACH ROW EXECUTE FUNCTION fn_empleado_bloqueo();

-- =====================================================================================
-- ALERTAS DE TIEMPO (RN-006, RN-014) Y VENCIMIENTO DE ASIGNACIONES (CU-002 FA-2)
-- La app la llama en cada ciclo de actualización automática; no duplica alertas.
-- =====================================================================================
CREATE FUNCTION fn_generar_alertas() RETURNS integer LANGUAGE plpgsql AS $$
DECLARE
    v_total integer := 0;
    v_filas integer;
BEGIN
    INSERT INTO notificacion (id_pedido, rol_destino, tipo_evento, mensaje)
    SELECT id_pedido, 'Gerente', 'ALERTA_45',
           format('RN-006: el pedido %s lleva más de 45 min en preparación.', folio)
      FROM pedido
     WHERE estado = 'En Preparación' AND fn_ahora() - fecha_preparacion > interval '45 minutes'
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS v_filas = ROW_COUNT;
    v_total := v_total + v_filas;

    INSERT INTO notificacion (id_pedido, rol_destino, tipo_evento, mensaje)
    SELECT p.id_pedido, r.rol, 'ALERTA_90',
           format('RN-014: el pedido %s lleva más de 90 min en camino.', p.folio)
      FROM pedido p CROSS JOIN (VALUES ('Gerente'), ('Cajero')) AS r(rol)
     WHERE p.estado = 'En Camino' AND fn_ahora() - p.fecha_en_camino > interval '90 minutes'
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS v_filas = ROW_COUNT;
    v_total := v_total + v_filas;

    UPDATE asignacion_entrega SET estado = 'EXPIRADA'
     WHERE estado = 'PENDIENTE' AND fn_ahora() - fecha_asignacion >= interval '5 minutes';
    RETURN v_total;
END $$;
