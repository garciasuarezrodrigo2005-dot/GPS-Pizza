# Guion de la demostración · GPizza

Objetivo: demostrar en ~25 minutos que el sistema cumple **todos** los casos de uso (CU), requisitos funcionales (RF),
reglas de negocio (RN) y requisitos no funcionales (RNF) de la ERS. Cada paso indica qué se cumple; la matriz completa
está en [trazabilidad.md](trazabilidad.md).

Contraseña de todos los usuarios de demo: **`Pizza2026`**.

---

## 0. Preparación (antes de la presentación, 10 min)

| # | Acción | Para qué |
|---|---|---|
| 1 | `flask --app gpizza db-reset --si` y `flask --app gpizza db-seed` | Datos limpios (229 pedidos, códigos sin usar, alertas listas) |
| 2 | En `.env`: `GPIZZA_HORA_DEMO=14:00` (o la hora que diga el seed) | Los pedidos de "hoy" coinciden con el reloj; los pedidos se aceptan aunque se presente antes de las 11:00 |
| 3 | `flask --app gpizza run --debug` (o `python run.py`) | Servidor |
| 4 | Abrir 4 ventanas: **Cliente** (Chrome, modo celular con F12), **Cajero** (Edge), **Repartidor** (Chrome incógnito, modo celular), **Gerente** (Edge InPrivate) | Cada actor con su sesión |
| 5 | `pytest -q` en una terminal visible | Mostrar las 168 pruebas en verde al inicio |
| 6 | Tener abierto `psql -U gpizza_user -d gpizza` | Demostrar las reglas en la base de datos |

**Plan B:** si no hay internet, los mapas no cargan sus mosaicos (todo lo demás funciona: Bootstrap, HTMX y Chart.js
están dentro del proyecto). Si el GPS falla, usar "Simular recorrido".

---

## 1. Arranque y calidad (2 min)

1. Terminal: `pytest -q` → todas en verde. *RNF-006 (mantenibilidad), todas las reglas probadas automáticamente.*
2. Navegador: `http://localhost:5000/salud` → `{"estado":"ok","bd":"ok"}`. *RNF-002.*
3. F12 → Network → cualquier petición → cabecera `Server-Timing: app;dur=…`. *RNF-001.*

## 2. El cliente pide (CU-001, CU-010, CU-005) — 4 min

Ventana **Cliente** (tamaño celular):
1. Inicio: el horario de pedidos está a la vista (RN-002). Teléfono `2297654321` → continuar: sus datos se autocompletan (CU-005, RF-005).
2. Menú (CU-010, RF-002): pestañas Pizzas / Complementos; un producto agotado en gris (CU-001 FA-2).
3. Agregar 1 Pepperoni Personal ($89): el total avisa "te faltan $11" (**RN-001**). Subir a 6 unidades: el "+" se apaga en 5 (**RN-003**).
4. Código `BIENVENIDA10` → "Aplicar" (**RN-008**). Probar `VENCIDO20` → "no está vigente".
5. Efectivo, "¿Con cuánto pagas?" 500 → el cambio se calcula solo (**RN-009, RN-010**).
6. Recargar la página: el pedido se recupera del dispositivo (CU-001 FA-5).
7. "Enviar pedido" → "Registrado en 0.0X s" (**RNF-001**) y la pantalla "Tu pedido" (boceto 3), que se actualiza sola.

## 3. El cajero confirma (CU-001 pasos 10–11, CU-007) — 3 min

Ventana **Cajero** (`cajero1.coyol`):
1. Aparece el aviso "1 pedido nuevo por confirmar" (CU-007) sin recargar.
2. Elegir "45 min" y un cocinero → "Confirmar pedido" (decisión 10: queda registrado quién cocina).
3. Cliente: en ≤ 10 s cambia a "Pedido confirmado · Tiempo estimado 45 min" con su barra de progreso (boceto 4, RF-004).
4. *(Alternativa)* "Rechazar" con motivo → el cliente ve el motivo.
5. "Nuevo" → teléfono nuevo → pedido por teléfono directo a cocina; escribir `YP000002` y Enter en "Escanea o escribe el código" (**RF-009**).

## 4. Cancelación de acuerdo mutuo (RN-005) — 2 min

1. Cliente: "¿Necesitas cancelar?" → motivo → pedir. El pedido **sigue** en preparación (una parte no basta).
2. Cajero → "Pedidos": "El cliente pide cancelar" → "Rechazar" (o "Aceptar").
3. En "En camino" el cajero ya no tiene botón de cancelar: "se requiere al gerente".

## 5. Listo, asignación y entrega (CU-002, RF-003, RF-010, RN-011, RN-013) — 5 min

