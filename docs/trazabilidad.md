# Matriz de trazabilidad: GPizza

> Relaciona cada caso de uso (CU), requisito funcional (RF), requisito no funcional (RNF) y regla de negocio (RN)
> con el lugar donde se implementa y la forma de demostrarlo. Se actualiza al cerrar cada fase.
> Las decisiones del equipo están en `diseno.md §7`.
>
> **Fases:** F0 Esqueleto · F1 Base de datos · F2 Autenticación · F3 Pedidos (cliente y cajero) ·
> F4 Ciclo del pedido · F5 Repartidor y mapas · F6 Panel del gerente · F7 Calidad y demo
>
> **Estado:** ⬜ pendiente · 🟨 en progreso · ✅ hecho y probado · ➖ fuera de alcance (decisión del equipo)
>
> Última actualización: 2026-11-01, al cerrar la **Fase 1** (ver "Registro de fases" al final)

## Casos de uso

| ID | Nombre | Dónde se implementa | Cómo se demuestra / prueba | Fase | Estado |
|---|---|---|---|---|---|
| CU-001 | Registrar Pedido de Pizzas | `web/cliente.py` (pedido desde la app), `web/cajero.py` (pedido por teléfono o en sucursal; confirmación eligiendo tiempo estimado y cocinero), `servicios/pedidos.py`, tablas `pedido` + `detalle_pedido` | Demo: el cliente arma un pedido → "Por confirmar" → el cajero lo confirma con tiempo y cocinero → "En Preparación". `test_registrar_pedido_valido` | F3 | ⬜ |
| CU-002 | Asignar Repartidor a Pedido | `servicios/asignacion.py` (automática por carga), botón "Aceptar" del repartidor, `web/gerente.py` (manual), `trg_asignacion_limite` | Demo: el cajero marca "Listo" → se asigna solo → el repartidor acepta → "En Camino". Sin aceptar en 5 min → reasignación. El gerente asigna a mano. `test_asignacion_*` | F4 | ⬜ |
| CU-003 | Consultar Seguimiento de Pedido | `web/cliente.py` (barra de progreso + mapa), `web/cajero.py` / `gerente.py` (búsqueda por folio o teléfono; muestra cajero, cocinero y repartidor), `web/repartidor.py` | Demo con los 4 actores; folio inexistente (FA-1); pedido cancelado con su motivo (FA-2) | F4 | ⬜ |
| CU-004 | Generar Reporte de Desempeño Operativo | `servicios/reportes.py`, `web/gerente.py`, Chart.js (sucursal fija = la del gerente) | Demo: filtros por período y repartidor; tarjetas, gráfica y tabla. Filtro sin datos (FA-1). `test_reportes.py` | F6 | ⬜ |
| CU-005 | Registrar Perfil de Cliente | `web/cliente.py` (primer pedido), `web/cajero.py` (Clientes / nuevo pedido), `servicios/clientes.py` | Demo: teléfono nuevo → captura de datos → vuelve al pedido | F3 | ⬜ |
| CU-006 | Autenticar Usuario | `web/auth.py`, `seguridad/acceso.py`, `seguridad/contrasenas.py` | Demo: login de cada rol; 3 intentos fallidos → bloqueo; sesión única con dos navegadores. `test_auth.py` | F2 | ⬜ |
| CU-007 | Notificar Estado | ✔ F1: los triggers generan las notificaciones de cada cambio de estado, solicitud de cancelación, asignación y alertas (`fn_pedido_despues`, `fn_asignacion_despues`, `fn_generar_alertas`). Pendiente: mostrarlas con polling (`static/js/polling.js`, F4) | ✔ `test_pedido_valido_se_registra_por_confirmar` (aviso al cajero), `test_rn006_*`, `test_rn014_*`. Demo: avisos al cliente en cada cambio | F1/F4 | 🟨 |
| CU-008 | Exportar Reporte PDF/Excel | `servicios/exportar.py` (ReportLab, openpyxl) | Demo: descargar y abrir los dos archivos. `test_exportar.py` | F6 | ⬜ |
| CU-009 | Gestionar Personal | `web/gerente.py` → Personal (solo su sucursal) | Demo: alta, edición y baja de empleados, incluidos los cocineros (sin usuario) | F6 | ⬜ |
| CU-009a | Gestionar Cajeros | `web/gerente.py` (filtro Cajeros; usuario, desbloqueo, reinicio de contraseña) | Demo: alta de un cajero → entra con su usuario | F6 | ⬜ |
| CU-009b | Gestionar Repartidores | `web/gerente.py` (filtro Repartidores; disponibilidad) | Demo: alta de un repartidor → aparece en la asignación | F6 | ⬜ |
| CU-010 | Consultar Menú Digital | `web/cliente.py`, `web/cajero.py`, `servicios/catalogo.py` | Demo: pestañas Pizzas / Complementos; producto agotado en gris (FA-2) | F3 | ⬜ |

