# Propuesta de valores para los parámetros operativos

**Fecha:** 2026-08-05 · **Estado:** propuesta, pendiente de aprobación de
Gerencia · **Mecanismo:** ADR-014 (`parametro_empresa`, RN-GER-008/009)

El mecanismo quedó resuelto e implementado el 2026-08-02: cada área propone
los parámetros de su módulo y **no surten efecto hasta que Gerencia los
aprueba**. Lo que faltaba era el valor. Este documento propone uno por
parámetro, con el razonamiento detrás, para que Gerencia apruebe, corrija o
rechace en `/gerencia/parametros`.

**Cómo leer esto.** Cada propuesta dice de dónde sale el número y —más
importante— **qué pasa si está mal**. Un parámetro mal puesto no rompe el
sistema: distorsiona una decisión diaria durante meses sin que nadie lo
note. Por eso cada uno lleva un disparador de revisión concreto.

**Los tres primeros meses son de calibración, no de acierto.** Cuatro de
estos siete valores se fijan hoy sin histórico propio: el ERP recién entra
en operación. Están anclados a referencias externas y a la lógica del
negocio, que es lo mejor disponible, pero el dato real de Charlie's va a
corregirlos. Eso no es un defecto de la propuesta — es la razón por la que
`parametro_empresa` existe en vez de una constante en el código.

---

## 1. `purchases/oc_umbral` — Umbral de aprobación de orden de compra

**Propuesta: S/ 2,000.00** (confirmar el valor semilla actual)

Sobre este monto, emitir una OC exige `purchases.aprobar` — que desde el
2026-08-05 es **solo del administrador**.

**Sustento.** Es el parámetro con menos base propia de los siete y conviene
decirlo primero: no hay histórico de órdenes de compra reales contra el cual
calibrarlo. Lo que sí se puede razonar es el rango en el que tiene que caer:

- Por **debajo** del pedido semanal rutinario de insumos, el umbral frena la
  operación: el encargado de compras espera al administrador para reponer
  queso y harina, y termina comprando con caja chica para esquivarlo — que
  es exactamente el descontrol que la caja chica no debe habilitar.
- Muy por **encima**, el umbral no controla nada: la aprobación se vuelve un
  trámite que solo ve compras extraordinarias que igual se hubieran
  conversado.

S/ 2,000 está cuatro veces por encima de la caja chica propuesta (§4) y
razonablemente sobre un pedido semanal de insumos de dos locales. Mantenerlo
tiene además una ventaja concreta: es el valor con el que el sistema ya
opera, así que aprobarlo no cambia ningún comportamiento y deja el cambio
para cuando haya dato.

**Revisar cuando** haya 3 meses de OC reales: el umbral correcto es el que
deja pasar sin aprobación ~80 % de las órdenes por cantidad y menos del 30 %
por monto. Si hoy pasa el 99 % de las órdenes, está alto; si el
administrador aprueba a diario, está bajo.

**Si está mal:** demasiado bajo, se convierte en cuello de botella y empuja
a saltarse el proceso. Demasiado alto, el control no existe pero figura
como si existiera — que es peor, porque nadie lo revisa.

---

## 2. `sales/margen_minimo` — Margen de contribución mínimo objetivo

**Propuesta: 60 %**

Margen de contribución = precio − costo variable (insumos + empaque +
comisión del medio de pago), según `politica-comercial.md §1`.

**Sustento.** Acá sí hay referencia sólida, y una particularidad local que
mueve el número:

- El *food cost* objetivo en pizzería ronda el **28-35 %** del precio de
  venta. Tomando 32 % como centro razonable.
- El **empaque** de una pizza para llevar pesa ~3 % del precio.
- La **comisión del medio de pago** (tarjeta, billetera) es ~3-4 %.

32 + 3 + 4 = 39 % de costo variable → **61 % de margen de contribución**.
Se propone 60 % como piso, no como objetivo: un piso deja espacio para
productos gancho por debajo con justificación escrita, que es lo que la
política ya exige.

**La particularidad que importa:** Majambo está **exonerada de IGV por la
Ley de Amazonía** (RN-IMP-001). El precio de carta no carga 18 % que en Lima
sí se va a SUNAT, así que a igual precio el margen real acá es más alto que
la referencia nacional. 60 % es exigente pero alcanzable en este régimen —
en un local con IGV el mismo piso sería agresivo.

**Revisar cuando** el reporte `margen_por_producto` (ya existe en el
tablero) tenga un trimestre de datos. Ese reporte deja el costo en `null`
para productos sin receta: **antes de fijar el piso conviene que las recetas
estén completas**, o el margen se mide contra un costo que falta.

**Si está mal:** demasiado alto, bloquea promociones legítimas y empuja a
saltarse la regla "con aprobación de gerencia" hasta volverla rutina.
Demasiado bajo, el negocio vende más y gana menos sin que el reporte lo
grite.

---

## 3. `inventory/margen_error_ajuste` — Margen de error de ajuste

