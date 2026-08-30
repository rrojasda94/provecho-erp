# ADR-085 — La unicidad del comprobante depende de quién lo emitió

- **Estado:** aceptada
- **Fecha:** 2026-08-30
- **Contexto:** `shared` (`comprobante`), `purchases`, `sales`
- **Relacionado:** ADR-081 (el IGV nace con el comprobante), ADR-082 (compra
  directa), RN-CPP-001/002, RN-CMP-005

## Contexto

`comprobante` es transversal a propósito: la misma tabla sirve a `sales`
emitiendo y a `purchases` recibiendo, distinguidos por `direccion`. Pero su
unicidad no lo distinguía:

```python
UniqueConstraint("empresa_id", "serie", "correlativo")
```

Eso dice que dentro de una empresa no puede haber dos documentos con la misma
serie y número, **sin importar quién los emitió**. Tres consecuencias, todas
reales:

1. **La F001-1 del proveedor bloquea la nuestra.** Nuestra serie de facturas
   es `F001` porque así la numera SUNAT; la del proveedor también. La primera
   factura de compra que entrara impedía emitir nuestro comprobante de ese
   número.
2. **Dos proveedores no pueden coincidir.** La molinera y la ferretería emiten
   su F001-1 el mismo día y los dos documentos son válidos. El segundo moría
   con un `IntegrityError`, o sea un 500.
3. **La numeración propia saltaba.** `ComprobanteRepo.siguiente_correlativo`
   toma el máximo de la serie sin filtrar `direccion`: registrar una compra
   F001-1200 hacía que el siguiente comprobante propio saliera con el 1201. Un
   salto de numeración ante SUNAT provocado por el papel de un tercero.

A eso se sumaba que la factura del proveedor no se podía representar: la tabla
guardaba tipo, serie, correlativo y sustento, y nada más. La fecha del papel
—la que manda en el Registro de Compras— no tenía dónde ir; el importe se
tomaba implícitamente de `orden_compra.total`, que es la **base valorizada de
lo recibido** y no lo que la factura declara.

## Decisión

### La unicidad se parte en dos, por dirección

- **Emitido:** único por `(empresa_id, serie, correlativo)`. Es nuestra
  numeración y la empresa responde por ella.
- **Recibido:** único por `(empresa_id, emisor_num_doc, serie, correlativo)`.
  El número del papel identifica al documento **dentro de su emisor**, no
  dentro de nuestra empresa.

Dos índices únicos parciales, con `sqlite_where` y `postgresql_where` —el
patrón que el repo ya usa en cinco modelos—, porque los tests corren sobre
SQLite con `create_all` y las migraciones sobre Postgres.

El predicado del índice de recibidos incluye `emisor_num_doc IS NOT NULL`
explícito. Un `ticket_compra` informal puede no identificar a su emisor, y ahí
no hay unicidad que imponer: escribirlo deja dicho que es a propósito en vez
de que dependa de cómo trata NULL cada motor. Se descartó `NULLS NOT
DISTINCT`, que sería lo equivalente: es Postgres 15+ y SQLite no lo tiene.

### `siguiente_correlativo` solo mira lo emitido

Es la mitad del arreglo, no un extra. Relajar la constraint sin esto habría
convertido un choque ruidoso (un 500 al registrar) en uno silencioso (la serie
propia numerando detrás de la del proveedor).

### La factura recibida gana tres columnas

`emisor_num_doc` (RUC, o DNI de un RHE de persona natural), `fecha_emision`
(`Date`: una factura declara un día, no una hora) y `total` (lo que dice el
papel, IGV incluido). Las tres nullable: un comprobante emitido no las usa.

`emisor_num_doc` **no se teclea por defecto**: sale de `proveedor.ruc`. El
emisor de la factura de una compra es el proveedor de esa compra, y pedirlo
otra vez son dos verdades sobre el mismo dato. Se admite mandarlo solo para el
caso en que el papel diga otra cosa.

### El evento no cambia su `monto`

`purchases.comprobante_conforme` sigue publicando `orden.total` —la base—
porque su plantilla del PCGE es `monto_es="base"` y apuntarla al total
facturado duplicaría el IGV que ese mismo asiento agrega. El importe del papel
viaja aditivamente como `total_documento`, hoy **sin consumidor**: existe para
la conciliación que la deuda de `purchases` ya tiene anotada.

### `tipo` y `sustento` pasan a `Literal`

Eran `str` libres contra columnas `Enum` con CHECK: un valor fuera de rango no
se rechazaba en la API, moría en el `flush` con un 500 que no decía qué campo
estaba mal. Es el mismo defecto que `ProveedorUpdate` ya había corregido.

## Lo que NO se hizo

- **Rellenar `total` y `fecha_emision` en los comprobantes ya registrados.**
  `orden_compra.total` no es lo que dice la factura, y copiarlo produciría un
  número que parece venir del papel sin venir de él — indistinguible después.
  Quedan NULL y la pantalla muestra el total de la OC en su propia columna,
  que es honesto.
- **Una tabla aparte para los comprobantes recibidos.** Duplicaría el modelo
  que `shared` existe para no duplicar, y `accounting` tendría que leer dos.
- **Prefijar la serie con el RUC del emisor.** Ensucia el dato que se imprime
  y se declara.
- **Aplicar la nota de crédito recibida.** `nc` queda fuera del `Literal` de
  entrada: no hay flujo que la aplique, y aceptarla dejaría entrar un
  documento que nada descuenta.

## Consecuencias

- Migración `0a056863874b`. El relleno deriva `emisor_num_doc` de la OC de
  cada comprobante recibido — es lo único derivable con certeza, y es de lo
  que depende la unicidad nueva.
- El `downgrade` **puede fallar** con datos reales: si para entonces existen
  dos facturas de proveedores distintos con la misma serie y número, la
  constraint global no se puede recrear. Es información sobre lo que este
  cambio hizo posible, no un defecto. En CI el `downgrade base` corre sobre
  base vacía.
- Un comprobante recibido duplicado ahora responde 409 con el documento
  nombrado, y no un 500: el índice sigue siendo la red que ataja la carrera
  entre dos usuarios, pero el mensaje lo da la capa de aplicación.
- `compra_id` gana índice. La ficha de una OC pide sus comprobantes por ahí y
  la columna no tiene FK —apunta a otro módulo—, así que tampoco tenía índice.
