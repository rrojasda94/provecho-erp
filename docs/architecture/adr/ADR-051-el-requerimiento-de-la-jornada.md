# ADR-051 — El requerimiento de la jornada

- **Estado:** aceptada
- **Fecha:** 2026-08-19
- **Contexto:** `inventory` (solicitudes, stock, conteos), `frontend/app/(app)/inventario/solicitudes`,
  `frontend/app/(app)/inventario/conteos`
- **Relacionado:** ADR-020 (abastecimiento interno), ADR-026 (paginación),
  RN-INV-001/006/009/010/013/015/022

## Contexto

El módulo `inventory` tenía la API completa de solicitud de insumos desde el
slice 4 (ADR-020) — crear, aprobar, rechazar, cancelar, listar — y ninguna
pantalla. El usuario preguntó, en orden: si el personal puede armar una lista
de pedido con un botón, si se arma sola con lo que está bajo mínimo, si se
puede sumar algo que no está bajo mínimo por decisión del local, y si el
almacén distingue una cosa de la otra. Las cuatro preguntas apuntaban al mismo
hueco: `solicitud_item` era `sku_id` + tres cantidades, sin origen y sin
urgencia, y no había ningún camino para armar la lista salvo llamar al
endpoint a mano con los SKU ya elegidos.

`GET /conteos` tampoco existía — un conteo solo se podía pedir por su `id`, o
sea sabiéndolo de antemano —, así que la toma de inventario tenía el mismo
problema: API completa (`abrir/cantidades/cerrar/anular/programa`), cero
pantalla, cero forma de listar lo abierto.

## Decisión

### Un estado `borrador`, no un formulario precargado

Se evaluaron las dos: precargar el formulario en el cliente (sin persistir)
contra sumar `borrador` al enum de `solicitud_insumos.estado`. Se eligió
persistir porque el pedido era explícito — "se crea automáticamente un
borrador... durante la jornada" — y porque un formulario sin persistir no
sobrevive a que dos personas del mismo turno pasen por la pantalla en
momentos distintos, que es el caso normal de una cocina.

`borrador_del_almacen` es **get-or-create y uno por almacén**, no por
usuario: la jornada la levanta el turno completo, y dos listas paralelas para
el mismo almacén son el problema exacto que esto viene a resolver — el
central recibiría dos pedidos que se solapan y ninguno completo.

### Sugerencia por `stock_minimo`, aditiva y no autoritativa

`sugerir_items` reusa `stock_uc.consultar_stock` y `rules.stock_bajo`, que ya
existían desde el ajuste de inventario. La cantidad sugerida es
`cantidad_a_reponer` (lo que falta para volver al mínimo, o el mínimo entero
si el almacén quedó en cero).

Al volver a abrir el borrador, `refrescar_sugerencias` **suma** los SKU que
cayeron bajo mínimo desde la última vez y no toca nada más: no corrige
cantidades ya tecleadas ni saca ítems que se repusieron. Una sugerencia que
pisara lo que el personal ya escribió convertiría la pantalla en algo que hay
que revisar dos veces, y un SKU que alguien dejó en la lista a propósito
—porque sabe que va a volver a faltar— no es un error a corregir.

El refresco corre **al leer la pantalla**, no en un job. `# ponytail`: el
techo es que si nadie abre la pantalla nadie ve lo nuevo; el upgrade, si hace
falta, es la tarea diaria que ya corre para `inventory.conteo_vencido`
(`application/tasks.py`). No se justificaba duplicar ese mecanismo para una
sugerencia que de todas formas se recalcula gratis cada vez que alguien mira.

### La urgencia se estampa, no se deriva

`solicitud_item.bajo_minimo_al_pedir` se fija al momento de agregar el ítem
—por sugerencia (`true`) o a mano (`_bajo_minimo` contra el stock actual)— y
nunca se recalcula. Es la respuesta a la pregunta del usuario sobre si el
almacén distingue una cosa de otra: sí, con esta columna.

