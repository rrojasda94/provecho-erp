- **La comida del personal ya se registra: precio cero, costo a gasto**
  (2026-08-09, ADR-034, RN-COM-025/026/027). El grupo alimenta a su gente en
  fines de semana, feriados y días de alta actividad, y eso no existía en
  ningún lado: el costo desaparecía dentro del costo de ventas.
  - Una orden de `tipo="consumo_personal"` se prepara y despacha como
    cualquier pedido —comanda con `** CONSUMO PERSONAL **`, distintivo en el
    KDS, entrega— pero **nace con todas sus líneas en cero**: no se consulta
    lista de precios y **tampoco se acepta el precio que mande el cliente**.
    No se cobra (409), no admite descuento (409) y no emite comprobante.
  - **Por qué no fue un descuento del 100% con motivo `colaborador`**, que ya
    existía y habría sido una línea: esa venta publica
    `sales.venta_confirmada`, que `accounting` asienta como ingreso y
    `marketing` atribuye a una campaña; además no se puede cerrar
    (`registrar_pago` exige `monto > 0` e igualdad exacta) y al cobrarse
    emitiría una boleta de S/ 0.00 a SUNAT. Por eso hay evento propio
    (`sales.consumo_personal_registrado`) y un estado terminal nuevo,
    `cerrada`, que pone la entrega: es el único cierre posible de algo que
    nunca pasa por caja.
  - **El costo sí llega**: sale del almacén con `tipo_movimiento` nuevo
    `consumo_interno` —separado de `consumo_venta` porque no tiene ingreso
    detrás—, `inventory` lo valoriza al `costo_promedio` sobre las mismas
    líneas que movieron el stock (mismo criterio que la merma: valoriza quien
    conoce el movimiento) y `accounting` lo asienta por `regla_asiento` como
    gasto de alimentación de personal. Anular el consumo repone el insumo
    **y reversa el asiento**, o el gasto quedaría inflado por comida que
    nadie comió.
  - Lo **autoriza un encargado con su PIN** (permiso propio
    `sales.registrar_consumo_personal`, separado de `sales.crear`) y exige
    motivo de un enum cerrado (`fin_semana`, `feriado`, `alta_actividad`,
    `capacitacion`, `otro`) — es comida gratis: sin firma cualquiera se
    sirve, y un motivo de texto libre no agrupa el gasto por causa.
  - **No se registra quién comió**, por decisión del negocio: se alimenta al
    turno. La columna nullable puede agregarse después sin romper nada.
  - Costo aceptado: el asiento depende de que la empresa configure sus dos
    cuentas y la regla; sin ella el consumo queda en el movimiento de
    inventario y en el log, como todo el resto de la generación automática.
    El reporte formal por sucursal/mes queda como deuda — hoy se lee por
    `GET /sales/ventas?tipo=consumo_personal`.
