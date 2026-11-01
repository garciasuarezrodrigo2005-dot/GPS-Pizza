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
> Última actualización: 2026-11-01, al cerrar la **Fase 0** (ver "Registro de fases" al final)

## Casos de uso

| ID | Nombre | Dónde se implementa | Cómo se demuestra / prueba | Fase | Estado |
|---|---|---|---|---|---|
| CU-001 | Registrar Pedido de Pizzas | `web/cliente.py` (pedido desde la app), `web/cajero.py` (pedido por teléfono o en sucursal; confirmación eligiendo tiempo estimado y cocinero), `servicios/pedidos.py`, tablas `pedido` + `detalle_pedido` | Demo: el cliente arma un pedido → "Por confirmar" → el cajero lo confirma con tiempo y cocinero → "En Preparación". `test_registrar_pedido_valido` | F3 | ⬜ |
| CU-002 | Asignar Repartidor a Pedido | `servicios/asignacion.py` (automática por carga), botón "Aceptar" del repartidor, `web/gerente.py` (manual), `trg_asignacion_limite` | Demo: el cajero marca "Listo" → se asigna solo → el repartidor acepta → "En Camino". Sin aceptar en 5 min → reasignación. El gerente asigna a mano. `test_asignacion_*` | F4 | ⬜ |
| CU-003 | Consultar Seguimiento de Pedido | `web/cliente.py` (barra de progreso + mapa), `web/cajero.py` / `gerente.py` (búsqueda por folio o teléfono; muestra cajero, cocinero y repartidor), `web/repartidor.py` | Demo con los 4 actores; folio inexistente (FA-1); pedido cancelado con su motivo (FA-2) | F4 | ⬜ |
| CU-004 | Generar Reporte de Desempeño Operativo | `servicios/reportes.py`, `web/gerente.py`, Chart.js (sucursal fija = la del gerente) | Demo: filtros por período y repartidor; tarjetas, gráfica y tabla. Filtro sin datos (FA-1). `test_reportes.py` | F6 | ⬜ |
| CU-005 | Registrar Perfil de Cliente | `web/cliente.py` (primer pedido), `web/cajero.py` (Clientes / nuevo pedido), `servicios/clientes.py` | Demo: teléfono nuevo → captura de datos → vuelve al pedido | F3 | ⬜ |
| CU-006 | Autenticar Usuario | `web/auth.py`, `seguridad/acceso.py`, `seguridad/contrasenas.py` | Demo: login de cada rol; 3 intentos fallidos → bloqueo; sesión única con dos navegadores. `test_auth.py` | F2 | ⬜ |
| CU-007 | Notificar Estado | `servicios/notificaciones.py`, tabla `notificacion`, `fn_generar_alertas()`, `static/js/polling.js` | Demo: aviso al cajero de un pedido nuevo, avisos al cliente en cada cambio, solicitudes de cancelación y alertas de 45 y 90 min (con datos sembrados "viejos") | F4 | ⬜ |
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