**Propuesta: 2 %** (confirmar el semilla) **más un piso de S/ 20.00**

Diferencia entre stock contado y esperado que se acepta sin escalar a
Gerencia. Sobre el margen, el ajuste dispara
`inventory.ajuste_fuera_margen`.

**Sustento.** El 2 % ya es el valor por defecto del código
(`INVENTORY_MARGEN_AJUSTE_PCT`) y es razonable para producto a granel: harina
y queso pierden peso por manipuleo y humedad, y un conteo perfecto de un saco
abierto no existe.

**El piso es el agregado, y es el punto de esta propuesta.** Un margen solo
porcentual castiga a las categorías baratas: 2 % de un conteo de S/ 30 en
servilletas son 60 céntimos, así que cualquier diferencia real escala a
Gerencia y el evento se vuelve ruido que nadie mira. Un piso absoluto de
S/ 20 dice: por debajo de eso no vale la pena la atención de nadie,
independientemente del porcentaje. **El código ya lo lee** (2026-08-06): la
diferencia se valoriza al `costo_promedio` del artículo y basta cumplir una
de las dos tolerancias —el porcentaje o el piso— para no escalar. Hasta que
Gerencia apruebe esta fila sigue rigiendo el 2 % sin piso.

**Revisar cuando** haya 2 meses de conteos cíclicos cerrados: si más del
20 % de los conteos dispara el evento, el margen está apretado o hay un
problema real de merma que el margen estaría tapando.

**Si está mal:** demasiado apretado, la alerta se vuelve ruido y se ignora
—que es la peor falla posible en un control—. Demasiado holgado, un robo
sostenido cabe dentro del margen y nunca se detecta.

---

## 4. `purchases/monto_caja_chica` — Fondo de caja chica de compras

**Propuesta: S/ 500.00 por sucursal**, reposición al bajar de S/ 150.00

**Sustento.** La caja chica existe para el proveedor informal que no emite
factura ni recibe OC: el mercado, la ferretería de la esquina, el taxi que
trae un repuesto urgente. Su tamaño correcto es **el que cubre una semana de
esos imprevistos y ni un sol más**: un fondo grande deja de ser un fondo de
emergencia y se convierte en una vía de compra paralela que esquiva el
proceso de OC — el riesgo que `docs/compras/README.md` ya señala.

S/ 500 cubre varios imprevistos semanales típicos de un local sin habilitar
una compra de insumo de volumen, que es justamente lo que debe seguir yendo
por OC. El disparador de reposición al 30 % evita que el encargado se quede
sin fondo un sábado.

**Revisar cuando** haya un trimestre de rendiciones: si la caja se repone
más de una vez por semana, o está corta; o hay compras entrando por acá que
deberían ser OC.

**Si está mal:** demasiado chico, el encargado adelanta plata de su bolsillo
—que es un problema laboral, no contable—. Demasiado grande, se vuelve la
compra fácil y la OC el trámite molesto.

---

## 5. `accounting/plazo_envio_comprobante` — Plazo interno de envío al contador

**Propuesta: 5 días hábiles** contados desde el cierre del mes

**Sustento.** El vencimiento real lo fija el **cronograma mensual de SUNAT,
que depende del último dígito del RUC** — no es una fecha fija y hay que
leerlo del calendario del año en curso. Por eso el parámetro **no es la
fecha de vencimiento sino el plazo interno**, que es lo que la empresa sí
controla.

5 días hábiles desde el cierre le dejan al contador externo alrededor de una
semana de holgura sea cual sea el dígito, que es lo que hace la diferencia
entre declarar con tiempo y declarar el último día. El plazo es interno y
por eso es exigible al encargado: no depende de SUNAT.

**Revisar cuando** haya dos cierres reales con el contador: si devuelve
comprobantes por inconsistencias, el cuello no es el plazo sino la calidad,
y acortarlo no ayuda.

**Si está mal:** demasiado largo, el contador declara contrarreloj y los
errores se pagan con multa. Demasiado corto, el encargado envía incompleto
y después manda alcances, que es peor para todos.

---

## 6. `rrhh/rango_salarial_<perfil>` — Rangos salariales

**Base de cálculo: RMV.** Los rangos se proponen **como múltiplo de la
Remuneración Mínima Vital**, no como monto fijo. Es deliberado: la RMV
cambia por decreto y un rango en soles queda desactualizado en silencio; un
múltiplo se recalcula solo. `marco-legal-laboral.md` registra la RMV en
**S/ 1,130 y anota "verificar vigente"** — **ese es el primer dato que hay
que confirmar antes de aprobar esta sección**, porque todo lo de abajo se
apoya en él.

Régimen: **microempresa REMYPE** (sin CTS, sin gratificaciones, sin
asignación familiar hasta ~jul 2027). El sueldo bruto es prácticamente el
costo total del puesto, a diferencia del régimen general.

Los **siete perfiles** son los que RRHH contrata hoy. Quedan fuera: gerente
general (es el dueño), contador (externo, honorarios por RHE), y los dos
perfiles de cocina de producción (planeados 2027, sin operación real).

