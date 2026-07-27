# Casos de uso

Casos de uso concretos por proceso — el "quién hace qué, en qué orden,
qué puede salir mal" que conecta [workflows.md](workflows.md) (el proceso
general) con [business-rules.md](business-rules.md) (las reglas que cada
paso debe cumplir). Se documentan por slice vertical de proceso, no todos
de una vez (ver `ROADMAP.md`).

Formato: `CU-<área>-nnn`, actor principal, precondición, flujo principal
(pasos numerados), flujos alternos/excepción, postcondición, reglas y
eventos relacionados. El CU hereda la versión del proceso que implementa —
nomenclatura y reglas de versionado en
[process-nomenclature.md](process-nomenclature.md).

## Venta

Implementa `PROC-COM-001` v1.0.

**Alcance (2026-07-14): Venta termina con el envío del pedido a cocina y
el cobro.** Lo que pasa después (preparación, entrega, encuesta) vive
desde 2026-07-27 en `PROC-OPE-002` — ver [Cumplimiento de
pedido](#cumplimiento-de-pedido) más abajo, CU-OPE-001/002/003.

> Relato base de esta sección: descripción del usuario 2026-07-14 de la
> experiencia real en los 3 canales, desde que el cliente decide contactar
> a una marca hasta el envío del pedido a cocina.

### CU-COM-001 — Web

- **Actor**: cliente (autoatención).
- **Precondición**: ninguna — puede entrar sin cuenta.
- **Flujo principal**:
  1. Ingresa con sus datos o se registra.
  2. Explora productos y promociones.
  3. Agrega productos al carrito.
  4. Al ir a pagar, elige primero modalidad: recojo en sucursal o delivery.
  5. Completa datos requeridos según modalidad (sucursal de preferencia, o
     dirección si delivery) — RN-COM-008.
  6. Upsell de productos relacionados/nuevos. Acepta → se agregan al
     carrito. No acepta → pasa a pasarela de pago.
  7. Elige tipo de comprobante (boleta/factura).
  8. Realiza el pago → se emite comprobante.
  9. Pedido enviado a la sucursal — **fin de Venta**.
  10. Recibe rango de tiempo aproximado para que el pedido esté listo.
- **Flujos alternos**:
  - Desistimiento en cualquier paso — el paso exacto se registra
    (`sales.carrito_abandonado`, RN-COM-013) para analizar dónde ocurren
    más abandonos.
- **Postcondición**: venta `pagada`/`facturada`, comprobante emitido,
  pedido enviado a sucursal.
- **Relacionado**: RN-COM-001/005/006/008/013, `sales.venta_confirmada`,
  `sales.comprobante_emitido`, `sales.carrito_abandonado`.

### CU-COM-002 — Central de Pedidos (llamada o WhatsApp)

- **Actor**: agente humano o agente de IA.
- **Precondición**: cliente contacta por llamada o WhatsApp.
- **Flujo principal**:
  1. Saludo de bienvenida de la marca.
  2. Pregunta si es cliente registrado.
     - Sí → pide DNI o teléfono, valida contra el sistema.
     - No → toma los datos del cliente (RN-COM-008: teléfono + nombre de
       referencia obligatorios para takeout/delivery; dirección exacta
       si delivery).
  3. Pregunta delivery o recojo en sucursal → según respuesta, selecciona
     dirección o sucursal.
  4. Pregunta si ya sabe su pedido o requiere la carta.
     - Requiere carta → se revisa en la web o se envía por WhatsApp.
     - Sabe su pedido → se solicita y arma el carrito.
  5. Upsell de productos/promociones relacionadas. Acepta → se agrega al
     carrito. No acepta → pasa a medio de pago.
  6. Se presenta el precio completo de la orden — **antes de esto**, el
     agente repite el pedido completo al cliente (RN-COM-009).
  7. Cliente elige medio de pago: link de pago, pagar a domicilio (contra
     entrega), o pagar al recoger en sucursal.
  8. Pedido enviado a cocina de la sucursal seleccionada — **fin de
     Venta**.
  9. Se entrega tiempo promedio para recoger/esperar.
  10. Comprobante emitido — se recibe al recoger el pedido, o digital por
      WhatsApp.
- **Flujos alternos (desistimiento y resolución)**:
  - Al llamar, número equivocado → fin sin venta.
  - Al pedir un producto: sin stock, no disponible, o no está en el menú
    → ofrecer alternativas antes de dar la venta por perdida (RN-COM-010).
  - Al recibir el monto total, precio no conveniente → ofrecer opciones
    similares más económicas o una promoción (RN-COM-011).
  - Al recibir el tiempo de espera, si es mucho → sugerir recojo en otra
    sucursal, o cambiar delivery por recojo (RN-COM-012).
- **Postcondición**: venta `pagada`/`facturada` (o pago pendiente contra
  entrega/recojo), comprobante emitido o pendiente de entrega física.
- **Relacionado**: RN-COM-001/005/006/008/009/010/011/012/013, Central de
  Pedidos (vision.md), `sales.venta_confirmada`, `sales.comprobante_emitido`,
  `sales.carrito_abandonado`.

### CU-COM-003 — Sucursal (mesa, takeout o delivery presencial)

- **Actor**: trabajador (atención al cliente / cajero).
- **Precondición**: sucursal con POS abierto (caja aperturada, RN-POS-003).
- **Flujo principal**:
  1. Cliente se acerca a mesa o mostrador; recibe saludo de bienvenida.
  2. Se pregunta tipo de pedido: comer en local, takeout, o delivery
     (sí — delivery puede iniciarse presencialmente).
  3. Pregunta si es cliente registrado.
     - Sí → solicita DNI o teléfono.
     - No → toma los datos (RN-COM-008 aplica igual si es takeout/delivery).
  4. Se presenta la carta (física o en pantalla).
  5. Cliente elige productos; el trabajador arma el carrito en el ERP.
  6. Upsell de productos relacionados/promociones. Acepta → suma al
     carrito. No acepta → procede al pago.
  7. Trabajador presenta el total — **antes de esto**, repite el pedido
     completo al cliente (RN-COM-009).
  8. Cliente presenta medio de pago; trabajador lo recibe y pregunta tipo
     de comprobante — si boleta, solicita DNI.
  9. Se efectúa el pago.
  10. Se envía la orden a cocina — **fin de Venta**.
  11. Se indica al cliente el tiempo de espera.
- **Flujos alternos**:
  - Producto sin stock/no disponible → ofrecer alternativas (RN-COM-010).
  - Cliente esperaba una promoción que no existe → desiste (sin
    resolución definida todavía, a diferencia de precio en Central de
    Pedidos).
  - **Mesa**: el cliente puede optar por pagar al finalizar el consumo en
    vez de al instante, porque puede seguir consumiendo más (RN-POS-005).
- **Postcondición**: venta `pagada`/`facturada`, comprobante emitido,
  pedido enviado a cocina.
- **Relacionado**: RN-COM-001/005/006/008/009/010, RN-POS-005,
  `sales.venta_confirmada`, `sales.comprobante_emitido`.

### Transversal a los 3 canales

- Datos sensibles (nombre completo, DNI) opcionales salvo excepciones —
  ver RN-COM-008.
- Confirmación verbal del pedido completo antes de dar el precio —
  RN-COM-009 (web queda exenta: el carrito ya es visual/editable).
- El abandono se registra en cualquier canal/paso — RN-COM-013.

## Cumplimiento de pedido

Implementa `PROC-OPE-002` v1.0. Los tres casos comparten la etapa de
preparación y se separan recién en el despacho, por modalidad de consumo —
por eso son un proceso con tres variantes y no tres procesos.

### CU-OPE-001 — Mesa

- **Actor**: personal de cocina (preparación) y de atención al cliente
  (entrega en mesa).
- **Precondición**: venta confirmada en modalidad `mesa`; la Orden de
  Pedido está en el KDS de la sucursal.
- **Flujo principal**:
  1. Cada estación ve en su pantalla los ítems de sus categorías y los
     avanza a `en_preparacion` al empezar (RN-CUP-002).
  2. Al terminar cada ítem lo marca `listo`.
  3. Con todos los ítems listos, el pedido aparece en la pantalla de
     despacho (`sales.pedido_listo`).
  4. Se emplata; se consume el empaque de mesa si el producto lo define
     (RN-EMP-003).
  5. Quien despacha verifica el pedido completo contra la comanda
     (RN-CUP-004).
  6. Se lleva a la mesa indicada en `referencia_atencion` y se entrega
     (RN-CUP-005) — **fin del cumplimiento**.
  7. Si el cliente sigue consumiendo, el servicio queda abierto: cada
     pedido adicional repite este ciclo sobre su propia venta.
- **Flujos alternos**:
  - Producto rechazado por el cliente en la mesa (frío, equivocado) →
    reproceso inmediato o devolución; se registra el motivo (RN-CUP-010).
  - Cliente se retira sin pagar teniendo pago pendiente → el cajero
    reporta de inmediato (RN-MDP-005).
- **Postcondición**: todos los ítems en `entregado`, `sales.venta_entregada`
  emitido; si el pago quedó para el final, la venta queda habilitada para
  cobro (RN-POS-005, RN-CUP-009).
- **Relacionado**: RN-CUP-001..006/009/010, RN-POS-005, RN-EMP-003,
  `sales.pedido_listo`, `sales.venta_entregada`.

### CU-OPE-002 — Takeout (recojo en sucursal)

- **Actor**: personal de cocina y de atención al cliente (mostrador).
- **Precondición**: venta confirmada en modalidad `takeout`, con teléfono
  y nombre de referencia del cliente (RN-COM-008).
- **Flujo principal**:
  1. a 3. Igual que CU-OPE-001 (preparación por estación hasta pedido listo).
  4. Se empaca para llevar, consumiendo el empaque de takeout (RN-EMP-003).
  5. Verificación contra comanda (RN-CUP-004).
  6. Se llama al cliente por número de orden en el mostrador.
  7. Se entrega y, si el pago quedó pendiente, se cobra antes de entregar
     (PROC-COM-002) — **fin del cumplimiento**.
- **Flujos alternos**:
  - Cliente no llega: el pedido queda en espera; pasado el plazo definido
    por la sucursal se escala al encargado, que decide resguardo, merma o
    anulación con devolución (RN-CUP-011).
  - Cliente llega antes de que el pedido esté listo → se le informa el
    tiempo restante desde el avance real del KDS.
- **Postcondición**: ítems en `entregado`, `sales.venta_entregada` emitido.
- **Relacionado**: RN-CUP-001..006/011, RN-COM-008, RN-EMP-003,
  PROC-COM-002.

### CU-OPE-003 — Delivery

- **Actor**: personal de cocina, despachador y repartidor (propio o de
  plataforma externa).
- **Precondición**: venta confirmada en modalidad `delivery`, con
  teléfono, nombre de referencia y dirección exacta (RN-COM-008).
- **Flujo principal**:
  1. a 3. Igual que CU-OPE-001 (preparación por estación hasta pedido listo).
  4. Se empaca para transporte, consumiendo el empaque de delivery
     (RN-EMP-003).
  5. Verificación contra comanda (RN-CUP-004).
  6. Se asigna repartidor: propio, o de plataforma externa — en cuyo caso
     se registra la plataforma y no hay vínculo laboral ni gestión de
     vehículo (RN-PER-003, RN-CUP-007).
  7. El repartidor sale con el pedido y la referencia de entrega.
  8. Entrega en el domicilio; si el cobro es contra entrega, lo ejecuta
     el repartidor y responde por el monto completo ante el cajero
     (PROC-COM-002, RN-MDP-005) — **fin del cumplimiento**.
- **Flujos alternos**:
  - Cliente ausente o dirección errada → el repartidor intenta contacto
    telefónico; sin respuesta, retorna el pedido y se registra el motivo
    del fallo (RN-CUP-008); el encargado decide devolución o merma.
  - Cliente rechaza el pedido en la puerta → devolución con motivo
    (RN-CUP-010).
  - Incidente en ruta (accidente, avería) → se reporta de inmediato y se
    reasigna el pedido si es recuperable.
- **Postcondición**: ítems en `entregado`, `sales.venta_entregada` emitido
  con el repartidor registrado; o pedido no entregado, con motivo.
- **Relacionado**: RN-CUP-001..008/010, RN-COM-008, RN-PER-003,
  RN-MDP-005, RN-EMP-003, PROC-COM-002.

### Transversal a las 3 modalidades

- El avance de preparación es único y compartido entre pantallas: lo que
  ve despacho es el estado real, no una copia (RN-CUP-003).
- Nunca se retrocede un estado; una corrección se registra como incidencia,
  no reescribiendo el avance (RN-CUP-002).
- La entrega es el disparador de la encuesta de satisfacción, que Marketing
  decide caso por caso (RN-COM-007) — no es automática.
