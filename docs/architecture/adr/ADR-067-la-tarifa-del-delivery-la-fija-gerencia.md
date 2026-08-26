# ADR-067 — La tarifa del delivery la fija Gerencia, y el reparto se cobra

- **Estado:** aceptada
- **Fecha:** 2026-08-25
- **Contexto:** `sales` (tarifa de delivery, total de la venta), Gerencia
  (`parametro_empresa`), PDV
- **Relacionado:** ADR-014 y su Addendum (parámetros operativos por empresa),
  ADR-053 (la dirección se elige en el mapa), ADR-054 (el delivery se cobra
  por kilómetro), ADR-018 (PDV)

## Contexto

ADR-054 se construyó completo y quedó **invisible**. Tres meses después de
mergeado, la respuesta del negocio fue «eso no está disponible». Ninguna de
las causas era falta de dominio:

1. **La tarifa vivía en `settings`**, o sea en el `.env`. Cambiar el precio
   por kilómetro exigía editar un archivo del servidor y redesplegar, así que
   en la práctica nadie la cambió nunca: los tres valores siguieron en `0` —
   la función existía y no cobraba nada. Y no había ninguna pantalla donde
   mirar, porque un `.env` no tiene pantalla.
2. **El reparto se calculaba, se congelaba en `venta.costo_entrega` y no se
   cobraba.** ADR-054 lo dejó explícitamente en la deuda («el costo se
   calcula, se guarda y se muestra»), pero desde caja eso se lee como «el PDV
   no funciona»: el cajero ve «reparto S/ 5» y el ticket cobra S/ 0.
3. **Sin claves de Google todo se degrada en silencio**, que es lo correcto
   frente al cajero —una venta no se pierde porque un tercero no contestó— y
   es exactamente lo incorrecto frente a Gerencia: el campo de dirección se ve
   como un cuadro de texto común y no hay forma de saber que falta una clave.

La primera y la tercera no son bugs de ADR-054; son la consecuencia de no
haberle dado dueño ni tablero a una función que define cuánta plata paga el
cliente.

## Decisión

### Los cuatro números son `parametro_empresa`, no `.env`

La tarifa del delivery es un **valor operativo configurable** en el sentido
exacto de ADR-014: lo fija el negocio, cambia con el mercado, y un cambio
tiene que poder sustentarse. Pasa a vivir donde ya viven el umbral de una
orden de compra y el margen mínimo, con los mismos códigos en el módulo
`sales`:

| código | forma del valor |
|---|---|
| `delivery_tarifa_base` | `{"monto": "5.00", "divisa": "PEN"}` |
| `delivery_precio_por_km` | `{"monto": "1.50", "divisa": "PEN"}` |
| `delivery_radio_km` | `{"km": "8"}` |
| `delivery_distritos_restringidos` | `{"distritos": ["Belén"]}` |

`settings.delivery_*` **no se borra**: queda como **semilla**, el valor con el
que cotiza una empresa que todavía no aprobó ninguno. Sin eso, encender esto
apagaría el delivery de golpe en el despliegue, y las 12 pruebas de ADR-054
—que ejercitan el cálculo, no de dónde salen los números— dejarían de decir
nada.

Consecuencia deliberada: **el cambio no surte efecto hasta que Gerencia lo
aprueba** (RN-GER-009). Son dos pasos y no uno porque acá se define cuánta
plata paga el cliente, y el mismo mecanismo que audita un umbral de compra
vale para esto.

`tarifa_de(session, empresa_id)` resuelve los cuatro de una vez y devuelve un
`Tarifa` inmutable que se pasa entero a `cotizar()`. Leer cada parámetro
dentro de cada función sería una consulta por número y, peor, dejaría que dos
partes del mismo cálculo usaran configuraciones distintas si alguien aprueba
un cambio en el medio.

Un parámetro **mal formado cobra la semilla** en vez de reventar: el valor es
un JSON que pasó por un formulario y por una pantalla de aprobación, y un 500
en caja es peor que cobrar el precio anterior.

### El reparto entra al total (RN-COM-041)

`total_a_cobrar` suma `venta.costo_entrega`. Tres reglas alrededor:

- **Después del descuento manual.** El encargado autoriza un descuento sobre
  lo que el cliente consumió; regalar el flete al mismo tiempo no es lo que
  aprobó.
- **Un consumo de personal no paga reparto.** Vale cero entero (RN-COM-025):
  cobrarle el flete a un trabajador emitiría un comprobante por el reparto
  solo.
