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
el cobro.** Lo que pasa después (preparación, entrega, encuesta) quedó
fuera — ver `workflows.md` y `state-machines.md`, sección "fuera de
Venta". CU-COM-003 (antes: encuesta) se retira de este documento por esa
razón — se retoma cuando exista el proceso de cumplimiento de pedido.

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
