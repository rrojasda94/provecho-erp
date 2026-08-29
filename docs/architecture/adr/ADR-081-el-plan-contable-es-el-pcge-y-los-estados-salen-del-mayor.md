# ADR-081 — El plan contable es el PCGE y los estados financieros salen del mayor

- **Estado:** aceptada
- **Fecha:** 2026-08-29
- **Contexto:** `accounting` (plan de cuentas, asientos automáticos, reportes)
- **Relacionado:** [ADR-004](ADR-004-estrategia-tenant.md) (alcance por
  empresa), [ADR-071](ADR-071-mover-lineas-no-repone-inventario-ni-reclasifica-el-asiento.md)
  (por qué mover líneas no reclasifica el asiento), [ADR-034](ADR-034-consumo-de-personal.md)
  (la comida del personal es gasto, no costo de ventas).

## Contexto

El libro contable existía desde el slice de julio y era correcto en su
mecánica —partida doble, periodo inmutable, reversión por asiento inverso—
pero no servía para llevar la contabilidad de una empresa peruana:

1. **El plan de cuentas nacía vacío.** Cada empresa inventaba sus códigos.
   El Perú tiene un plan **obligatorio** —el Plan Contable General
   Empresarial (PCGE), versión modificada 2019, vigente desde el
   01/01/2020— y el contador externo trabaja con él. Un ERP que obliga a
   inventar el número de una cuenta que ya existe garantiza dos planes
   distintos: el del sistema y el del contador.
2. **`regla_asiento` solo sabía hacer asientos de dos líneas.** Una cuenta
   de debe y una de haber por (empresa, evento). Ningún asiento peruano
   real tiene dos líneas: una venta gravada son tres (cobrar, IGV,
   ingreso) y una compra son cinco, contando el asiento de destino que
   ingresa la mercadería al almacén. El IGV, que es la mitad de la
   obligación tributaria mensual, no aparecía en ninguna parte.
3. **No había estados financieros.** Ni balance de comprobación, ni libro
   mayor, ni Estado de Situación Financiera, ni Estado de Resultados. La
   pregunta «¿cómo está mi empresa?» no tenía dónde contestarse: había que
   exportar los asientos y sumarlos afuera.

## Decisión

### 1. El PCGE vive en código, no en configuración

`src/modules/accounting/domain/pcge.py` trae el catálogo oficial y
`POST /accounting/cuentas-contables/pcge` lo siembra en la empresa
(idempotente por código).

Esto contradice en apariencia el criterio del módulo —«la empresa configura,
el código no hardcodea su propio plan de cuentas»— y no lo contradice de
verdad: ese criterio protege **decisiones de la empresa**, y el PCGE no lo
es. Es una norma nacional, igual para las tres empresas del grupo y para el
contador externo. Lo que sigue siendo decisión de la empresa es qué cuentas
activa, cuáles agrega y qué mapeo usa para cada evento.

**Cobertura:** elementos 1 a 7 y 9 completos a nivel de rubro, con las
divisionarias que una operación de restaurante usa. Del elemento 8 se
siembran solo `87` y `88`, que son gasto del ejercicio; los saldos
intermediarios de gestión (`80`–`85`) y la determinación del resultado (`89`)
quedan fuera porque son cuentas de cierre anual que arma el contador y los
estados de este módulo calculan el resultado directo de los elementos 6, 7 y
9. El elemento 0 (cuentas de orden) queda fuera: no mueve activo, pasivo ni
resultado, y ningún proceso del ERP lo alimenta. Las dos omisiones están en
la deuda del ROADMAP.

**El elemento 9 es de denominación libre** según el propio PCGE. El ERP fija
la convención más difundida (91 costo de producción, 94 administración,
95 ventas, 97 financieros) y la deja escrita para que nadie la adivine.

### 2. Un asiento se imputa en la cuenta de último nivel

`crear_asiento_manual` rechaza una cuenta que agrupa a otras. Cargar contra
«42 Cuentas por pagar comerciales» deja el mayor sin decir contra qué
divisionaria, y el rubro pasa a tener movimiento propio además del de sus
hijas —el balance sigue cuadrando y el detalle deja de existir.

### 3. Plantillas de asiento del PCGE, con `regla_asiento` como override

`domain/plantillas.py` describe, por evento, el asiento oficial completo con
códigos del PCGE. Ejemplos:

| evento | asiento |
|---|---|
| `sales.venta_confirmada` | 1212 D total · 7011 H total |
| `sales.comprobante_emitido` | 7011 D IGV · 40111 H IGV |
| `purchases.compra_recibida` | 6011 D · 4212 H · **201 D · 611 H** (destino) |
| `purchases.comprobante_conforme` | 40111 D IGV · 4212 H IGV |
| `inventory.consumo_personal_valorizado` | 625 D · 201 H |
| `accounting.pago_ejecutado` | 4212 D · 1041 H |