- **No se prorratea entre cuentas separadas**, pero sí se cobra: va entero
  en la **primera** cuenta. Omitirlo del cobro por grupo parecía inofensivo y
  no lo era — el cobro normal del PDV pasa por ahí (`grupo_cobro=1`), así que
  el delivery de una sola cuenta no se habría cobrado nunca. Y la suma de las
  cuentas tiene que dar el total de la venta, o la orden no se puede terminar
  de cobrar. Partir un reparto entre comensales es lo que nadie pidió.

**Y el PDV cotiza aunque no haya ancla.** Hasta ahora, sin punto en el mapa
no se pedía cotización: no había nada que medir. Desde que el flete entra al
total eso deja al cajero mirando un total menor que el que el servidor va a
cobrar — y es el caso **normal**, no el raro: sin clave de Maps, o con una
calle que Google no conoce, ninguna dirección tiene ancla. La llamada extra no
le cuesta nada a nadie: sin destino, `cotizar` devuelve la tarifa base y ni
pregunta a Google. Con la tarifa apagada el renglón no se dibuja, para no
poner un «Reparto S/ 0.00» en cada delivery.

**Sin línea de venta.** ADR-054 dejó anotado que corresponde un producto de
servicio «Delivery» para que aparezca en el comprobante y en contabilidad. Se
descarta por ahora: exige un artículo, una receta vacía, una categoría y una
cuenta contable para mover un número que ya está en su propia columna. La
columna `costo_entrega` sobrevive al comprobante igual, y el día que
facturación lo exija por separado, el cambio es de emisión, no de cobro.

### Gerencia tiene una pantalla, y la pantalla dice la verdad

`/gerencia/delivery`: los cuatro campos, las propuestas pendientes con su
botón de aprobar, y **tres renglones de diagnóstico** que es lo que hace que
la pantalla no mienta:

- si el reparto se está cobrando (base y precio por km distintos de cero),
- si hay `GOOGLE_MAPS_SERVER_KEY` — sin ella toda distancia sale de la línea
  recta y se cobra marcada «aprox.»,
- si hay `GOOGLE_MAPS_BROWSER_KEY` — sin ella no hay buscador ni pin, y sin
  punto no hay distancia que medir.

Los alimenta `GET /sales/delivery/configuracion`, que devuelve la tarifa
**efectiva** (lo aprobado, o la semilla) y no lo propuesto. Es una llamada
distinta de `GET /parametros` a propósito: son dos preguntas —«con qué se
está cobrando» y «qué falta resolver»— y mezclarlas es lo que haría que la
pantalla muestre un valor que nadie está usando.

La clave del navegador la reporta el propio frontend desde su entorno
(`lib/mapas.ts`) y no la API: son dos procesos con dos configuraciones, y
preguntarle a la API por una variable del contenedor `web` daría la respuesta
de otro.

### La tarifa es por empresa

No por sucursal. `parametro_empresa` ya es por empresa y el grupo cotiza
igual desde todos sus locales. Cuando dos sucursales necesiten precios
distintos, el parámetro gana alcance o `sucursal` gana columnas — ninguna de
las dos cosas hoy tiene caso.

## Alternativas descartadas

- **Dejar la tarifa en el `.env` y solo agregar una pantalla de lectura.**
  Barato, y no resuelve nada: el problema no era no ver el número, era no
  poder cambiarlo sin un despliegue.
- **Sembrar los cuatro códigos en `src/seeders/parametros.py` y editarlos
  desde `/gerencia/parametros`.** Cero pantallas nuevas, pero el formulario
  genérico de ese listado solo sabe expresar **un** número con su unidad: la
  lista de distritos vetados no entra, y los cuatro valores quedarían como
  cuatro filas sueltas que hay que resolver de a una sin ver la tarifa
  completa.
- **Un endpoint nuevo de escritura para la tarifa.** Salteaba la aprobación
  de ADR-014 para el único parámetro que define un precio al cliente. La
  pantalla escribe por `POST /parametros` como todo el mundo.
- **Cobrar el reparto como línea de venta.** Ver arriba.
- **Que la API reporte si el navegador tiene clave de Maps.** Ver arriba.

## Consecuencias

- **Sin migración.** `parametro_empresa` existe desde ADR-014 y las columnas
  de ubicación desde ADR-053. Este cambio no toca el esquema.
- **El total de una venta con delivery cambia** el día del despliegue si —y
  solo si— hay tarifa configurada. Con la semilla en `0`, que es el estado
  actual, ninguna venta cambia de precio.
- Una propuesta por número cambiado: guardar los cuatro a la vez deja cuatro
  filas para aprobar. Se proponen **solo los que cambiaron** contra la tarifa
  efectiva, no los cuatro siempre.
- `.env.staging.example` y `frontend/.env.example` pasan a documentar las
  claves de Maps, que era el otro motivo real de «esto no está disponible».
