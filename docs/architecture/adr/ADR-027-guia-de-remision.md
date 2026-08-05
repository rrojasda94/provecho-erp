# ADR-027 — La guía de remisión vive en `inventory` y se deriva del traslado

Fecha: 2026-08-05
Estado: aceptada

## Contexto

Charlie's Pizzas mueve mercadería todos los días: del almacén central a CH1
y CH2, entre locales, y de vuelta al central con lo que sobra. Cada uno de
esos traslados necesita una guía de remisión que viaje con la carga
(RN-GDR-001), la emite el área de almacén (RN-GDR-002) y la resguarda
contabilidad (RN-GDR-003). Sin ella, la mercadería en la carretera es
mercadería sin sustento.

El ciclo de traslado ya estaba construido: `solicitud_insumos` → reserva →
`transferencia` con despacho FEFO → recepción (ADR-020). Lo único que
faltaba era el documento.

Dos planes anteriores apuntaban a otro lado y hay que descartarlos
explícitamente:

- El ROADMAP de julio declaraba un **módulo `logistics`** futuro que se
  quedaría con transporte y guías.
- ADR-005 anotaba `despatch-*` de Factiliza como "futuro módulo
  `logistics`".

## Decisión

**1. La guía vive en `inventory`, no en un módulo nuevo ni en `sales`.**

Lo que la guía declara es un traslado, y el traslado es un hecho de
inventario: qué SKU salió, de qué almacén, en qué cantidad. Un módulo
`logistics` habría necesitado importar el dominio de `inventory` (stock,
lote, FEFO) para poder llenar la guía, y CLAUDE.md lo prohíbe. Emitirla
desde `sales` tiene el mismo problema al revés: `sales` conoce
comprobantes, no almacenes.

Que sea un documento de SUNAT no la hace de `sales`. `comprobante` está en
`shared` justamente porque el emisor cambia según el caso; la guía no
necesita eso todavía porque hoy la emite un solo lado.

**2. Las líneas se derivan de `transferencia_item`, no se teclean.**

RN-TRP-002 exige que lo transportado coincida exactamente con lo declarado.
Un formulario de ítems aparte es, literalmente, la forma de que no
coincidan: bastaría un dedo distraído para que la guía diga 8 cajas y en el
camión vayan 10. Se teclea solo lo que el sistema no puede saber —quién
maneja, en qué vehículo, cuánto pesa la carga, qué día arranca el viaje.

**3. Las líneas se agrupan por SKU, no por lote.**

El despacho reparte por FEFO y una línea de 10 kg puede salir de tres lotes
(ADR-015). Eso es control interno: SUNAT declara producto y cantidad. La
trazabilidad por lote sigue completa en `transferencia_item`, que es donde
sirve para un retiro de producto. Declarar los lotes en la guía habría
triplicado líneas sin agregar información fiscal.

**4. No hay entidad `vehiculo`.**

Placa y datos del chofer viajan en la guía. El grupo no tiene flota propia
ni operación de reparto con ruteo (ver ROADMAP → la fila de módulos
futuros); una tabla de vehículos hoy sería un formulario que nadie
mantiene y que habría que llenar antes de poder emitir la primera guía.
Cuando exista flota, `vehiculo_placa` se reemplaza por su FK y las guías
viejas conservan la placa con la que viajaron, que es lo correcto.

**5. Un traslado, una guía; la numeración es por (empresa, serie).**

`transferencia_id` es único: dos guías del mismo traslado declararían la
misma mercadería dos veces, que ante una fiscalización es exactamente lo
que no se puede explicar. La emisión es idempotente — pedirla de nuevo
devuelve la misma. El correlativo se calcula **al emitir** y no se reserva
antes: una guía reservada que nunca se emite deja un hueco en la
numeración, y un hueco también hay que justificarlo.

**6. La emisión electrónica es asíncrona y no bloquea el traslado.**

Mismo patrón que el comprobante (ADR-005): la guía existe y se imprime
apenas se crea, en estado `pendiente`; el envío a Factiliza
(`POST /despatch/send`) va por Celery con reintentos. Un rechazo de SUNAT
es un veredicto del negocio —el dato está mal, hay que corregirlo y
reemitir—, no un error de transporte. El camión no espera a un proveedor
externo.

El mapper vive en `factiliza/guias.py`, **aparte de `mapper.py`**: una guía
no tiene aritmética tributaria (no declara valor de venta, ni IGV, ni forma
de pago) y tenerla en el mismo archivo que la factura invitaba a reusar el
cálculo de IGV sobre un documento que no cobra nada.

## Consecuencias

- Nuevas entidades `guia_remision` y `guia_remision_item` en `inventory`;
  migración `a4c8f21e6b09`.
- Permiso nuevo `inventory.emitir_guia`, en el rol `almacenero`
  (RN-GDR-002). Un cajero con `inventory.leer` no emite guías.
- Endpoints: `POST/GET /inventory/transferencias/{id}/guia` y
  `GET /inventory/guias-remision` (paginado, ADR-026).
- Eventos nuevos `inventory.guia_remision_emitida` y
  `inventory.guia_remision_emitida_sunat`, ambos sin consumidor todavía:
  contabilidad resguarda leyendo el listado (RN-GDR-003).
- `FactilizaClient.enviar_guia_remision` y una cola propia en
  `inventory.application.tasks`.
- Queda **fuera a propósito**: la guía de una venta con reparto a domicilio
  (hoy `transferencia_id` es obligatorio y no hay reparto propio), la
  descarga de PDF/XML/CDR de la guía, la anulación por comunicación de baja,
  y el `codigo_sunat` por unidad de medida — mientras solo la guía lo
  necesite, el diccionario del mapper es menos trabajo que una columna que
  alguien tiene que llenar. Todo declarado en ROADMAP → Deuda técnica.
- El payload de `/despatch/send` sigue el mismo estilo que el de
  `/invoice/send`, **pendiente de verificación contra el sandbox real de
  Factiliza** — igual que estuvo la boleta antes de su primera emisión.