## Requisitos funcionales

| ID | Nombre | Dónde se implementa | Cómo se demuestra / prueba | Fase | Estado |
|---|---|---|---|---|---|
| RF-001 | Registro de pedido + procesamiento de pago | `servicios/pedidos.py`, `pedido` (CHECK de pago) | CU-001 con efectivo (cambio calculado), tarjeta y transferencia | F3 | ⬜ |
| RF-002 | Menú digital | `servicios/catalogo.py`, plantillas de menú | CU-010; el gerente cambia la disponibilidad y se ve al instante | F3 | ⬜ |
| RF-003 | Asignación automática de repartidor | `servicios/asignacion.py` | CU-002; `test_asignacion_elige_menor_carga` | F4 | ⬜ |
| RF-004 | Seguimiento de pedido | `web/cliente.py`, vistas de Pedidos por estado | CU-003; la barra de progreso se actualiza sola | F4 | ⬜ |
| RF-005 | Gestión de clientes | `web/cajero.py` (Clientes), `web/gerente.py` (Clientes) | CU-005; búsqueda por teléfono; dirección cifrada en la BD | F3/F6 | ⬜ |
| RF-006 | Gestión de empleados | `web/gerente.py` (Personal) | CU-009, 009a, 009b | F6 | ⬜ |
| RF-007 | Notificaciones de estado | `servicios/notificaciones.py` + polling | CU-007 | F4 | ⬜ |
| RF-008 | Reportes de desempeño | `servicios/reportes.py`, `servicios/exportar.py` | CU-004 + CU-008 | F6 | ⬜ |
| RF-009 | Registro con código QR / barras | `producto.codigo_qr_barras`; escáner `html5-qrcode` en "Nuevo pedido" (o lector USB); QR del folio para seguimiento | Demo: escanear el QR de un producto → se agrega al pedido; escanear el QR del folio → abre el seguimiento | F6 | ⬜ |
| RF-010 | Control de entregas con firma digital | `web/repartidor.py`, `servicios/entregas.py`, `static/js/firma.js` (canvas → PNG → `firma_digital`) | Demo: 1) el cliente firma o da su código; 2) el repartidor pulsa "Confirmar entrega". Se ven la firma, la fecha y la hora en el detalle | F5 | ⬜ |
| RF-011 | Devoluciones | `web/gerente.py` (Descuentos y devoluciones), `trg_devolucion_validar` | Demo: devolución válida; intento con más de 2 h → rechazado | F6 | ⬜ |
| RF-012 | Autenticación por rol | `seguridad/acceso.py` (`@rol_requerido` + filtro por sucursal) | CU-006; un cajero que abre una URL del gerente → 403; un gerente que abre un pedido de otra sucursal → 404. `test_acceso_por_rol`, `test_acceso_por_sucursal` | F2 | ⬜ |

## Reglas de negocio (doble validación: código + base de datos)

La columna "En la BD" está terminada desde la Fase 1 (`db/*.sql`) y probada con SQL directo, sin pasar por la app
(`tests/test_rn_bd.py`). La columna "En el código" se completa en la fase indicada.

