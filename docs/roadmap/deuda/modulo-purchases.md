# Deuda técnica — Módulo purchases (slices siguientes)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ✅ 2026-08-30 **El ciclo de la OC en pantalla** (ADR-085, migración
  `0a056863874b`): ficha con emitir / recibir / anular / facturar, pantalla de
  compra directa, registro de compras (`GET /purchases/comprobantes`, nuevo),
  y las dos lecturas que faltaban (recepciones y comprobantes de una OC). El
  módulo tenía **todos** sus casos de uso con endpoint y test verde desde
  siempre: el hueco estaba entero del lado del frontend, y no estaba anotado
  en ninguna parte — a diferencia de la deuda de pantallas de `inventory`, que
  sí se documentó. Esa omisión es lo que lo dejó vivo cuatro meses.
- ⬜ **`total_documento` viaja en `purchases.comprobante_conforme` y no lo lee
  nadie** (2026-08-30). Es el importe que declara la factura, aditivo, para la
  reconciliación estilo Odoo que sigue diferida más abajo. El `monto` del
  evento sigue siendo la base de lo recibido, que es lo que la plantilla del
  PCGE espera.
- ⬜ **La compra directa no tiene su propia comprobación de recepción**
  (2026-08-30): recibe el 100% de lo comprado en el mismo paso, que es lo
  correcto para un gasto ya incurrido, pero si el papel dice una cantidad y
  llegó otra no hay dónde corregirlo salvo anulando y rehaciendo.

- ✅ 2026-07-25 **Migración Alembic** `4ff85f833b29` (proveedor,
  orden_compra, orden_compra_item, recepcion_compra, recepcion_item)
  aplicada a la BD dev (Supabase).
- ✅ 2026-07-25 **Conformidad de comprobante** (`application/comprobantes.py`,
  permiso `purchases.dar_conformidad`): crea el `comprobante` recibido
  (transversal, `shared`), lo liga a la última `recepcion_compra` de la OC
  y publica `purchases.comprobante_conforme` — `accounting` encola el pago
  (ver slice pago a proveedor abajo).
- ⬜ **`cotizacion`**: hoy toda OC tipo `insumo` emite sin cotización
  comparativa (el camino "simplificado" de proveedor preferente es el
  único implementado). Falta el flujo normal (proveedor regular) con
  cotización de respaldo.
- ⬜ **OC tipo `activo` + `requerimiento_activo`**: doble aprobación
  (área + gerencia) y mínimo 2 cotizaciones vinculadas antes de emitir.
  Hoy el tipo está rechazado explícitamente en la capa de aplicación.
- ✅ 2026-08-29 **`compra_directa`** (ADR-082): compra a proveedor
  informal sin OC previa, sustentada solo con el comprobante recibido.
  Reutiliza `orden_compra` con `origen="directa"` — mismo contrato de
  eventos que ya consumen `inventory`/`accounting`, cero código nuevo ahí.
- ⬜ **Caja chica** (`caja_chica_compras`, `caja_chica_movimiento`,
  `rendicion_caja_chica`): `compra_directa` ya registra el gasto, pero
  sale por cuentas por pagar normal — el cargo a un fondo fijo con
  rendición semanal conciliada por `accounting` sigue sin modelar.
- ⬜ **Combobox de artículos con búsqueda server-side**: el selector de
  producto en OC y el importador de recetas piden `/inventory/articulos`
  con `page_size=200` fijo (2026-08-29) — funciona mientras el catálogo no
  pase de 200 filas. Si lo hace, hace falta un combobox que busque en el
  servidor en vez de traer todo de una.
- ⬜ **Reconciliación estilo Odoo entre compras/inventario/contabilidad**:
  hoy cada módulo se comunica solo por evento puntual (OC recibida,
  comprobante conforme); falta un tablero/flujo que concilie explícitamente
  qué OC, qué recepción y qué asiento corresponden entre sí, más allá de lo
  que cada evento ya deja escrito. Diferido — es un cambio de alcance
  arquitectónico, no un fix puntual.
- ⬜ **`evaluacion_proveedor`** automática (cumplimiento de plazo,
  conformidad, variación de precio) recalculada en cada recepción.
- ⬜ **`orden_compra` no queda marcada como pagada**: `accounting.pago_ejecutado`
  se publica pero `purchases` no lo escucha; `orden_compra.estado` no tiene
  un valor para "pagada" todavía (RN-CMP-014 vive hoy solo del lado de
  `accounting`).
- ⬜ **Listener `inventory.devolucion_a_proveedor`**: gestionar reclamo/
  nota de crédito con el proveedor (bloqueado por `devolucion` en
  inventory, ver arriba).
