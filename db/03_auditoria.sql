-- =====================================================================================
-- GPizza · 03_auditoria.sql
-- RN-019: cada acción relevante queda registrada automáticamente con usuario, fecha y hora,
-- y el historial no se puede editar ni borrar.
-- =====================================================================================
SET client_min_messages = warning;

-- Registro genérico. Parámetros del trigger: TG_ARGV[0] = columna llave;
-- TG_ARGV[1..] = columnas que NO se copian a la bitácora (contraseñas, firmas, datos cifrados).
CREATE FUNCTION fn_auditar() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_excluir text[] := TG_ARGV[1:];
    v_nuevo   jsonb := to_jsonb(NEW) - v_excluir;
    v_viejo   jsonb;
    v_detalle jsonb;
    v_accion  text;
    v_usuario integer := fn_id_empleado();
BEGIN
    IF TG_OP = 'INSERT' THEN
        v_accion := 'CREAR';
        v_detalle := jsonb_build_object('nuevo', v_nuevo);
    ELSE
        v_viejo := to_jsonb(OLD) - v_excluir;
        -- Solo los campos que cambiaron: {"campo": {"antes": ..., "despues": ...}}
        SELECT jsonb_object_agg(n.key, jsonb_build_object('antes', v_viejo -> n.key, 'despues', n.value))
          INTO v_detalle
          FROM jsonb_each(v_nuevo) AS n
         WHERE n.value IS DISTINCT FROM v_viejo -> n.key;
        IF v_detalle IS NULL THEN
            RETURN NULL;  -- no cambió nada que valga la pena registrar
        END IF;
        v_accion := 'MODIFICAR';
    END IF;

    -- Nombres de acción más claros para los casos importantes.
    IF TG_TABLE_NAME = 'pedido' AND v_nuevo ->> 'estado' = 'Cancelado'
       AND v_viejo ->> 'estado' IS DISTINCT FROM 'Cancelado' THEN
        v_accion := 'CANCELAR';
    ELSIF TG_TABLE_NAME = 'sesion' THEN
        v_accion := CASE WHEN TG_OP = 'INSERT' THEN 'LOGIN' ELSE 'LOGOUT' END;
        v_usuario := (v_nuevo ->> 'id_empleado')::integer;
    ELSIF TG_TABLE_NAME = 'empleado' AND TG_OP = 'UPDATE' THEN
        IF (v_nuevo ->> 'bloqueado')::boolean AND NOT (v_viejo ->> 'bloqueado')::boolean THEN
            v_accion := 'BLOQUEO';
        ELSIF (v_nuevo ->> 'intentos_fallidos')::int > (v_viejo ->> 'intentos_fallidos')::int THEN
            v_accion := 'LOGIN_FALLIDO';
        END IF;
    END IF;

    INSERT INTO auditoria (id_empleado, accion, entidad, id_entidad, detalle, fecha_hora)
    VALUES (v_usuario, v_accion, TG_TABLE_NAME, (v_nuevo ->> TG_ARGV[0])::integer, v_detalle, fn_ahora());
    RETURN NULL;
END $$;

CREATE TRIGGER trg_auditar AFTER INSERT OR UPDATE ON pedido
    FOR EACH ROW EXECUTE FUNCTION fn_auditar('id_pedido', 'direccion_entrega', 'referencia_pago');
CREATE TRIGGER trg_auditar AFTER INSERT OR UPDATE ON producto
    FOR EACH ROW EXECUTE FUNCTION fn_auditar('id_producto');
CREATE TRIGGER trg_auditar AFTER INSERT OR UPDATE ON empleado
    FOR EACH ROW EXECUTE FUNCTION fn_auditar('id_empleado', 'password_hash', 'latitud_actual', 'longitud_actual');
CREATE TRIGGER trg_auditar AFTER INSERT OR UPDATE ON cliente
    FOR EACH ROW EXECUTE FUNCTION fn_auditar('id_cliente', 'direccion');
CREATE TRIGGER trg_auditar AFTER INSERT OR UPDATE ON asignacion_entrega
    FOR EACH ROW EXECUTE FUNCTION fn_auditar('id_asignacion', 'firma_digital');
CREATE TRIGGER trg_auditar AFTER INSERT ON devolucion
    FOR EACH ROW EXECUTE FUNCTION fn_auditar('id_devolucion');
CREATE TRIGGER trg_auditar AFTER INSERT OR UPDATE ON codigo_descuento
    FOR EACH ROW EXECUTE FUNCTION fn_auditar('id_codigo');
CREATE TRIGGER trg_auditar AFTER INSERT OR UPDATE ON sesion
    FOR EACH ROW EXECUTE FUNCTION fn_auditar('id_sesion', 'token_hash');

-- -------------------------------------------------------------------------------------
-- Inmutabilidad: dos candados.
-- 1) Trigger: cualquier UPDATE, DELETE o TRUNCATE sobre la bitácora lanza un error.
-- 2) Permisos: se le quitan esos permisos al usuario de la app (aunque sea el dueño).
-- -------------------------------------------------------------------------------------
CREATE FUNCTION fn_auditoria_inmutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM fn_error('RN-019: la bitácora de auditoría es inmutable; solo admite nuevos registros.');
    RETURN NULL;
END $$;

CREATE TRIGGER trg_auditoria_inmutable BEFORE UPDATE OR DELETE ON auditoria
    FOR EACH ROW EXECUTE FUNCTION fn_auditoria_inmutable();
CREATE TRIGGER trg_auditoria_sin_truncate BEFORE TRUNCATE ON auditoria
    FOR EACH STATEMENT EXECUTE FUNCTION fn_auditoria_inmutable();

REVOKE UPDATE, DELETE, TRUNCATE ON auditoria FROM PUBLIC, CURRENT_USER;