| Perfil | Rango propuesto | Razón |
|---|---|---|
| Limpieza y apoyo | 1.00 – 1.10 RMV | Puesto de entrada, sin requisito de experiencia previa |
| Atención al cliente (caja/mozo) | 1.05 – 1.30 RMV | Maneja dinero y es la cara del local; el techo premia experiencia y polifuncionalidad |
| Cocina (sucursal) | 1.10 – 1.45 RMV | Oficio con curva de aprendizaje real; el techo es para quien saca hora punta solo |
| Chofer repartidor | 1.10 – 1.35 RMV | Licencia vigente y responsabilidad sobre el vehículo y la cobranza en ruta |
| Encargado de almacén central | 1.40 – 1.80 RMV | Responde por el inventario del grupo entero y aprueba despachos |
| Encargado de compras | 1.50 – 2.00 RMV | Negocia con proveedores y maneja caja chica; el puesto donde un error cuesta más |
| Jefe comercial | 2.00 – 2.80 RMV | Puesto de jefatura con metas y personal a cargo |

**Sustento y su límite.** La estructura —entrada, oficio, encargatura,
jefatura— sale de la responsabilidad que cada perfil ya tiene documentada en
`docs/*/perfiles/`, y los saltos entre niveles son los que mantienen sentido
ascender. **Lo que esta propuesta no tiene es el mercado laboral real de
Tarapoto**, que es la mitad del problema: un rango correcto en estructura
pero fuera de mercado no consigue candidatos, o los consigue y los pierde en
tres meses.

**Antes de aprobar** conviene contrastar contra dos o tres avisos reales de
puestos equivalentes en la zona. Es una hora de trabajo que evita un año de
rotación.

**Si está mal:** demasiado bajo, se contrata a quien no tiene otra opción y
se paga en rotación e inducción repetida. Demasiado alto, se compromete
planilla que en temporada baja no se puede sostener — y bajar un sueldo ya
pactado no se puede.

---

## 7. Esquema de incentivo / comisión

**Propuesta: bono grupal por sucursal, no comisión individual por venta.**

`politica-comercial.md §3` exige que el criterio lo aprueben **Comercial +
RRHH + Gerencia juntos**, se documente por escrito y se comunique **antes**
de empezar a medirse, nunca retroactivo. Esto es una propuesta de diseño
para esa conversación; el valor numérico va después en
`sales/incentivo_meta_pct`.

**Diseño propuesto:**

- Se paga **por sucursal**, no por persona, y solo si la meta del periodo se
  cumple al **100 %**.
- Monto: **3 % del excedente sobre la meta**, repartido entre el personal
  del periodo **en proporción a las horas trabajadas** (`asistencia` ya las
  tiene).
- Techo por persona: **0.5 RMV** en el periodo, para que un mes atípico no
  cree una expectativa insostenible.
- Se comunica al inicio del periodo junto con la meta (`meta_venta.
  comunicada_at` existe justamente para probar que se comunicó).

**Por qué grupal y no individual.** En un local de comida **la venta es de
equipo**: el cajero no vende más si la cocina se demora o el despacho se
equivoca. Una comisión por ticket individual produce efectos conocidos y
malos — el cajero compite por atender al cliente que más gasta, apura el
guion, presiona el *upsell* hasta incomodar, y la cocina queda fuera del
incentivo aunque sea la que sostiene el tiempo de atención. El bono grupal
alinea a todo el turno con el mismo número.

**Por qué sobre el excedente y no sobre la venta total.** Un porcentaje de
la venta total paga por la venta que igual iba a ocurrir. Sobre el excedente
se paga solo lo que la meta no daba por hecho, que es lo único que el
esfuerzo agregó.

**Si está mal:** un incentivo mal diseñado es peor que ninguno, porque
premia el comportamiento equivocado y cuesta caro retirarlo. Si hay dudas,
la política ya tiene la salida correcta: **las metas funcionan como
herramienta de gestión sin efecto en el sueldo** hasta que el criterio esté
claro.

---

## Resumen para aprobar

| Parámetro | Propuesta | Confianza |
|---|---|---|
| `purchases/oc_umbral` | S/ 2,000.00 | **Baja** — sin histórico propio |
| `sales/margen_minimo` | 60 % | Media-alta — referencia sólida + Amazonía |
| `inventory/margen_error_ajuste` | 2 % + piso S/ 20.00 | Media-alta — el piso ya está en código |
| `purchases/monto_caja_chica` | S/ 500.00 | Media |
| `accounting/plazo_envio_comprobante` | 5 días hábiles | Alta — el plazo es interno |
| `rrhh/rango_salarial_*` (7) | 1.00 – 2.80 RMV según perfil | **Baja** — falta contraste de mercado local |
| Incentivo por meta | Bono grupal, 3 % del excedente | Media — decisión de tres áreas |

Los dos de confianza baja son los que conviene aprobar **como provisionales
y con fecha de revisión**, no como definitivos.
