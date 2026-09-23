# ADR-089 — La empresa nace contable y el periodo se abre solo

- Estado: aceptado
- Fecha: 2026-09-05
- Contexto: `src/modules/accounting/application/periodos.py`,
  `src/modules/accounting/application/asientos.py`,
  `src/modules/accounting/application/listeners.py`,
  `src/modules/accounting/infrastructure/models/asiento_omitido.py`,
  `src/modules/users/application/organizacion.py`
- Relacionado: ADR-034 (consumo de personal), ADR-081 (el plan contable es el
  PCGE), ADR-086 (la cuenta contable se configura en la categoría),
  RN-CTB-010, RN-CTB-011

## Contexto

El 2026-09-05, operando en staging: **las ventas cerradas no aparecían en el
balance y la comida de personal no costaba nada**. La hipótesis razonable era
que faltaba cablear algo, o que la facturación en modo prueba solo reconoce
comprobantes oficiales.

Ninguna de las dos. El cableado está completo y es correcto:

- `sales.venta_confirmada` se publica **al confirmar la orden** y su plantilla
  asienta debe `1212` / haber `7011`. Del comprobante aceptado por SUNAT
  cuelga **solo el IGV** (`plantillas.py`). La venta no depende de la boleta,
  y no tenía por qué depender: el ingreso es devengado.
- La comida de personal recorre `sales` → `inventory` (salida valorizada) →
  `accounting` (debe `625` «Atención al personal» / haber `201`), con ADR-034
  y pruebas verdes.

Lo que fallaba es que el asiento **se descartaba en silencio**, y por dos
cosas que nadie sabía que había que hacer a mano:

1. **El plan de cuentas.** `importar_pcge` solo se ejecutaba desde el botón
   «Importar PCGE». `crear_empresa` creaba la fila de `empresa` y nada más.
   Sin las cuentas del PCGE, `crear_asiento_desde_plantilla` devuelve `None`.
   ADR-034 ya lo había anticipado como consecuencia conocida —*"el ERP no
   siembra plan de cuentas para nadie"*— y la consecuencia resultó ser que
   **ninguna empresa asentó nada, nunca**.
2. **El periodo contable.** `abrir_periodo` solo se llamaba desde su endpoint
   manual: no hay job, ni cron, ni seeder. `periodo_de_fecha` era un lookup
   puro que devolvía `None` si la fila no existía. Es decir: **un mes que
   nadie abrió descarta todos los asientos automáticos del ERP entero**, de
   todos los módulos, sin bloquear nada y sin avisar.

Y encima el aviso mentía. `listeners._generar` imprimía siempre *«sin
regla_asiento configurada, asiento omitido»* a nivel `log.info`, cuando el
asiento sale `None` por cinco motivos distintos: periodo cerrado, cuentas
faltantes, evento sin plantilla, asiento duplicado y monto cero. Quien buscara
por qué el balance estaba vacío iba a mirar `regla_asiento`, que era el único
lugar donde no estaba el problema.

## Decisión

**1. Una empresa nace con su plan de cuentas.** `crear_empresa` publica
`organizacion.empresa_creada` y `accounting` lo escucha para importarle el
PCGE. Va por el bus y no por una llamada directa entre módulos, como manda
`CLAUDE.md`; `importar_pcge` ya era idempotente, así que reprocesar el evento
no duplica nada.

El plan contable no es una preferencia de la empresa: es el requisito para que
la contabilidad exista. Quien quiera otro lo edita después — el PCGE es el
plan oficial peruano y ADR-081 ya lo había elegido como base.

**2. El periodo se abre al primer asiento del mes.**
`periodo_para_registrar(empresa, fecha)` reemplaza al lookup puro en los
cuatro lugares que asientan: si el mes no existe, lo abre. `None` pasa a
significar **una sola cosa**, que el mes está cerrado.

Esto no debilita RN-CTB-010. La regla prohíbe asentar en un periodo
**cerrado**, y contra eso sigue protegiendo: un mes cerrado rechaza igual que
antes, y cerrarlo sigue siendo un acto explícito con su permiso. Un mes que
nunca se abrió no está cerrado — no existe, que es otra cosa. Confundir las
dos era el bug.