El orden de resolución es: **`regla_asiento` de la empresa si existe, y si
no, la plantilla**. La empresa manda sobre el default de fábrica; quien no
configuró nada pasó de no tener asiento a tener el asiento correcto.

Si a la empresa le falta alguna de las cuentas de la plantilla (todavía no
importó el PCGE), el asiento se omite y se audita en el log — el mismo
criterio no bloqueante de siempre: contabilidad no puede impedir vender.

**`purchases.oc_emitida` no tiene plantilla a propósito.** Una orden emitida
es un compromiso, no un hecho contable; su lugar en el PCGE son las cuentas
de orden, que este catálogo no siembra. Quien igual quiera provisionarla lo
declara en su `regla_asiento`.

### 4. El IGV nace con el comprobante, y su régimen se elige

**Enmendado el 2026-08-29**, mismo cambio. La primera versión ponía el IGV en
el asiento de la venta confirmada y en el de la compra recibida, y sacaba la
tasa de `empresa.zona_tributaria`. Las dos cosas estaban mal:

- **la zona no alcanza para decidir el régimen.** La exoneración de Amazonía
  (Ley 27037) depende de zona **y actividad**, y no había dónde elegirla. Y
  no había forma de que una operación puntual se apartara del régimen: Grupo
  Majambo vende exonerado y aun así **compra con IGV** a proveedores de fuera
  de la región — crédito fiscal que no se registraba en ninguna parte;
- **el asiento salía antes de que se supiera el IGV.** La venta se asienta al
  confirmarse y la compra al recibirse, las dos antes de que exista el
  comprobante donde se marca si la operación va gravada.

**Tres niveles, resueltos en un solo lugar** (`src/shared/tributos.py`, que
reemplaza la misma condición copiada en el asiento contable y en el
comprobante electrónico): la casilla de la operación si alguien la marcó → el
default de la empresa (`empresa.config_fiscal["igv_por_defecto"]`, en su
ficha) → su zona tributaria. El último nivel es el comportamiento histórico,
así que desplegar esto no cambia de régimen a ninguna empresa viva.

**El IGV se reconoce con el comprobante.** El asiento de venta confirmada y el
de compra recibida van sin IGV; lo asientan `sales.comprobante_emitido` y
`purchases.comprobante_conforme`. No es un rodeo para esquivar el problema de
orden: es lo que exige el marco legal del área —el crédito fiscal solo se toma
con el comprobante válido y anotado en el registro de compras, y el débito
nace con el comprobante emitido—. De paso deja el flag en **una sola tabla**
(`comprobante.gravado_igv`, nullable) en vez de repartirlo entre `venta` y
`orden_compra`.

Cada plantilla declara qué trae el evento en su monto —`total` (con IGV, una
venta), `base` (sin IGV, una compra: `costo_unitario` es lo que `inventory`
usa para valorizar y el IGV de compras es crédito fiscal, no costo) o `neto`
(un costo ya valorizado, un pago)—.

El IGV se calcula **por diferencia contra el total**, nunca redondeando base
e IGV por separado: al redondearlos aparte la suma se aparta un céntimo de lo
que el cliente pagó, y el asiento no cuadra.

Con tasa cero las dos líneas del asiento de IGV valen 0 y **no se escribe**:
para una empresa exonerada, que es el caso de Majambo, el libro queda igual
que antes de esta enmienda.

De paso se corrigió el payload de `sales.comprobante_emitido`, que mandaba
`venta.total` en vez del importe de **su** grupo de cobro: con la cuenta
dividida (RN-COM-018) eso habría reconocido el IGV una vez por comprobante
sobre la venta entera.

### 5. Los estados financieros son consulta, no tabla

`balance_comprobacion`, `libro_mayor`, `estado_situacion_financiera` y
`estado_resultados` se calculan agregando `asiento_linea` en cada pedido. No
hay tabla de saldos: un saldo materializado es un segundo lugar donde vive la
verdad, y el día que se desincroniza del mayor nadie sabe cuál leer. Si la
agregación llega a pesar, el remedio es un índice o una vista materializada,
no una tabla que se escribe a mano.

El mapa rubro→línea del estado vive en `domain/estados_financieros.py` por el
mismo motivo que el PCGE: es el formato de presentación peruano (NIIF, forma
SMV), igual para toda empresa que lleve el plan oficial.

**Ninguna de las cuatro consultas filtra por `asiento.estado`.** Un asiento
anulado conserva sus líneas y su reversión existe como asiento aparte con las
líneas al revés: las dos juntas suman cero. Excluir el anulado y dejar la
reversión restaría el hecho **dos veces**. Se ve como un bug y es lo
correcto; hay una prueba que lo fija.

