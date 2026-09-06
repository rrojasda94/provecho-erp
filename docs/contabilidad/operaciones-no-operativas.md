# Plata que no viene de vender ni se va en comprar

Préstamos, premios de concurso, subvenciones y mover efectivo entre el banco y
la caja chica. **Hoy el ERP no modela ninguna de estas operaciones**: se
registran con el asiento manual de Contabilidad → Asientos → «+ Asiento
manual», y este documento dice exactamente cuál.

No es un parche provisorio disfrazado: el asiento manual es el instrumento
correcto para un hecho que pasa dos veces al año. Lo que sí falta —y está
anotado como deuda— es el control alrededor cuando pase seguido.

## Antes de empezar

- El **plan de cuentas tiene que estar importado**. Desde ADR-089 la empresa
  nace con él; una empresa anterior a ese cambio se arregla con
  `python scripts/sembrar_contabilidad.py` o con el botón «Importar PCGE» en
  Contabilidad → Plan de cuentas.
- El asiento se imputa **siempre en la cuenta de último nivel**, nunca en el
  rubro que la agrupa. `104` no se usa; se usa `1041`.
- Todo asiento cuadra debe contra haber (RN-CTB-001) y entra en el periodo de
  su fecha, que se abre solo (ADR-089) salvo que el mes ya esté cerrado.

## Los cuatro casos

### 1. Préstamo recibido

Entra la plata al banco y nace la deuda.

| Cuenta | | Importe |
|---|---|---|
| `1041` Cuentas corrientes operativas | Debe | monto recibido |
| `451` Préstamos de instituciones financieras y otras entidades | Haber | monto recibido |

Glosa sugerida: `Préstamo <entidad> <nº contrato>, desembolso`.

**Antes de firmarlo**, RN-EMP-006: todo préstamo de una empresa del grupo
requiere estudio de viabilidad previo del área contable —monto, motivo, tasas,
plazos— y lo aprueba Gerencia. El ERP no lo verifica; el control es del
proceso.

### 2. Cuota del préstamo

Se paga capital e interés juntos, y solo el interés es gasto.

| Cuenta | | Importe |
|---|---|---|
| `451` Préstamos de instituciones financieras | Debe | amortización de capital |
| `673` Intereses por préstamos y otras obligaciones | Debe | interés del periodo |
| `1041` Cuentas corrientes operativas | Haber | total pagado |

El **cronograma de cuotas no existe** en el ERP, así que la porción corriente
de la deuda (lo que vence dentro de los doce meses) no se separa sola: la `45`
va entera a no corriente en el estado de situación financiera y el contador
externo reclasifica. Está anotado como deuda.

### 3. Premio de concurso, subvención o donación

Es ingreso, no venta: no lleva IGV ni comprobante de venta.

| Cuenta | | Importe |
|---|---|---|
| `1041` Cuentas corrientes operativas | Debe | monto recibido |
| `7591` Subsidios gubernamentales | Haber | monto recibido |

Si el fondo llega con **destino restringido** —solo se puede gastar en lo que
dice la bases del concurso— el debe va a `107` Fondos sujetos a restricción en
vez de `1041`, y se traslada a `1041` a medida que se libera. Para una
donación privada la contrapartida es `7592` Donaciones; para un ingreso que no
es ninguna de las dos, `7599` Otros ingresos de gestión.

Los tres caen en «Otros ingresos de gestión» del estado de resultados, aparte
de las ventas — que es lo que se quiere: un premio no infla el margen del
negocio.

### 4. Retiro del banco para caja chica

| Cuenta | | Importe |
|---|---|---|
| `102` Fondos fijos | Debe | monto retirado |
| `1041` Cuentas corrientes operativas | Haber | monto retirado |

Y cuando la caja chica se gasta y se repone, el asiento es el gasto contra
`102`, no contra el banco.

**Lo que este asiento no hace, y hay que saberlo**: ese efectivo **queda sin
responsable nominal**. El circuito de custodia del ERP (ADR-025) cuelga de una
apertura de caja del PDV —`movimiento_caja` y `custodia_efectivo` llevan
`apertura_caja_id`—, así que plata que nace de un retiro bancario no tiene
dónde colgarse: nadie firma que la recibió, nadie la cuenta al cierre del día
y no aparece en ningún arqueo. Es un hueco de modelo, no un endpoint que
falte, y está anotado como deuda en
`docs/roadmap/deuda/modulo-accounting.md`.

Mientras tanto, el control es de proceso: el voucher del banco se archiva con
el asiento, y quien recibe el efectivo lo firma en papel.

## Lo que el ERP sí controla, y por eso no está acá

El pago a proveedor y el cobro de una venta **no se asientan a mano**: tienen
su cola, su umbral de aprobación y su asiento automático. Registrarlos como
asiento manual los saca de esos controles y duplica el asiento cuando el
automático llegue.
