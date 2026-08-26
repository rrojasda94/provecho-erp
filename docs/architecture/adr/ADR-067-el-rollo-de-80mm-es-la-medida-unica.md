# ADR-067 — El rollo de 80 mm es la medida única, y el ticket lo arma el ERP

- Estado: aceptado
- Fecha: 2026-08-25
- Contexto: `sales` (comprobante, comanda, precuenta), `shared` (formato de
  papel), frontend (PDV, Contabilidad)
- Relacionado: ADR-005 (facturación electrónica con Factiliza), ADR-013
  (arquitectura frontend), ADR-044 (cadena de estaciones del KDS), ADR-048 (el
  proxy pasa bytes), RN-COM-003, RN-COM-018, RN-COM-019, RN-CUP-014,
  RN-IMP-001, RS 097-2012/SUNAT

## Contexto

Hasta hoy el ERP **no tenía ningún modelo de boleta ni de factura**. Lo que
había era:

- El **PDF de Factiliza**, que se baja a pedido
  (`GET /sales/comprobantes/{id}/descargar/pdf`) y cuyo diseño lo decide el
  proveedor en su cuenta. El ERP no le manda formato ni lo puede cambiar.
- La **comanda** de cocina, texto plano de **32 columnas** (58 mm).
- La **precuenta**, texto plano de **40 columnas**.

Tres documentos que salen del mismo local, con tres anchos distintos, ninguno
con membrete, y el único que el cliente se lleva —el comprobante— dependiendo
de que un tercero conteste y de que alguien abra un visor de PDF. En la caja
eso significa que el cliente espera, o que se va sin papel.

Además, todas las ticketeras del grupo son de **80 mm**. Los dos anchos que
había estaban puestos para una impresora que no existe en ninguna sucursal.

## Decisión

### 1. Un solo ancho: 48 columnas

`src/shared/impresion.py` fija `ANCHO = 48` —lo que entra en 80 mm con la
fuente A (12x24) de ESC/POS— y lo usan la comanda, la precuenta y el CSS de
impresión del frontend. La comanda pasa de 32 a 48; la precuenta, de 40 a 48.

No hay parámetro de ancho por sucursal. Un parámetro implicaría que alguien lo
configure bien en cada local, y el día que esté mal el síntoma es un ticket
cortado que nadie relaciona con una pantalla de ajustes. Si algún día entra una
impresora de 58 mm, esto vuelve a ser una decisión, no un valor por defecto que
se arrastró.

### 2. El ticket del comprobante lo arma el ERP, y no reemplaza al PDF

`GET /sales/comprobantes/{id}/ticket` devuelve la representación impresa:
membrete, ítems con precio, desglose de impuestos, total en letras y el QR de
SUNAT. **No recalcula nada**: pide el mismo payload que se le manda a
Factiliza (`documento_de` + `construir_payload`) y lo lee. Si el ticket sumara
por su cuenta, el papel y el XML podrían discrepar en un céntimo de redondeo, y
el papel es lo que el cliente se lleva.

El PDF de Factiliza sigue siendo el documento formal y sigue estando a un
click. Lo que cambia es que la entrega en caja ya no depende de él.

**El ticket sale aunque SUNAT todavía no haya contestado.** La emisión es
asíncrona a propósito (RN-COM-003) y hacer esperar al cliente frente a la caja
es exactamente lo que esa decisión evita; mientras el comprobante no esté
`aceptado`, el papel lo dice en una franja.

La **nota de crédito** no entra todavía: su documento se arma con las líneas
acreditadas y no con las del comprobante, y ese armado hoy es privado de
`notas_credito`. Se entrega en PDF hasta que se haga (Deuda técnica).

### 3. El QR es dominio, no integración

`sales/domain/qr_sunat.py` codifica los nueve campos del anexo de la
RS 097-2012 separados por `|` y con `|` final. Vive en el dominio y no en
`shared/integrations/factiliza/` porque lo manda SUNAT: cambiar de proveedor no
cambia esta cadena.

Se agrega **una** dependencia, `segno`, para rasterizar el QR. Es Python puro y
sin dependencias propias —no arrastra Pillow ni una toolchain de imagen a la
API— y devuelve SVG, que es lo que la ticketera y el navegador pintan sin
perder nitidez. Se descartó generarlo en el navegador: la cadena es un dato
fiscal y su correctitud se prueba donde está la suite que la puede probar.

El SVG viaja como `data:` URI y se pinta con `<img>`. Un SVG inyectado en el
DOM puede ejecutar script; un `<img>` no.