Derivarla en el momento de leer la solicitud habría contado una historia
distinta de la que el local vio: entre que se pide y se aprueba pasan horas,
el stock se mueve, y un SKU que estaba en cero al pedir puede llegar
repuesto al momento de aprobar (por una transferencia lateral, por ejemplo).
Estampar es lo único que preserva "esto era urgente cuando el local lo pidió"
como hecho auditable, en línea con el resto del módulo (`cantidad_solicitada`
vs. `cantidad_aprobada` vs. `cantidad_despachada` existen por el mismo
motivo: tres momentos distintos, tres cantidades).

### `GET /conteos`, filtro por sucursal y marca via join

`ConteoRepo.q_list` y `SolicitudRepo.q_list` ganan `sucursal_id` y
`marca_id`, resueltos con un join `Almacen → Sucursal` porque las dos
entidades viven **por almacén** (RN-INV-020: la solicitud, ADR-019: el
conteo) y sucursal/marca cuelgan del almacén, no al revés. Sin columna
nueva: el dato ya existe una vez, en `almacen.sucursal_id` y
`sucursal.marca_id`.

## Contrato

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/inventory/solicitudes/borrador?almacen_id=` | Get-or-create + refresco. Va **antes** de `/{solicitud_id}` en el router (mismo motivo que `/conteos/programa`). |
| `POST` | `/inventory/solicitudes/{id}/items` | Agrega a mano; estampa `bajo_minimo_al_pedir`. |
| `PATCH` | `/inventory/solicitudes/{id}/items/{sku_id}` | Cambia cantidad; la urgencia no se toca. |
| `DELETE` | `/inventory/solicitudes/{id}/items/{sku_id}` | Quita, incluso uno sugerido. |
| `POST` | `/inventory/solicitudes/{id}/enviar` | `borrador → pendiente`; **re-resuelve** el abastecedor (RN-INV-022 pudo cambiar entre que se abrió la lista y se envió). |
| `GET` | `/inventory/conteos` | Paginado, con `almacen_id`/`estado`/`sucursal_id`/`marca_id`; el abierto encabeza. |

Las cuatro operaciones de edición del borrador reusan `SOLICITAR_INSUMOS`
—el mismo permiso que ya existía para crear una solicitud directa—, sin
permiso nuevo.

## Alcance de esta entrega

Solicitudes + Conteo, ambos con pantalla nueva. Recortar el aprobado por SKU
(`SolicitudAprobar.aprobadas`) no tiene formulario todavía —se aprueba lo
pedido tal cual—; queda en deuda técnica, igual que un selector de conteo por
lote/FEFO en la grilla de cantidades.

## Consecuencias

- Migración `b5f27ac41e83`: una columna (`solicitud_item.bajo_minimo_al_pedir`,
  `BOOLEAN NOT NULL DEFAULT false`). El estado `borrador` no necesitó
  migración: el enum de `solicitud_insumos.estado` es
  `Enum(..., native_enum=False)`, o sea VARCHAR sin CHECK
  (`create_constraint=False` en SQLAlchemy 2.x), y `"borrador"` (8) entra en
  el VARCHAR(10) que ya fijaba `"despachada"`. Verificado contra Postgres, no
  solo SQLite — es justo la clase de detalle (largo de columna) que SQLite no
  habría hecho fallar.
- El hub (ADR-009) **no sube borradores**: `pendientes()` los excluye
  explícitamente. Reproducir en la nube una lista que el local ni envió sería
  mandarla por su cuenta, lo contrario de lo que el estado existe para
  evitar. `SolicitudSyncIn` gana `bajo_minimo_al_pedir` por ítem —puesta por
  el local contra su propio stock offline— para que el replay no la
  recalcule contra el stock de la nube, que ya se movió mientras no había
  internet.
- `solicitudes_resumen_para_negociacion` (contrato público hacia `purchases`)
  excluye `borrador` además de `cancelada`: negociar volumen con una lista a
  medio llenar prometería al proveedor una demanda que nadie confirmó.
- Sin permisos nuevos, sin evento nuevo. `inventory.stock_bajo_minimo` sigue
  siendo el aviso "al cruzar"; esta pantalla es donde ese aviso se convierte
  en acción.