1. Cajero → "Pedidos" → "Marcar listo" → "Se asignó a Carlos Gómez Arano" (**CU-002**, menor carga, **RN-011**).
2. Ventana **Repartidor** (`repartidor1.coyol`): "Activos: N de 2", el pedido "Por aceptar" con su plazo de 5 min → "Aceptar entrega".
3. Cliente: "Tu pedido va en camino" con mapa, "Llega en ~N min", "Llamar" y su **código de entrega** (boceto 5, CU-003).
4. Repartidor: "Simular recorrido" → el 🛵 avanza también en el mapa del cliente.
5. Repartidor: "Marcar como entregado" está desactivado. Firmar con el dedo (o escribir el código del cliente) →
   "Registrar confirmación del cliente" → "Paso 2 · Marcar como entregado" (**RN-013, RF-010**).
6. Cajero → "Ver detalle" del pedido: firma, horas de cada paso, cajero, cocinero y repartidor (CU-003).

## 6. Alertas (RN-006, RN-014) — 1 min

1. Cajero → "Pedidos": el pedido de la demo con más de 45 min aparece en rojo (**RN-006**); pestaña "En camino": el de más de 90 min (**RN-014**).
2. Gerente → campana 🔔: las alertas de tiempo (CU-007).

## 7. Gerente (CU-004, CU-008, CU-009, RF-011, RN-007, RN-015, RN-019) — 5 min

Ventana **Gerente** (`gerente.coyol`, escritorio):
1. **Catálogo y precios**: cambiar el precio de la Hawaiana Grande → recargar el menú del cliente (**RN-007**). Imprimir etiquetas QR (RF-009).
2. **Personal**: alta de un cajero → contraseña temporal; entrar con ella obliga a cambiarla (**CU-009a, RN-018**). Desbloquear `repartidor3.coyol`.
3. **Descuentos y devoluciones**: emitir un código; registrar la devolución del pedido entregado en el paso 5 (**RF-011, RN-015**).
4. **Reportes**: período de 14 días → tarjetas, gráfica y detalle por repartidor; filtrar por repartidor; **Exportar PDF** y **Exportar Excel** (**CU-004, CU-008**). "Generado en 0.1 s".
5. **Auditoría**: filtrar por "CANCELAR" o por usuario `cajero1.coyol`; no existe forma de editar (**RN-019**).

## 8. Seguridad y reglas en la base de datos (RNF-003, RN-016–RN-019) — 2 min

1. Login con contraseña equivocada → "Intento 1 de 3" (**RN-018**); `repartidor3.coyol` bloqueado.
2. Entrar como `cajero1.coyol` en otra ventana → la primera se cierra al siguiente clic (**RN-017**).
3. Cajero abre `http://localhost:5000/gerente/reportes` → "Acceso no permitido" (**RF-012, RN-016**).
4. `psql`:
   ```sql
   SELECT set_config('gpizza.rol', 'Cajero', false);
   UPDATE producto SET precio = 1 WHERE id_producto = 1;   -- RN-007: rechazado por la BD
   DELETE FROM auditoria;                                 -- RN-019: permiso denegado
   SELECT telefono, direccion FROM cliente LIMIT 2;       -- RNF-003: dirección cifrada
   ```

## 9. Requisitos no funcionales en vivo — 2 min

| RNF | Demostración |
|---|---|
| RNF-001 Rendimiento | `pytest -s tests/test_rendimiento.py` → "20 pedidos · máximo 0.03 s · límite 3 s" |
| RNF-002 Disponibilidad | PowerShell **como administrador**: `Stop-Service postgresql-x64-18` → `/salud` responde 503 "caida" y el inicio del cliente sigue abriendo → `Start-Service postgresql-x64-18` → `/salud` vuelve a "ok" sin reiniciar la app |
| RNF-003 Seguridad | `pytest -v tests/test_rnf.py` → 50 rutas × 4 perfiles revisadas automáticamente |
| RNF-004 Usabilidad | Comparar las pantallas con los bocetos (`docs/evidencias/`) |
| RNF-005 Escalabilidad | `flask --app gpizza nueva-sucursal --nombre "Boca del Río" …` → aparece de inmediato en la lista del cliente, sin tocar código |
| RNF-006 Mantenibilidad | Estructura de carpetas (README) y `tests/test_rnf.py::test_rnf006_*` |
| RNF-007 Compatibilidad | Capturas en `docs/evidencias/` (Chrome y Edge, 375 px y 1366 px); instalar como app en un celular |
| RNF-008 Portabilidad | README "Instalación en una computadora nueva": se probó clonando en una carpeta vacía |

## Preguntas frecuentes del jurado

- **¿Por qué validar dos veces (código y base de datos)?** El código da mensajes claros; la base garantiza la regla aunque alguien use SQL directo o haya un error en el código.
- **¿Por qué una PWA y no una app nativa?** Un solo código para celular y PC; se instala en la pantalla de inicio y funciona en Android 10+ e iOS 14+ (RNF-007).
- **¿Y la zona de cobertura (RN-012)?** Por decisión del equipo se reclasificó como RNF-009 (mejora futura); la sucursal ya guarda su radio.
- **¿Cómo sabe la base de datos quién hace cada acción?** La app fija `gpizza.rol` y `gpizza.id_empleado` en cada transacción; los triggers los leen (docs/diseno.md §5).