| ID | Regla | En el código | En la BD | Prueba (✔ = ya pasa) | Fase | Estado |
|---|---|---|---|---|---|---|
| RN-001 | Pedido mínimo $100 (subtotal, antes del descuento) | `reglas.PEDIDO_MINIMO`; mensaje y botón en F3 | ✔ `rn001_pedido_minimo` (`subtotal >= 100`) | ✔ `test_rn001_subtotal_menor_a_100_es_rechazado` | F1/F3 | 🟨 |
| RN-002 | Horario 11:00–22:00 | ✔ aviso en el inicio del cliente (F0); validación en F3 | ✔ `trg_pedido_alta` contra el horario de la sucursal y `fn_ahora()` | ✔ `test_rn002_fuera_de_horario_es_rechazado`, `test_inicio_fuera_de_horario_*` | F0/F1/F3 | 🟨 |
| RN-003 | Máx. 10 distintos / 5 c/u | Botón "+" desactivado (F3) | ✔ `rn003_unidades`, `rn003_producto_unico`, trigger diferido `trg_pedido_verificar_detalle` | ✔ `test_rn003_mas_de_5_unidades_*`, `test_rn003_mas_de_10_productos_*` | F1/F3 | 🟨 |
| RN-004 | Nombre, teléfono (10 dígitos) y dirección obligatorios | Formulario (F3) | ✔ `NOT NULL`, `btrim(...) <> ''`, `rn004_cliente_telefono` | ✔ `test_rn004_telefono_no_numerico_y_datos_vacios_*` | F1/F3 | 🟨 |
| RN-005 | Cancelación: acuerdo mutuo en "En Preparación"; después, solo el gerente | Botones Solicitar / Aceptar / Rechazar (F4) | ✔ `trg_pedido_cambio` (solicitud, aceptación, confirmación telefónica, gerente) | ✔ `test_rn005_cajero_solo_no_cancela_*`, `test_rn005_acuerdo_mutuo_cancela`, `test_rn005_pedido_telefonico_*`, `test_rn005_en_camino_solo_cancela_el_gerente` | F1/F4 | 🟨 |
| RN-006 | Alerta a los 45 min en preparación | Aviso rojo en Pedidos (F4) | ✔ `fn_generar_alertas()` + `uq_notificacion_alerta` (sin duplicados) | ✔ `test_rn006_alerta_a_los_45_minutos_sin_duplicarse` | F1/F4 | 🟨 |
| RN-007 | Solo el gerente edita precios | Formulario de precios solo para el gerente (F6) | ✔ `trg_producto_gerente`, `trg_detalle_alta` (precio de lista) | ✔ `test_rn007_cajero_no_cambia_precios_y_gerente_si`, `test_rn007_precio_alterado_*` | F1/F6 | 🟨 |
| RN-008 | Descuento solo con código del gerente | Validación del código (F3) | ✔ `trg_pedido_alta` (vigente, sin usar, monto exacto; sin código = sin descuento), `trg_descuento_validar`, `UNIQUE id_codigo_descuento` | ✔ `test_rn008_no_hay_descuentos_sin_codigo`, `test_rn008_codigo_vencido_usado_o_mal_calculado_*`, `test_rn008_solo_el_gerente_emite_codigos` | F1/F3 | 🟨 |
| RN-009 | Un método de pago | Selector de una opción (F3) | ✔ una sola columna `forma_pago` + `rn009_forma_pago` | ✔ `test_rn009_un_solo_metodo_de_pago_valido` | F1/F3 | 🟨 |
| RN-010 | Cálculo automático del cambio | Cálculo en el servicio (F3) | ✔ `rn010_cambio` (`cambio = monto_recibido - total`, y que alcance para pagar) | ✔ `test_rn010_cambio_mal_calculado_es_rechazado` | F1/F3 | 🟨 |
| RN-011 | Máx. 2 pedidos activos por repartidor | Filtro en la asignación; "Activos: 1 de 2" (F4) | ✔ `trg_asignacion_validar` con `FOR UPDATE` | ✔ `test_rn011_un_repartidor_no_tiene_mas_de_2_*` | F1/F4 | 🟨 |
| RN-012 | Zona de entrega | ➖ **Movida a RNF-009** (decisión 5). El cliente elige su sucursal. | Solo se guarda `sucursal.radio_cobertura_km` | — | — | ➖ |
| RN-013 | Entrega en dos pasos: cliente (firma o código) y repartidor | Canvas y botón de confirmación (F5) | ✔ `rn013_confirmacion_cliente`, `rn013_entrega`, validación del código, `trg_pedido_cambio` | ✔ `test_rn013_sin_confirmacion_del_cliente_*`, `test_rn013_codigo_del_cliente_incorrecto_*`, `test_rn013_entrega_en_dos_pasos`, `test_solo_el_repartidor_asignado_acepta` | F1/F5 | 🟨 |
| RN-014 | Alerta a los 90 min en camino (gerente y cajero) | "Tiempo en camino" en rojo (F4/F5) | ✔ `fn_generar_alertas()` | ✔ `test_rn014_alerta_a_los_90_minutos_al_gerente_y_al_cajero` | F1/F4 | 🟨 |
| RN-015 | Devoluciones: solo el gerente y ≤ 2 h | Pantalla de devoluciones (F6) | ✔ `trg_devolucion_validar` | ✔ `test_rn015_solo_el_gerente_registra_devoluciones`, `test_rn015_devolucion_dentro_y_fuera_de_las_2_horas` | F1/F6 | 🟨 |
| RN-016 | Un rol por usuario; el cocinero no inicia sesión | `@rol_requerido`, menú según el rol (F2) | ✔ columna única `puesto`, `rn016_empleado_acceso`, `trg_sesion_unica` | ✔ `test_rn016_un_rol_por_usuario_y_el_cocinero_no_inicia_sesion` | F1/F2 | 🟨 |
| RN-017 | Sesión única | Validación del token en cada petición (F2) | ✔ `rn017_sesion_unica` (índice único parcial) + `trg_sesion_unica` | ✔ `test_rn017_un_segundo_inicio_de_sesion_cierra_el_primero` | F1/F2 | 🟨 |
| RN-018 | Contraseña ≥ 8 con letras y números, vence a 90 días, bloqueo a los 3 intentos | ✔ `seguridad/contrasenas.py` (Argon2id, política, vencimiento); pantallas en F2 | ✔ `rn018_intentos`, `trg_empleado_bloqueo` (bloquea y cierra sesiones) | ✔ `test_rn018_tres_intentos_bloquean_la_cuenta` | F1/F2 | 🟨 |
| RN-019 | Auditoría inmutable | Pantalla Auditoría de solo lectura (F6) | ✔ `fn_auditar` en 8 tablas (sin datos sensibles), `trg_auditoria_inmutable`, `REVOKE` | ✔ `test_rn019_cada_accion_queda_registrada_con_usuario`, `test_rn019_la_bitacora_no_se_puede_editar_ni_borrar` (×3), `test_rn019_la_bitacora_no_guarda_datos_sensibles` | F1/F6 | 🟨 |