| ID | Regla | En el código | En la BD | Prueba | Fase | Estado |
|---|---|---|---|---|---|---|
| RN-001 | Pedido mínimo $100 (sobre el valor de los productos, antes del descuento) | `servicios/pedidos.py` (mensaje + botón desactivado) | `CHECK (subtotal >= 100)` | `test_rn001_minimo` (servicio + INSERT directo) | F1/F3 | ⬜ |
| RN-002 | Horario 11:00–22:00 | Aviso de horario en el inicio del cliente; pantalla "Fuera de horario"; validación en el servicio | `trg_pedido_validar_alta` contra `sucursal.hora_apertura/cierre` | `test_rn002_fuera_de_horario` | F1/F3 | ⬜ |
| RN-003 | Máx. 10 distintos / 5 c/u | Botón "+" desactivado; validación en el servicio | `CHECK cantidad BETWEEN 1 AND 5`, `UNIQUE (id_pedido,id_producto)`, trigger diferido (≤10) | `test_rn003_*` | F1/F3 | ⬜ |
| RN-004 | Nombre, teléfono y dirección obligatorios | Formulario + servicio; teléfono numérico de 10 dígitos | `NOT NULL` + `CHECK (btrim(...) <> '')` + `CHECK telefono ~ '^[0-9]{10}$'` | `test_rn004_campos_obligatorios`, `test_rn004_telefono_no_numerico` | F1/F3 | ⬜ |
| RN-005 | Cancelación: en "En Preparación" de acuerdo mutuo cliente–cajero; después, solo el gerente | `servicios/cancelaciones.py`; botones Solicitar / Aceptar / Rechazar; casilla "confirmó por teléfono" | `trg_pedido_transicion` + `gpizza.rol` + columnas de solicitud | `test_rn005_una_parte_no_basta`, `test_rn005_acuerdo_mutuo`, `test_rn005_telefono`, `test_rn005_cajero_no_cancela_en_camino`, `test_rn005_gerente_si` | F1/F4 | ⬜ |
| RN-006 | Alerta a los 45 min en preparación (desde `fecha_preparacion`) | Aviso rojo en Pedidos (como en el boceto) | `fn_generar_alertas()` + índice único de alertas | `test_rn006_alerta_45` | F4 | ⬜ |
| RN-007 | Solo el gerente edita precios | Solo la ruta del gerente tiene el formulario de precio | `trg_producto_precio`, `trg_detalle_precio` | `test_rn007_cajero_no_cambia_precio`, `test_rn007_precio_manipulado` | F1/F6 | ⬜ |
| RN-008 | Descuento solo con código del gerente | Validación del código en el servicio | `trg_descuento_emisor`, `trg_pedido_descuento`, `UNIQUE id_codigo_descuento` | `test_rn008_codigo_invalido/vencido/usado` | F1/F3 | ⬜ |
| RN-009 | Un método de pago | Selector de una sola opción | Una sola columna `forma_pago` + `CHECK IN (...)` | `test_rn009_metodo_invalido` | F1/F3 | ⬜ |
| RN-010 | Cálculo automático del cambio | `servicios/pedidos.py` | `CHECK (cambio = monto_recibido - total)` | `test_rn010_cambio` | F1/F3 | ⬜ |
| RN-011 | Máx. 2 pedidos activos por repartidor | Filtro en `asignacion.py`; "Activos: 1 de 2" | `trg_asignacion_limite` con `FOR UPDATE` | `test_rn011_tercera_asignacion_falla` | F1/F4 | ⬜ |
| RN-012 | Zona de entrega | ➖ **Movida a RNF-009** (decisión 5). El cliente elige su sucursal. | Solo se guarda `sucursal.radio_cobertura_km` | — | — | ➖ |
| RN-013 | Entrega solo con firma o código | Paso 1 (cliente) obligatorio antes de habilitar el botón del repartidor; validación del código | `ck_entregada` + `trg_pedido_transicion` | `test_rn013_sin_confirmacion_cliente`, `test_rn013_codigo_incorrecto`, `test_rn013_flujo_completo` | F1/F5 | ⬜ |
| RN-014 | Alerta a los 90 min en camino | "Tiempo en camino" en rojo al pasar el límite | `fn_generar_alertas()` | `test_rn014_alerta_90` | F4 | ⬜ |
| RN-015 | Devoluciones: solo el gerente y ≤ 2 h | Ruta del gerente + validación | `trg_devolucion_validar` | `test_rn015_fuera_de_plazo`, `test_rn015_no_gerente` | F1/F6 | ⬜ |
| RN-016 | Un rol por usuario | `@rol_requerido`, menú según el rol | Una sola columna `puesto` + `CHECK` + `ck_acceso` | `test_rn016_*` | F1/F2 | ⬜ |
| RN-017 | Sesión única | Se valida el token en cada petición | `trg_sesion_unica` + índice único parcial | `test_rn017_segundo_login_cierra_primero` | F1/F2 | ⬜ |
| RN-018 | Contraseña ≥8 con letras y números, vence a 90 días, bloqueo a los 3 intentos | `seguridad/contrasenas.py`, pantalla "Cambiar contraseña", `flask desbloquear` | `CHECK intentos 0..3`, `trg_empleado_bloqueo` | `test_rn018_politica`, `test_rn018_vencida`, `test_rn018_bloqueo` | F1/F2 | ⬜ |
| RN-019 | Auditoría inmutable | Pantalla Auditoría (solo lectura, solo su sucursal) | `trg_auditar_*`, `trg_auditoria_inmutable`, `REVOKE` | `test_rn019_update_falla`, `test_rn019_delete_falla`, `test_rn019_registro_automatico` | F1/F6 | ⬜ |