### 6. Un solo Estado de Resultados, por naturaleza

Sus líneas cubren **todos** los rubros de resultado, así que el número que
arroja es idéntico al que sale de sumar el libro entero — y la respuesta trae
las dos cifras (`resultado_ejercicio` y `resultado_libro`) más un `cuadra`
para que el descuadre se vea en la pantalla y no haya que buscarlo.

El estado **por función** (costo de ventas, gastos de venta, de
administración) queda fuera: necesita los asientos de destino del PCGE
—elemento 9 contra la 79— que hoy ningún proceso del ERP genera. Presentarlo
ahora daría un estado con la utilidad bruta como única línea real y todo lo
demás en cero, que no cuadra contra el mayor. Deuda anotada.

## Alternativas descartadas

- **Tabla `plan_contable_plantilla` en base de datos.** El PCGE cambiaría por
  norma, no por empresa: una tabla obliga a migrar datos en cada instalación
  para arreglar una denominación, y a que dos empresas del mismo grupo puedan
  tener catálogos distintos sin que nadie lo note. En código, el catálogo se
  versiona con el resto y una prueba lo verifica entero.
- **Ampliar `regla_asiento` a N líneas.** Es el camino "configurable" puro y
  exige que el usuario arme a mano el asiento peruano —cinco líneas con roles
  de base/IGV/total— antes de poder facturar. La plantilla da eso resuelto y
  `regla_asiento` sigue disponible para quien quiera otra cosa.
- **Sembrar el PCGE en el seeder.** Se descartó: mete 400 cuentas en toda
  base de desarrollo y de demo, incluidas las de los tests, que crean sus
  propias cuentas con códigos de rubro (`10`, `60`, `70`) y chocarían contra
  el catálogo. Importarlo es un botón en Plan de cuentas.
- **Materializar saldos por cuenta y periodo.** Ver punto 5.
- **Presentar los dos formatos del Estado de Resultados.** Ver punto 6: uno
  de los dos no cuadraría, y un estado financiero que no cuadra es peor que
  no tenerlo.

## Consecuencias

- El circuito contable por defecto es el de **mercaderías**
  (601 → 201 → 611 → 691 / 7011) y no el de producción
  (602 → 241 → 21 → 702). Un restaurante transforma insumos, así que el de
  producción sería el purista; el de mercaderías es el que puede sostenerse
  sin un sistema de costos por orden, que el ERP no lleva. La empresa que
  quiera el otro lo declara en su `regla_asiento`.
- **La cuenta por cobrar de la venta queda abierta.** El asiento carga 1212 y
  nada la cancela, porque `sales.pago_registrado` todavía no se publica. El
  balance cuadra igual —el activo está en «cuentas por cobrar» en vez de en
  «efectivo»— pero mientras el evento no exista, el efectivo del ciclo de
  caja y el libro contable no se tocan. Deuda ya anotada, ahora con
  consecuencia visible en el balance.
- **El costo de ventas (69) no se genera solo.** Necesita un evento
  valorizado de consumo por venta que `inventory` no publica
  (`inventory.stock_consumido` viaja sin monto). Mientras tanto el consumo se
  refleja por la vía del elemento 6: compras (60) contra variación de
  existencias (61), que es exactamente lo que el estado por naturaleza
  presenta.
- **El balance no distingue el ejercicio.** No existe el asiento de cierre
  anual que traslada el resultado a resultados acumulados, así que el
  resultado se presenta acumulado desde el inicio del libro, en su línea
  propia del patrimonio.
- **El corte corriente/no corriente se toma por rubro.** Separar la porción
  corriente de un préstamo exige la fecha de vencimiento de cada cuota, que
  el modelo no guarda; mientras tanto la 45 va entera a no corriente.
- El plan de cuentas no necesitó migración: el elemento y el nivel se
  derivan del código, y quién es hija de quién ya estaba en
  `cuenta_padre_id`. La enmienda del IGV sí trae una, de **una columna**
  nullable (`comprobante.gravado_igv`, `dfb195b14433`): todo lo ya emitido
  conserva el régimen con el que se emitió.
- **Una venta sin comprobante nunca reconoce IGV.** Es correcto —sin
  comprobante no hay venta— pero conviene saberlo: si la emisión a SUNAT
  falla, el débito fiscal queda pendiente hasta que se reemita.
- **`movimiento_dinero.monto` sigue siendo el total de la OC sin IGV**, así
  que el pago a un proveedor gravado se encola por menos de lo que dice su
  factura. Es anterior a este cambio y queda anotado en la deuda.
