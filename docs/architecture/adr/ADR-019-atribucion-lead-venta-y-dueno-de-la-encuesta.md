# ADR-019 — Atribución lead→venta y dueño de la encuesta de satisfacción

- Estado: aceptado
- Fecha: 2026-08-01

## Contexto

Al implementar el slice core de `marketing` aparecieron dos cruces con
`sales` que la documentación previa resolvía de una forma que el código no
podía sostener.

**1. Quién escribe `lead.venta_id`.** `events.md` listaba a `sales` como
consumidor de `marketing.lead_generado`, con la nota "sales lo enlaza a la
venta cuando Comercial cierra". Eso obliga a `sales` a escribir una columna
de una tabla de `marketing` — exactamente lo que CLAUDE.md prohíbe ("nunca
importar el dominio de otro módulo"). Además invierte la dirección natural:
el hecho que dispara la atribución es la venta, y la venta ocurre *después*
del lead, así que el evento útil va en el otro sentido.

**2. Dónde vive `encuesta_satisfaccion`.** La tabla estaba descrita en
data-model §6 (ventas) porque su disparador es `sales.venta_entregada`,
pero §8d ya decía que pertenece a marketing. Ambigüedad a resolver antes de
crear la tabla.

**3. Cuánta atribución automatizar.** La tentación es atribuir siempre: si
el cliente tiene leads abiertos, marcar el más reciente. Pero `lead.venta_id`
no es un dato de conveniencia — es *la* métrica por la que existe una
campaña ("el valor de la campaña se mide por leads con `venta_id` no nulo,
no por volumen bruto", data-model §8d). Un dato inventado ahí no es un dato
incompleto: es un número que hace ver bien a la campaña equivocada.

## Decisión

**1. La atribución la hace `marketing`, escuchando `sales.venta_confirmada`.**
`marketing/application/listeners.py` es dueño de la escritura de
`lead.venta_id`; `sales` no escucha `marketing.lead_generado` y no conoce a
marketing. `sales.venta_confirmada` suma `cliente_id` al payload (cambio
compatible: agregar campos está permitido por las convenciones de
`events.md`). `marketing.lead_generado` queda como evento informativo/BI,
sin consumidor.

**2. La atribución automática solo actúa sin ambigüedad.** Se atribuye
cuando el cliente tiene **exactamente un** lead abierto (`venta_id` nulo) en
una campaña **en curso**. Con dos o más, el listener no escribe nada y
loguea; esos casos se resuelven por `POST /marketing/leads/{id}/atribucion`,
que exige `marketing.lead_gestionar`. Una campaña cerrada no se lleva
crédito nuevo.

**3. `encuesta_satisfaccion` es tabla de `marketing`.** Su disparador
(`sales.venta_entregada`) no la hace de ventas: quien decide a qué venta
entregada encuestar es Marketing, no la caja (RN-COM-007). data-model §6
mantiene la descripción por ser donde nace el disparador, apuntando a §8d.

**4. `marketing` lee el estado de entrega por contrato público.** Función
nueva `sales/application/queries_publicas.py::venta_para_encuesta`, que
devuelve sucursal, cliente y si el pedido ya se entregó. `marketing` nunca
importa `Venta`/`VentaItem`. La sucursal que devuelve es además la que
escopa el tenant de la encuesta (ADR-004), que no tiene `empresa_id` propio.

## Alternativas descartadas

- **`sales` escucha `marketing.lead_generado` y escribe `lead.venta_id`**
  (lo que decía `events.md`): rompe la frontera de módulos y pone la lógica
  de medición de campañas dentro de ventas.
- **Atribuir siempre al lead más reciente**: convierte una métrica en una
  suposición. El costo del error no es un registro perdido sino una decisión
  de presupuesto tomada sobre una conversión que nunca ocurrió.
- **Una tabla read-model de ventas entregadas dentro de marketing**,
  poblada por `sales.venta_entregada`: duplica estado que ya vive en
  `venta_item.estado_preparacion` y hay que mantener en sincronía. El
  contrato público resuelve lo mismo con una consulta.
- **Crear la encuesta automáticamente al entregar**: contradice RN-COM-007
  (selectiva) y llenaría la tabla de filas que nadie va a enviar.

## Consecuencias

- `lead.venta_id` puede quedar sin llenar aunque la venta haya ocurrido:
  es deliberado — un hueco visible es preferible a un número falso.
  La atribución manual es parte del proceso de Marketing, no un parche.
- `marketing` depende de `sales` en una dirección (lectura por contrato
  público + escucha de evento); `sales` no depende de `marketing`. La
  dependencia es acíclica y `marketing` sigue siendo removible.
- Agregar `cliente_id` a `sales.venta_confirmada` es compatible: los
  consumidores existentes (`inventory`, `accounting`) lo ignoran.