## Requisitos no funcionales

| ID | Categoría | Dónde se implementa | Cómo se demuestra | Fase | Estado |
|---|---|---|---|---|---|
| RNF-001 | Rendimiento (< 3 s) | ✔ F0: `gpizza/monitoreo.py` mide cada petición → `logs/rendimiento.log` + cabecera `Server-Timing`. Pendiente: aviso "Registrado en X s" y prueba con pedidos reales | ✔ `test_cada_respuesta_trae_su_tiempo_en_server_timing`. Pendiente: `test_rendimiento.py` (20 pedidos < 3 s; reportes < 5 s) | F0/F3/F7 | 🟨 |
| RNF-002 | Disponibilidad | ✔ F0: `GET /salud` (`web/sistema.py`), páginas 403/404/500/CSRF, error 503 amable si cae la BD, `connect_timeout` y `pool_pre_ping`, waitress (`run.py`) | ✔ `test_salud_*`, `test_pagina_que_usa_la_bd_caida_*`, `test_error_inesperado_*`, `test_pagina_inexistente_*`. Demo: detener PostgreSQL → `/salud` responde 503 "caida" y la app sigue | F0/F7 | 🟨 |
| RNF-003 | Seguridad | ✔ F0: CSRFProtect global, cookies HttpOnly + SameSite, cabeceras `nosniff` y `X-Frame-Options`. Pendiente: Argon2id, Fernet, `@rol_requerido`, consultas parametrizadas | ✔ `test_post_sin_token_csrf_es_rechazado`, `test_cabeceras_de_seguridad`. Pendiente: `test_seguridad.py` (inyección SQL, cifrado, hash) | F0–F3/F7 | 🟨 |
| RNF-004 | Usabilidad | Plantillas basadas en los bocetos; botones de ≥ 48 px; mensajes en español; navegación inferior en el celular | Recorrido de la demo comparando cada pantalla con su boceto | F3–F7 | ⬜ |
| RNF-005 | Escalabilidad | Sucursal, horario y personal son datos; nada fijo en el código; la lista de sucursales del cliente sale de la BD | Ejecutar `db/ejemplo_nueva_sucursal.sql` (o `flask nueva-sucursal`) → aparece en la lista del cliente y se le pueden dar de alta gerente y personal, sin reiniciar | F7 | ⬜ |
| RNF-006 | Mantenibilidad | ✔ F0: fábrica `create_app`, blueprints en `web/`, `reglas.py`, `reloj.py`, `monitoreo.py`, *docstrings* en español, README | Revisión de la estructura en la presentación | Todas | 🟨 |
| RNF-007 | Compatibilidad | ✔ F0: Bootstrap mobile-first (botones de 48 px), `manifest.webmanifest`, service worker (`/sw.js`), iconos, página `/offline`; Bootstrap y HTMX incluidos en `static/vendor` (funcionan sin internet) | ✔ `test_service_worker_y_manifest_disponibles`; revisado a 375 px (sin desborde horizontal) y en escritorio. Pendiente: instalar en un celular real y capturas en `docs/evidencias/` | F0/F7 | 🟨 |
| RNF-008 | Portabilidad | ✔ F0: `.env` / `.env.example`, `config.py` (todo sale del entorno), `requirements.txt` con versiones fijas, `run.py` (waitress). Pendiente: `flask db-reset` | README "Instalación en una computadora nueva". Demo: clonar en otra carpeta y seguir el README | F0/F7 | 🟨 |
| RNF-009 | Cobertura geográfica (antes RN-012) | ➖ Fuera de alcance en esta versión; la sucursal guarda `radio_cobertura_km` para una versión futura | Se explica en la presentación como trabajo futuro | — | ➖ |

## Registro de fases

| Fase | Fecha | Entregable | Pruebas |
|---|---|---|---|
| F0 Esqueleto | 2026-11-01 | Configuración por `.env`, fábrica de la app, `/salud`, páginas de error, medición de tiempos, plantilla base con el estilo de los bocetos, pantalla de inicio del cliente con horario, PWA (manifest, service worker, iconos), README | `pytest`: 10 pasan, 1 omitida (`test_salud_con_bd_disponible` necesita la base `gpizza_test`) |