**3. La omisión deja rastro.** Tabla `asiento_omitido` con empresa, evento,
referencia de origen, fecha y motivo (`periodo_cerrado`, `sin_cuentas` con los
códigos que faltan, `sin_plantilla`), más `GET /accounting/asientos-omitidos`
y un aviso en la portada de Contabilidad que dice qué hacer con cada motivo.
Es la misma tabla que `incidencia_inventario`, por la misma razón y con la
misma forma.

`duplicado` y `monto_cero` **no se anotan**: son omisiones correctas y
esperadas —el evento se reprocesó, o el hecho no movió plata— y anotarlas
convertiría la tabla en ruido que nadie mira.

## Alternativas descartadas

- **Una tarea de Celery que abra el periodo del mes siguiente.** Es una tarea
  más que mantener, que puede no correr, y que resuelve tarde algo que se
  resuelve al usarlo. Y deja intacto el modo de falla: si la tarea falla, el
  mes vuelve a no existir y los asientos vuelven a desaparecer callados.
- **Que el asiento sin periodo levante un error.** Rompe la regla que sostiene
  todo el diseño de los listeners: contabilidad **nunca** bloquea la operación
  que la originó. Una venta no se puede caer porque el contador no abrió el
  mes.
- **Sembrar el PCGE en el seeder.** Arregla los entornos de prueba y deja rota
  la producción, que es donde el problema apareció. El alta de empresa es el
  único momento que existe siempre.
- **Solo mejorar el log.** Era lo primero que se pensó, y no alcanza: nadie
  lee los logs de la aplicación buscando por qué el queso no cuadra. Es
  textualmente lo que decía `incidencia_inventario` cuando se creó, y es la
  misma respuesta.

## Consecuencias

- El balance se llena solo. La venta cerrada, la compra recibida y la comida
  de personal asientan sin que nadie configure nada.
- **Se puede asentar en un mes viejo sin darse cuenta**: si llega una
  operación fechada tres meses atrás y ese mes nunca se abrió, se abre ahora y
  se asienta ahí. Es lo correcto contablemente —la operación pertenece a su
  mes— pero cambia un balance que alguien ya había mirado. El control es el
  cierre de periodo: el mes que se cerró no admite nada.
- Las empresas creadas antes de este cambio siguen sin cuentas hasta correr
  `scripts/sembrar_contabilidad.py`.
- **RN-CTB-011 queda desactualizada** por un cambio anterior a este, y se
  corrige acá: decía que sin mapeo configurado no hay asiento, pero
  `domain/plantillas.py` introdujo plantillas de fábrica, así que "sin
  configuración" ya no significa "sin asiento".
- Esto **no** repone los asientos que se perdieron mientras faltaban las
  cuentas y el periodo. Reprocesarlos es otro problema —hay que saber qué
  eventos hubo, no solo qué falta— y va en su propia rama.

## Enmienda 2026-09-23 — el aviso dice cuáles, y el error también se anota

- **El aviso decía cuántos, no cuáles.** Contaba por motivo y no mostraba
  ni la operación, ni el documento, ni el detalle que la tabla ya guardaba.
  Ahora trae una tabla desplegable con fecha, operación en palabras («Venta»,
  «Recepción de compra», «Depreciación mensual»…), el documento con enlace a
  su ficha cuando la tiene (`frontend/lib/asientos-omitidos.ts`), el motivo y
  el detalle.
- **Ventana de 30 días.** El aviso sumaba desde el primer día: un problema
  resuelto seguía gritando para siempre. Una configuración que sigue rota
  vuelve a aparecer mañana, que es la señal correcta.
- **Motivo `error`** (migración `d8e2f4a6b1c3`). Un listener que revienta con
  una excepción solo dejaba `log.exception`. Ahora `_registrar_fallo` lo anota
  en una sesión nueva con la clase y el mensaje de la excepción en `detalle`,
  resolviendo la empresa desde el payload. Si la empresa no se puede
  resolver, queda solo el log (sin empresa no hay a quién mostrárselo).
- `_omitir` pasa a ser `anotar_omision` (público dentro del módulo): lo usa
  también el listener.

