# ADR-043 — La orden enviada sigue viva, y la corrección tiene ventana

- Estado: aceptado
- Fecha: 2026-08-12

## Contexto

Hasta ahora, enviar una orden a cocina la congelaba: el PDV respondía *"Este
pedido ya se envió. Usa + para abrir uno nuevo"* a cualquier agregado, y
quitar una línea exigía **siempre** el PIN de un supervisor (RN-COM-020).

Las dos cosas chocan con cómo se atiende una mesa:

- **Una mesa pide de a poco.** La primera comanda sale, y diez minutos
  después piden otra bebida. Abrir una orden nueva para eso deja a la misma
  mesa con dos cuentas, que se cobran por separado y se entregan por
  separado.
- **El cajero se equivoca al teclear.** Marcar el plato de al lado y tener
  que llamar al encargado para corregirlo, treinta segundos después de
  haberlo mandado, convierte al supervisor en un pulsador de PIN. Y un
  control que se ejecuta veinte veces por turno deja de ser un control:
  se termina dejando la sesión del encargado abierta en la caja, que es
  exactamente lo que RN-AUD-005 quiere evitar.

## Decisión

### 1. Agregar es libre; quitar es lo que se controla

`POST /ventas/{id}/items` con el mismo permiso que crear la orden
(`sales.crear`) y sin firma de nadie. Agregar es lo que el negocio quiere que
pase: sube el ticket, no saca nada del inventario, y el rastro queda igual.

Lo que se controla es **quitar**, porque repone stock y baja el total.

### 2. La ventana de corrección son 5 minutos

Dentro de ella, quitar una línea o anular la orden lo hace quien opera la
caja, sin firma. Pasada, hace falta un supervisor.

Cinco minutos porque es lo que dura un error honesto en caja: más corto y el
cajero termina llamando al encargado por cada dedo mal puesto; más largo y
deja de ser corrección — a los quince minutos el plato salió, y quitarlo ya
no es arreglar un tecleo.

**Se mide contra la línea, no contra la orden.** Y la ventana de la orden
entera se mide contra su **última línea**: una mesa que sigue pidiendo tiene
la orden abierta desde hace una hora, pero lo último que mandó a cocina puede
ser de hace un minuto, y es eso lo que todavía se puede deshacer.

**Un lote necesita firma si alguna de sus líneas salió de la ventana.** Al
revés —dejar pasar el lote porque una es reciente— sería la forma de quitar
cualquier línea vieja acompañándola de una nueva.

### 3. El evento lleva **lo confirmado en esta operación**

Agregar líneas publica `sales.venta_confirmada` otra vez, con `items` = solo
las nuevas y `total` = **el incremento**, no el acumulado.

Se evaluó un evento nuevo (`sales.lineas_agregadas`) y se descartó: obligaría
a configurar una `regla_asiento` propia para que contabilidad lo asentara, y
mientras eso no pase el incremento no entraría a los libros. Reusando el
evento, cada consumidor hace lo correcto sin tocar nada:

| Consumidor | Con el delta |
|---|---|
| `inventory` | descuenta solo lo nuevo — nunca vio el acumulado |
| `accounting` | asienta el incremento; con el total acumulado contaría la venta dos veces |
| `marketing` | el lead ya está atribuido, así que no hace nada |
| `sales` | reprograma la revisión de demora, que es correcto: salió comida nueva |

`items` **ya era** el detalle de la operación; lo único que cambia de
significado es `total`, y al crear la orden delta y total coinciden. La
definición pasa a ser una sola: *lo que se confirmó recién*.

### 4. El PDV pide la firma cuando el servidor la pide, no antes

Intenta sin autorización; si recibe 403, abre el diálogo de firma y
reintenta. Al revés —pedir el PIN siempre, como hacía el diálogo de producto—
se le pedía la firma incluso a quien ya tenía el permiso, para su propio
pedido.

### 5. Un borrador vacío no es un pedido

El "+" reusa el borrador vacío que ya esté abierto en vez de apilar otro, y
una pestaña **sin líneas y sin enviar** se puede descartar con su "×". Una
con líneas o ya enviada no: eso es "Anular pedido", que repone inventario y
queda auditado. La última pestaña nunca se cierra — el PDV sin ninguna no
tiene dónde empezar a teclear.

## Alternativas descartadas

- **Que agregar también pida firma**: no protege nada. Lo que sale del
  inventario sin cobrarse es lo que se quita, no lo que se suma.
- **Ventana configurable por empresa** (`parametro_empresa`): sin caso que lo
  pida. Es una constante hasta que dos locales quieran números distintos.
- **Medir la ventana contra la creación de la orden**: una mesa larga
  quedaría fuera de ventana para siempre, y la línea recién agregada
  necesitaría firma a los dos segundos de existir.
- **Evento propio para el agregado**: ver §3.
- **Prohibir cerrar pestañas**: es el estado actual, y es el bug.

## Consecuencias

- Sin migración: `venta_item.created_at` ya existía y es la marca de tiempo
  que la ventana usa.
- `POST /ventas/{id}/anular-lineas` deja de exigir `autorizacion` en el
  cuerpo: pasa a opcional. Un cliente que la mande siempre sigue funcionando.
- `POST /ventas/{id}/anular` acepta el mismo cuerpo opcional (ADR-042 ya lo
  había introducido para el cajero).
- Queda anotado en Deuda técnica que **el KDS no distingue** una línea
  agregada de las originales: aparece en la cola como cualquier otra, sin
  decir que llegó después. Para la cocina eso es correcto —hay que
  prepararla— pero el despacho no ve que el pedido creció.
