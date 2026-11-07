-- =====================================================================================
-- GPS · ejemplo_nueva_sucursal.sql  (RNF-005 Escalabilidad)
--
-- Una sucursal nueva se agrega SOLO CON DATOS: no se modifica el código ni se reinicia la app.
-- Su horario, su radio de cobertura y su personal también son datos.
--
-- Uso:  psql -U gpizza_user -d gpizza -f db/ejemplo_nueva_sucursal.sql
--
-- El gerente necesita una contraseña con hash Argon2, que se genera en Python; por eso, para
-- crear la sucursal CON su gerente, lo recomendable es el comando equivalente:
--   flask --app gpizza nueva-sucursal --nombre "Boca del Río" --direccion "Blvd. Ávila Camacho 2000" \
--         --ciudad "Boca del Río" --gerente gerente.bocadelrio --gerente-nombre "Laura" \
--         --gerente-apellidos "Mendoza Ruiz" --gerente-telefono 2291234500
-- =====================================================================================

BEGIN;

INSERT INTO sucursal (nombre, direccion, ciudad, estado, radio_cobertura_km, hora_apertura, hora_cierre)
VALUES ('Boca del Río', 'Blvd. Manuel Ávila Camacho 2000', 'Boca del Río', 'Veracruz', 4.5, '12:00', '23:00');

-- Un cocinero no inicia sesión (RN-016), así que se puede dar de alta directamente en SQL.
INSERT INTO empleado (id_sucursal, nombre, apellidos, telefono, puesto)
SELECT id_sucursal, 'Mario', 'Fuentes Rivas', '2291234501', 'Cocinero' FROM sucursal WHERE nombre = 'Boca del Río';

COMMIT;

-- Comprobación: la sucursal ya existe, con su propio horario (RN-002 se valida contra él).
SELECT id_sucursal, nombre, ciudad, hora_apertura, hora_cierre, activa FROM sucursal ORDER BY id_sucursal;
