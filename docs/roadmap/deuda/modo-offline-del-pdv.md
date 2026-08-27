# Deuda técnica — Modo offline del PDV (tras la fase 2 de 2026-07-27 — ADR-009)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ✅ **Cambio previo a la fase 2** (2026-07-27): `crear_venta`,
  `registrar_pago` y `registrar_movimiento` aceptan `id` opcional
  client-generado; sin migración, como estaba previsto.
- ✅ **Motor de sync real** (2026-07-27): push→pull por ciclo, contrato
  declarativo por módulo, watermark por recurso, runner en su propio
  contenedor.
- ✅ **Cuenta de servicio por sucursal** (2026-07-27): rol `hub_sucursal`
  en el seeder y alta con `python -m src.seeders.hub`.
- ⬜ **Un ítem que la nube rechaza frena su recurso hasta que alguien lo
  mire**: es la política elegida (perder una venta en silencio es peor),
  pero hoy el único aviso es `ultimo_error` en `/health/sync`. Falta que el
  monitor externo alerte sobre eso, o una bandeja de ítems en conflicto.
- ⬜ **El borde del watermark se vuelve a bajar en cada ciclo**: el pull
  usa `campo_marca >= desde` para no perder nunca una fila escrita en el
  mismo instante que la marca, y `now()` en Postgres es el reloj de la
  transacción — así que un catálogo sembrado de una sola vez y nunca
  tocado viaja entero en cada ciclo. Con el tamaño de un catálogo de
  restaurante son cientos de KB por minuto; si el enlace de algún local lo
  siente, la salida es paginar por cursor compuesto `(marca, pk)`.
- ⬜ **Nada alerta si un hub deja de sincronizar**: `/health/sync` expone
  `ultimo_ok` por recurso, pero no hay nadie mirándolo. Mismo pendiente que
  la alerta de backups.
- ⬜ **`venta_item.estado_preparacion` no viaja a la nube**: el avance de
  KDS es local al local (y sus ítems no conservan `id` entre lados). Si
  alguna vez se quieren tiempos de cocina consolidados por grupo, hay que
  resolverlo aparte.
- ⬜ **`agregar_lineas`, `anular_lineas` y `mover_lineas` (2026-08-27,
  RN-COM-043, ADR-070) no tienen verbo de replay**: `sincronizacion.py` solo
  reproduce crear/cobrar/anular una venta **completa**. Una orden que en el
  hub sumó líneas, quitó líneas o movió productos entre pedidos durante un
  corte de enlace no reproduce esos cambios al reconectar — `_crear` es
  idempotente por `id`/`idempotency_key`, así que la venta ya sincronizada
  simplemente no vuelve a tocarse. Se agrava en `mover_lineas` porque
  identifica líneas por `venta_item.id`, y esos ids **no son estables entre
  el hub y la nube** (bullet anterior): un traslado no tendría ni contra qué
  ids replayarse. Resolverlo exige el mismo trabajo para los tres verbos:
  un cuarto tipo de lote en `pendientes()`/`aplicar()`, ordenado después de
  `_aplicar_ventas`.
- ⬜ **`cliente` no se replica**: una venta offline es anónima o con datos
  escritos a mano; vender a cliente registrado exige estar en línea.
- ⬜ **`receta`/`receta_item` viajan sin filtro de tenant**: no tienen
  columna de empresa y acotarlas exigiría cruzar `producto_comercial`
  (dominio de `sales`) desde `inventory`. Aceptable mientras el grupo opere
  empresas que pueden verse entre sí; si eso cambia, `receta` necesita su
  columna de tenant antes que este sync.
- ⬜ **Descubrimiento del hub en la LAN** (mDNS `sucursal.local` o IP fija
  configurada por dispositivo): decisión de cliente, no resuelta en el
  backend.
- ⬜ **Redundancia del hub**: si el Raspberry Pi mismo se cae, la sucursal
  pierde el PDV entero — no hay hub de respaldo. Aceptado como riesgo por
  ahora (ADR-009); mitigación futura: imagen lista para flashear en un
  repuesto.
- ⬜ **Ningún frontend construido todavía**: web, Android y PC son proyectos
  aparte, ahora con contrato de arquitectura para construir contra él.
- ⬜ **Migraciones en cada hub**: un hub offline por días necesita
  `alembic upgrade head` local antes de sincronizar contra un esquema de
  nube ya migrado — mismo runbook que la nube (ADR-008), sin automatizar
  todavía por sucursal.
