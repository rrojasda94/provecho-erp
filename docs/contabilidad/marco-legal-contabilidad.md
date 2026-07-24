# Marco legal — Contabilidad (Grupo Majambo)

Contexto tributario y contable peruano que condiciona los procesos del área.
No sustituye la asesoría del contador externo; fija el terreno común para
diseñar el ERP y los SOPs.

> Los importes, tasas y umbrales concretos viven en configuración, no en este
> documento — cambian por norma o por año fiscal. Aquí se describe el
> mecanismo, no el número vigente.

## Régimen y empresa

- El grupo opera varias empresas (ver [datos Majambo](../../CLAUDE.md) y el
  área de RRHH); cada empresa tiene su propio RUC y emite comprobantes con
  serie y correlativo **propios, que nunca se repiten dentro de la empresa**
  (ver Comprobante de Pago en el [glosario](../foundation/glossary.md)).
- Régimen tributario de cada empresa (según nivel de ingresos): define tasa de
  renta, obligación de libros y periodicidad. El contador externo confirma el
  régimen vigente de cada RUC.

## IGV y Régimen de Amazonía

- Varias operaciones se benefician del **Régimen de Amazonía** (exoneración o
  tasa reducida de IGV según zona y actividad). Ya considerado en el
  [marco legal de Compras](../compras/marco-legal-compras.md); del lado
  contable determina cómo se registra el IGV de compras y ventas.
- El crédito fiscal de IGV solo se toma con comprobante válido y anotado en el
  registro de compras dentro del plazo — refuerza "sin comprobante no hay
  registro".

## Comprobantes de pago

- La empresa **emite** boleta/factura electrónica (vía Nubefact, ver
  [ADR-003 / integraciones](../../CLAUDE.md)); **acepta** factura, recibo por
  honorarios (RHE) y, excepcionalmente, boleta/ticket de compra.
- Sin comprobante emitido no hay venta (regla comercial); sin comprobante
  válido recibido no hay pago ni crédito fiscal (regla de este marco).
- Los comprobantes electrónicos se resguardan digitalmente; los físicos
  aceptados se archivan y se conservan por el plazo legal.

## Detracciones (SPOT)

- Ciertos servicios y bienes obligan a **detraer** un porcentaje del pago y
  depositarlo en la cuenta de detracciones del proveedor antes o al pagar.
- El proceso de **pago a proveedor** (PROC-CTB-003) verifica si la operación
  está sujeta a detracción y ejecuta el depósito correspondiente; el
  incumplimiento hace perder el crédito fiscal y genera multa.

## Libros y registros electrónicos

- Según el régimen, la empresa lleva registro de ventas, registro de compras y
  libros electrónicos (SLE/SIRE) con la periodicidad que fije SUNAT.
- El ERP es la **fuente** de los movimientos; el contador externo consolida y
  presenta. El cierre de periodo (RN-CTB-002) fija los datos que alimentan los
  libros de ese mes.

## Plazos y contador externo

- Las obligaciones mensuales (declaración de IGV-Renta, PLAME con RRHH,
  detracciones) siguen el cronograma SUNAT según el último dígito del RUC.
- El grupo trabaja con **contador externo**: Contabilidad entrega la
  información completa y a tiempo (PROC-CTB-011, propuesto); el externo declara
  y presenta. Una fecha límite próxima es una alerta en el ERP.

## Activo fijo y depreciación

- Los bienes de uso duradero (equipamiento, vehículos, mobiliario) son
  **activos no corrientes**: se registran, se deprecian según la tasa que
  corresponda a su tipo y se dan de baja al final de su vida útil o por venta.
- La compra de un activo cruza con Compras y Gerencia antes de ejecutarse
  (ver [área de Compras](../compras/README.md), camino 3); el alta contable y
  la depreciación son de este área (PROC-CTB-010, propuesto).
- Los vehículos tienen tratamiento específico (depreciable, combustible,
  mantenimiento) — ver Vehículo en el [glosario](../foundation/glossary.md).