### 4. El membrete sale del padrón, y lo configurable vive en `marca.skins`

Razón social, RUC, domicilio fiscal, nombre y dirección de la sucursal salen de
`empresa`/`sucursal`/`marca`. **No se teclean por local**: un local que escribe
su propio encabezado termina imprimiendo el RUC de la empresa equivocada, y eso
en una boleta es un problema fiscal, no de diseño.

Lo que sí se configura —el logo y las líneas de cortesía del pie— va en
`marca.skins["ticket"]`, la columna JSONB que ya existía para el branding del
PDV. Sin migración y sin tabla nueva: son dos campos de texto por marca, y una
tabla propia sería un CRUD más y una migración por cada línea.

El logo se referencia por **ruta** (`/marcas/charlies.svg`, servido por
`frontend/public/marcas/`) y no como binario en la base. Cambiarlo es
reemplazar el archivo.

### 5. Se imprime desde el navegador, y el diálogo lo quita una bandera

La hoja se monta en un portal colgado de `<body>` y `@media print` esconde todo
lo demás (incluido `dialog[open]`, que vive en el top layer y no lo alcanza un
selector de hijos de `<body>`). `@page { size: 80mm auto }` fija el papel.

**La impresión sin diálogo no es código de la aplicación**: es
`--kiosk-printing`, una bandera del navegador que hace que `window.print()`
mande directo a la impresora predeterminada. Se documenta en
`docs/engineering/impresion-termica.md` y se configura una vez por tablet.

Se descartaron dos alternativas:

- **Un agente ESC/POS local** (o impresión por red al puerto 9100): imprime de
  verdad sin diálogo y sin depender del navegador, pero es un binario más que
  instalar, actualizar y depurar en cada sucursal, y no hay ninguna sucursal
  con ese problema todavía. Queda anotado en Deuda técnica, y el trabajo hecho
  acá lo habilita: el cuerpo de la comanda y la precuenta ya son texto de 48
  columnas, que es exactamente lo que un ESC/POS consume.
- **Un `<iframe>` con documento propio**: aísla mejor, pero obliga a duplicar
  el CSS del ticket como string dentro del iframe, y esa copia se desincroniza
  del original a la primera corrección.

### 6. Los comprobantes emitidos tienen pestaña en Contabilidad

`GET /sales/comprobantes` acepta `sales.leer` **o** `accounting.leer`. El
contador tiene que poder ver el documento fuente del asiento —es literalmente
lo que declara— y no tiene `sales.leer` ni le corresponde: darle el módulo de
ventas entero para que vea las boletas de la empresa sería el problema al
revés. Mismo patrón que `GET /kds/pantallas` con `kds.operar`/`kds.configurar`
(ADR-065).

El importe de la fila sale de los **pagos confirmados** de esa cuenta y no de
un recálculo de líneas: el comprobante nace cuando la cuenta queda pagada, así
que los pagos son su total, y leerlo de ahí evita repetir el prorrateo del
descuento de la orden por cada fila del listado.

### 7. La fecha del documento es la del cobro, no la de "ahora"

`_documento()` ponía `datetime.now(UTC)` como `fecha_Emision`. Dos errores
encimados:

- Un comprobante que se quedó en la cola —proveedor caído, worker muerto,
  `FACTILIZA_TOKEN` sin configurar— y sale al día siguiente declaraba **una
  fecha que la venta nunca tuvo**.
- `now(UTC)` corre el calendario: una venta de las 20:00 en Tarapoto es del día
  25, pero en UTC ya es el 26. Es la misma trampa que documenta
  `shared.fechas`.

Ahora es `comprobante.created_at` leído en `America/Lima`. Sale acá y no como
arreglo aparte porque el QR codifica esa fecha: con dos fechas distintas, el
papel y el XML no se pueden contrastar, que es justamente para lo que el
fiscalizador escanea el QR.

## Consecuencias

- Una dependencia nueva en la API (`segno`).
- La comanda de cocina cambia de ancho: los rollos de 58 mm que hubiera en un
  cajón dejan de servir.
- La impresión directa depende de cómo se lance el navegador en cada tablet.
  Sin la bandera todo funciona igual, con un diálogo de por medio.
- El PDF de Factiliza sigue siendo la copia formal; el ERP no la archiva
  (decisión de ADR-005, sin cambios).
- Queda pendiente: nota de crédito imprimible, agente ESC/POS, y reenvío del
  comprobante por WhatsApp/correo (ya estaba en Deuda técnica).
