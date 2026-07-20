# Módulo `sales` — Ventas y PDV

## Objetivo

Registrar ventas por sucursal en todos los canales (PDV humano, agente de IA,
delivery), cobrar (efectivo / Izipay) y emitir comprobantes
electrónicos vía Nubefact.

## Entidades

`producto_comercial`, `receta`, `receta_item`, `lista_precio`, `venta`,
`venta_item`, `pago`, `comprobante`, `cliente`. Detalle en `docs/architecture/data-model.md` §3, §6.

## Casos de uso

- CRUD de productos comerciales y recetas (separados de artículos inventariables).
- Crear venta (carrito) → confirmar → cobrar → emitir comprobante.
- Venta por agente de IA: mismo contrato API, usuario tipo `agente_ia`.
- Anulación / nota de crédito (con permiso y auditoría).
- Precios por sucursal/canal mediante listas de precio.
- `lista_precio` con flag `es_promocional` + `vigencia_inicio`/`vigencia_fin`:
  al vencer, el precio regular se restaura automáticamente sin intervención
  manual (soporta el flujo de Comercial de ofertas/promociones con fin
  obligatorio).
- Cálculo de margen de contribución por producto (`precio - costo_variable`,
  donde `costo_variable` = costo de receta vía `inventory` + empaque +
  comisión de canal) expuesto a Comercial para su evaluación de precio —
  el módulo calcula, Comercial decide y aprueba el precio final.

## Reglas

- Confirmar venta exige stock suficiente de los insumos de la receta (o política
  configurable de venta sin stock, por definir).
- `idempotency_key` obligatoria al confirmar venta y al registrar pago.
- Comprobante se encola a Nubefact (worker Celery, reintentos); la venta no se
  bloquea por caída del proveedor.
- El PDV usa el branding de la marca de la sucursal (config del módulo de ajustes).
- Cambio de precio regular pasa por `lista_precio` nueva versión, nunca
  edición directa del precio vigente (auditable, igual que OC en
  `purchases`); ligado a la ficha de evaluación de margen de Comercial.

## Flujo

Producto comercial → receta → confirmar venta → evento `sales.venta_confirmada`
→ inventory descuenta insumos del almacén del local → pago → comprobante.

## Relaciones

- Publica: `sales.venta_confirmada`, `sales.venta_anulada`, `sales.pago_registrado`,
  `sales.comprobante_emitido` (respuesta OK de Nubefact),
  `sales.carrito_abandonado` (analítica de embudo, RN-COM-013).
- Escucha: nada (consulta stock vía contrato público de inventory).
- Integraciones: Nubefact, Izipay, Meta API (pedidos por WhatsApp).
