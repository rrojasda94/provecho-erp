# ADR-074 — El borrador del PDV vive en el servidor

- **Estado:** aceptada
- **Fecha:** 2026-08-28
- **Contexto:** `sales` (`pedido_borrador`), `frontend/app/pdv`
- **Relacionado:** ADR-009 (modo offline del PDV), ADR-043 (la orden abierta
  sigue viva), RN-COM-005

## Contexto

El ticket a medio armar vivía **solo** en la memoria del navegador:

```ts
const [borradores, setBorradores] = useState<Borrador[]>([nuevoBorrador()]);
```

Sin `localStorage`, sin servidor, sin nada. Recargar la página, quedarse sin
batería o navegar fuera del PDV borraba todas las pestañas de pedido, y el
mesero volvía a teclear la mesa entera. En el turno de prueba pasó lo
segundo: el pedido a medio armar se perdió porque la sesión se cayó
(ADR-073), y no había de dónde recuperarlo.

El propio código lo documentaba como diseño —"vive solo en el PDV hasta que
se envía"— apoyado en que ADR-009 iba a resolverlo con el motor de sync
offline. Ese motor sigue sin construirse, y mientras tanto el turno pierde
pedidos todas las semanas.

## Decisión

Una tabla, tres endpoints y un autoguardado.

### `pedido_borrador`, con el contenido en JSONB

`id` (el uuid que la pestaña ya tenía en el navegador), `sucursal_id`,
`punto_venta_id`, `usuario_id` y `contenido` JSONB.

**JSONB y no columnas.** Un borrador **no es un hecho de negocio**: no
descuenta stock, no asienta, no se cobra y no tiene número de orden. La forma
la decide el PDV —tipo de orden, mesa, comensales, cliente y líneas con sus
extras, restas y atributos—, y modelarla en columnas obligaría a una
migración cada vez que el ticket gane un campo. El día que haya que reportar
sobre borradores (¿qué se arma y no se cobra?), esto se normaliza; hoy sería
una tabla llena de columnas que solo se leen juntas y de una sola vez. Es el
mismo criterio ya aceptado para `sin_articulo_ids` y `valores_variante_ids`.

Lo que sale a cocina **sí** se valida entero, en `POST /sales/ventas`. El
servidor no interpreta el borrador; lo guarda.

### Es de la caja, no del usuario

Se lista por `punto_venta_id`. El relevo de turno tiene que poder seguir el
pedido que dejó el anterior sin que ese cierre sesión primero — que es
exactamente el caso que rompe un borrador por usuario. `usuario_id` guarda
quién lo tocó al final, y no restringe nada.

### `PUT` con el id del cliente, y no `POST`

El navegador guarda con cada cambio y no puede llevar la cuenta de si esta
pestaña ya llegó al servidor. Un `PUT` idempotente por el id que ya tenía
deja que un reintento tras un corte de red termine en el mismo estado; un
`POST` que crea dejaría una pestaña nueva por cada tecla.

### No es una `venta` en estado `borrador`

Se evaluó y se descartó: una `venta` consume `numero_orden`, el correlativo
legible por sucursal y día que ve el personal. Numerar algo que quizá nunca
salga de la caja deja huecos en la serie que el turno lee como pedidos
perdidos. Además obligaría a filtrar ese estado en todas las consultas que
hoy asumen que una `venta` es una venta.

### Nada de esto bloquea la caja

Si el guardado falla —red intermitente, API caída—, el PDV sigue vendiendo
con el borrador en memoria, que es exactamente lo que hacía antes. La
persistencia es una red de seguridad, no un requisito para tomar un pedido.

## Detalles que no son arbitrarios

**Se guarda con 800 ms de espera desde la última tecla**, y solo la pestaña
que cambió: se compara contra lo último que se mandó de cada una. Sin eso,
tocar una pestaña reenviaría también las otras, sin haber cambiado.

**Una pestaña en blanco no se guarda.** Sin líneas, sin mesa, sin cliente y
sin haber salido a cocina es la pestaña con la que el PDV arranca: guardarla
llenaría la tabla de tickets vacíos y devolvería pestañas fantasma en cada
arranque.

**Los recuperados reemplazan a la pestaña del arranque, no se suman.** Si no,
cada recarga dejaría una pestaña vacía por encima de lo que se estaba
armando.

**El listado filtra por jornada** y una tarea de madrugada purga lo anterior.
Un borrador sin enviar de un turno que ya cerró no es un pedido que alguien
esté esperando. La purga corre a las 5:30 y no cada hora: el corte es la
medianoche del negocio, y borrar a media tarde el borrador de "ayer" mientras
alguien todavía lo tiene abierto sería quitarle el pedido de la pantalla en
pleno servicio.

**Descartar borra de verdad, y es idempotente.** Un borrador descartado no
tiene nada que auditar —nunca salió de la caja— y conservarlo obligaría a
filtrarlo en cada listado para siempre. El PDV descarta al enviar el pedido y
al cerrar la pestaña, dos caminos que pueden cruzarse: un 404 ahí solo
serviría para pintar un aviso de algo que ya está como se quería.

## Consecuencias

- **Migración** `a1c47e6b90d2`: crea `pedido_borrador` con índice por
  `punto_venta_id` —la consulta que corre en cada arranque del PDV es "los
  borradores de esta caja"— y sin `deleted_at`.
- `PUT /sales/borradores/{id}`, `GET /sales/borradores?punto_venta_id=` y
  `DELETE /sales/borradores/{id}`, todos con permiso `sales.crear`.
- **El proxy del navegador ganó su handler de `PUT`.** No lo tenía, y Next
  responde 405 al verbo que el archivo no exporta sin decir en ningún lado
  que el que falta es el del proxy y no el del endpoint. Un test del contrato
  ahora exige un handler por cada verbo que la API usa.
- Esto **no** reemplaza a ADR-009: el borrador se guarda cuando hay red. Un
  PDV sin conexión sigue con lo suyo en memoria hasta que el motor de sync
  exista.
