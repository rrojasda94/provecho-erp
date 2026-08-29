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

- La empresa **emite** boleta/factura electrónica (vía Factiliza, ver
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

## Plan contable y estados financieros

- El **Plan Contable General Empresarial (PCGE)**, versión modificada 2019
  (vigente desde el 01/01/2020), es el catálogo de cuentas obligatorio. No es
  optativo ni sustituible por un plan propio: es el lenguaje con el que el
  contador externo lee los libros y con el que se arman las declaraciones.
- El ERP lo trae de fábrica y lo siembra por empresa (ADR-081). Sus elementos:
  1 activo disponible y exigible, 2 activo realizable, 3 activo inmovilizado,
  4 pasivo, 5 patrimonio, 6 gastos por naturaleza, 7 ingresos, 8 saldos
  intermediarios de gestión, 9 costos y gastos por función (**denominación
  libre**), 0 cuentas de orden.
- Los **estados financieros** se presentan bajo NIIF adoptadas en el Perú, en
  el formato que usa la SMV: Estado de Situación Financiera (activo corriente
  y no corriente contra pasivo y patrimonio) y Estado de Resultados. El ERP
  presenta el de resultados **por naturaleza**; el de por función necesita los
  asientos de destino del elemento 9 contra la 79, que hoy se hacen a mano.
- El **IGV** se registra en la 40111 (cuenta propia); en las empresas bajo el
  Régimen de Amazonía la venta sale exonerada y esa línea no existe. El
  régimen **por defecto** de cada empresa se elige en su ficha
  (Organización → Empresas), porque la exoneración depende de zona **y**
  actividad y el enum de zona solo no alcanza para decidirla.
- Una **operación puntual** puede apartarse de ese default: una compra a un
  proveedor de fuera de la región llega con IGV en la factura aunque la
  empresa venda exonerada, y ese crédito fiscal se registra. Se marca donde
  alguien tiene el documento delante — al cobrar en el PDV y al dar
  conformidad a la factura del proveedor.
- El IGV se reconoce **con el comprobante**, no con la operación: el crédito
  fiscal solo se toma con el comprobante válido y anotado en el registro de
  compras, y el débito nace con el comprobante emitido (ADR-081).

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