## Requisitos no funcionales

| ID | Categoría | Dónde se implementa | Cómo se demuestra | Fase | Estado |
|---|---|---|---|---|---|
| RNF-001 | Rendimiento (< 3 s) | ✔ F0: `gpizza/monitoreo.py` mide cada petición → `logs/rendimiento.log` + cabecera `Server-Timing`. Pendiente: aviso "Registrado en X s" y prueba con pedidos reales | ✔ `test_cada_respuesta_trae_su_tiempo_en_server_timing`. Pendiente: `test_rendimiento.py` (20 pedidos < 3 s; reportes < 5 s) | F0/F3/F7 | 🟨 |
| RNF-002 | Disponibilidad | ✔ F0: `GET /salud` (`web/sistema.py`), páginas 403/404/500/CSRF, error 503 amable si cae la BD, `connect_timeout` y `pool_pre_ping`, waitress (`run.py`) | ✔ `test_salud_*`, `test_pagina_que_usa_la_bd_caida_*`, `test_error_inesperado_*`, `test_pagina_inexistente_*`. Demo: detener PostgreSQL → `/salud` responde 503 "caida" y la app sigue | F0/F7 | 🟨 |
| RNF-003 | Seguridad | ✔ F0: CSRFProtect, cookies HttpOnly + SameSite, cabeceras. ✔ F1: Argon2id (`seguridad/contrasenas.py`), Fernet en dirección y referencia de pago (`seguridad/cifrado.py`), token de sesión guardado como SHA-256, bitácora sin datos sensibles. Pendiente: `@rol_requerido` y filtro por sucursal (F2) | ✔ `test_post_sin_token_csrf_*`, `test_cabeceras_de_seguridad`, `test_rnf003_la_direccion_se_guarda_cifrada`. Pendiente: inyección SQL y hash en el login (F2/F3) | F0–F3/F7 | 🟨 |
| RNF-004 | Usabilidad | Plantillas basadas en los bocetos; botones de ≥ 48 px; mensajes en español; navegación inferior en el celular | Recorrido de la demo comparando cada pantalla con su boceto | F3–F7 | ⬜ |
| RNF-005 | Escalabilidad | ✔ F1: sucursal, horario, radio y personal son datos (5 sucursales en la demo, cada una con su horario en la BD). Pendiente: `db/ejemplo_nueva_sucursal.sql` | Ejecutar el ejemplo → la sucursal aparece en la lista del cliente y acepta personal, sin reiniciar | F1/F7 | 🟨 |
| RNF-006 | Mantenibilidad | ✔ F0: fábrica `create_app`, blueprints en `web/`, `reglas.py`, `reloj.py`, `monitoreo.py`, *docstrings* en español, README | Revisión de la estructura en la presentación | Todas | 🟨 |
| RNF-007 | Compatibilidad | ✔ F0: Bootstrap mobile-first (botones de 48 px), `manifest.webmanifest`, service worker (`/sw.js`), iconos, página `/offline`; Bootstrap y HTMX incluidos en `static/vendor` (funcionan sin internet) | ✔ `test_service_worker_y_manifest_disponibles`; revisado a 375 px (sin desborde horizontal) y en escritorio. Pendiente: instalar en un celular real y capturas en `docs/evidencias/` | F0/F7 | 🟨 |
| RNF-008 | Portabilidad | ✔ F0: `.env` / `.env.example`, `config.py`, `requirements.txt`, `run.py`. ✔ F1: `flask db-reset` y `flask db-seed` recrean todo en cualquier PC | README "Instalación en una computadora nueva". Demo: clonar en otra carpeta y seguir el README | F0/F1/F7 | 🟨 |
| RNF-009 | Cobertura geográfica (antes RN-012) | ➖ Fuera de alcance en esta versión; la sucursal guarda `radio_cobertura_km` para una versión futura | Se explica en la presentación como trabajo futuro | — | ➖ |

## Registro de fases

| Fase | Fecha | Entregable | Pruebas |
|---|---|---|---|
| F0 Esqueleto | 2026-11-01 | Configuración por `.env`, fábrica de la app, `/salud`, páginas de error, medición de tiempos, plantilla base con el estilo de los bocetos, pantalla de inicio del cliente con horario, PWA (manifest, service worker, iconos), README | `pytest`: 10 pasan, 1 omitida (`test_salud_con_bd_disponible` necesita la base `gpizza_test`) |
| F1 Base de datos | 2026-11-01 | Esquema PostgreSQL (12 tablas), 27 triggers con las reglas RN-001 a RN-019, auditoría inmutable, cifrado y hash de contraseñas, `flask db-reset` / `db-seed` / `alertas`, datos de demo (5 sucursales, 25 empleados, 30 productos, 229 pedidos que recorren su ciclo completo por los triggers) | `pytest`: 50 pasan (39 nuevas de reglas en la BD) |
