# ADR-018 — Cobro dividido, mesa tipada y descuento de orden

- **Estado:** aceptado
- **Fecha:** 2026-07-28
- **Contexto previo:** [ADR-005](ADR-005-facturacion-electronica-factiliza.md)
  (emisión electrónica), [ADR-009](ADR-009-modo-offline-pdv.md) (replay del hub),
  [ADR-012](ADR-012-dashboard-gerencial-y-slice-minimo-de-caja.md) (caja).

## Contexto

El diseño del punto de venta (prototipo interactivo, julio 2026) dejó al
descubierto cuatro cosas que el PDV necesita y el modelo no daba:

1. **Mesa como texto libre.** `venta.referencia_atencion` guardaba `"Mesa 5"`
   como cadena. No permite un mapa de salón, ni saber qué mesas están
   ocupadas, ni reportar ventas por mesa, ni validar que la mesa exista.
2. **Un comprobante por venta.** `crear_comprobante_pendiente` era idempotente
   por `venta_id`. Cobrar solo algunos productos de la mesa — caso corriente
   en restaurante, cada comensal paga lo suyo con su propio comprobante — era
   imposible.
3. **Receptor atado a cliente registrado.** `tipo_comprobante()` exigía un
   `cliente` de tipo jurídico en la base para emitir factura. En caja el
   cliente dicta su RUC en el momento del cobro y nadie lo registra.
4. **Descuento sin trazabilidad.** Solo existía `venta_item.descuento`, un
   monto por línea que sale de listas promocionales. No había forma de aplicar
   un descuento al total, ni de saber quién lo autorizó ni por qué.

## Decisión

### 1. `mesa` como entidad, en el módulo `sales`

Tabla `mesa` (`sucursal_id`, `numero`, `zona`, `capacidad`, `activa`), con
`venta.mesa_id` y `venta.comensales`.

Vive en `sales` y no en `users` junto a `sucursal`: quien le da sentido es la
toma de pedido, y `sales` no puede importar el dominio de otro módulo
(CLAUDE.md). De `users` solo se referencia `sucursal_id`, igual que ya hace
`punto_venta`.

**El mapa de mesas es una lectura derivada, no un estado.** Una mesa está
ocupada si tiene una venta en `orden`; no existe `mesa.ocupada`. Dos fuentes
de verdad para el mismo hecho se desincronizan el primer día que alguien
cobre desde otra caja.

`referencia_atencion` **no se elimina**: sigue siendo el texto libre para
takeout y delivery (`"Carlos"`, `"Rappi #1042"`), que es su uso legítimo.

### 2. `grupo_cobro` como discriminador, no entidad `Cuenta`

Columna entera (default `1`) en `venta_item`, `pago` y `comprobante`. Los
pagos de un grupo suman contra el total de *ese* grupo; la venta pasa a
`pagada` recién cuando ningún grupo queda con saldo.

Se descartó una entidad `cuenta_venta` con sus propios ítems, pagos y
comprobante. Sería más limpia conceptualmente, pero obliga a refactorizar tres
tablas ya en uso y a migrar sus datos, a cambio de una expresividad que hoy
nadie pide. Si aparece la necesidad de una cuenta con vida propia (nombre,
apertura y cierre independientes, transferencia entre mesas), esta decisión se
revisa.

**La clave de idempotencia del grupo 1 no cambia.** `clave_idempotencia()`
devuelve `venta:{id}` para el grupo 1 y `venta:{id}:g{n}` para el resto: los
comprobantes emitidos antes de este cambio siguen resolviendo idempotentes.

### 3. Receptor en el comprobante

`comprobante.receptor_num_doc` y `receptor_nombre`. Cuando vienen informados
ganan sobre `venta.cliente_id` al armar el envío a SUNAT; vacíos, se resuelve
desde el cliente como siempre.

El largo del documento decide el tipo:
`tipo_comprobante_por_documento()` — 11 dígitos es RUC y obliga factura; 8
(DNI), `00000000` o vacío van a boleta. Un documento a medio teclear se
rechaza en el dominio, no en SUNAT.

`tipo_comprobante()` (la regla vieja, por cliente registrado) **se conserva**
y sigue aplicando cuando el PDV no informa documento.

### 4. Descuento de orden en columnas de `venta`

`descuento_modo` (`porcentaje`/`monto`), `descuento_valor`,
`descuento_motivo` y `descuento_autorizado_por`. Motivo y autorizador son
obligatorios: sin saber quién regaló margen y por qué, el dato no sirve en el
reporte de descuentos.

Se descartó una entidad `descuento_venta` (permitiría varios descuentos
acumulados sobre una orden) por ser más piezas de las que el caso necesita
hoy: un descuento por orden.

El permiso `sales.aplicar_descuento` es de **supervisor**, separado de
`sales.cobrar`, para que el cajero que lo pide no sea quien lo autoriza.

`venta.total` se sincroniza al aplicar o quitar el descuento: siempre es lo
que el cliente debe pagar. Si no, el cierre de caja cuadraría contra un total
irreal.

**El descuento se prorratea entre los grupos de cobro** según lo que pesa cada
uno. Sin prorrateo, la primera cuenta en cobrarse se llevaría todo el
beneficio. Al emitir, baja a las líneas vía `repartir_descuento()`, con el
residuo de redondeo en la línea más grande para que la suma cuadre al céntimo.

### 5. `persona.numero_documento` pasa a opcional

Migración `e1c4a9d6b038`. `numero_documento` y `tipo_documento` de `persona`
dejan de ser obligatorios; el UNIQUE se conserva (un índice único admite
varios NULL).

El motivo es operativo: **no todo cliente quiere dar su DNI en el
mostrador**, y negarse a registrarlo por eso pierde la venta y su historial.
Para una persona natural basta el **teléfono**, que además es más fácil de
pedir y sirve para encontrarla después. El documento se completa cuando al
cliente le convenga — `PATCH /sales/clientes/{id}/documento` (RN-PTS-004).

Para **facturar a una empresa el RUC sigue siendo obligatorio**: sin él no
hay factura.

**Trabajador y usuario siguen exigiendo documento.** Esa validación vive en
`users.application.admin`, no en el esquema, porque `persona` es compartida
y no todos sus roles tienen la misma exigencia. Aflojar la columna no
aflojó ninguna de esas reglas.

Un cliente sin documento, o con el genérico `00000000`, **no cuenta como
identificado**: compra, recibe su boleta a su nombre y figura en el
historial, pero queda fuera de las promociones reservadas a clientes
registrados con documento (RN-PTS-005). Se resolvió como **regla derivada**
(`rules.cliente_identificado`) y no como columna: guardar el mismo hecho dos
veces solo crea la ocasión de que se contradigan — mismo criterio que con la
ocupación de mesa.

`00000000` se persiste como `NULL`, no literal: es "sin documento", no un
documento, y guardarlo tal cual haría chocar al segundo anónimo contra el
UNIQUE.

Búsqueda de caja por **teléfono, documento o nombre**
(`GET /sales/clientes/buscar?q=`, RN-PTS-006), separada del listado de
análisis externo, que tiene otro permiso.

### 6. Autorización de supervisor como elevación de corta vida

`POST /auth/autorizar` recibe usuario + PIN + permiso, verifica **ambos** y
devuelve un JWT de 3 minutos con `typ=autorizacion` y el permiso concedido.
La operación siguiente lo presenta y el servidor deriva de ahí quién
autorizó (RN-AUD-005).

Corrige un defecto que introdujo la primera versión de este ADR: el
descuento recibía `autorizado_por` como UUID **en el cuerpo del request**,
sin validar. El permiso se comprobaba contra el token de quien llamaba, así
que el cajero ni siquiera podía ejecutarlo, y el campo de auditoría era
falsificable — exactamente el dato que justifica pedir autorización.

Tres decisiones dentro de la decisión:

- **Un access token normal no sirve como autorización** (`typ` distinto). Si
  sirviera, el cajero se autorizaría con su propia sesión.
- **La elevación está acotada a un permiso**: una obtenida para descontar no
  vale para anular.
- **Va detrás del mismo rate limit que el login**: es un endpoint que recibe
  PINes; sin freno sería el camino cómodo para probarlos. El error es el
  mismo tenga o no el permiso, para no revelar qué PIN es válido ni quién es
  supervisor.

Aplica hoy a descuento de orden, anulación de líneas enviadas y retiro de
efectivo del cajón.

### 7. `json` → `jsonb` en cuatro columnas

Los modelos declaran `JsonB` (`JSON().with_variant(JSONB(), "postgresql")`),
pero cuatro migraciones antiguas crearon la columna con `sa.JSON()` a secas:
`acta.participantes`, `boleta_pago.ingresos`, `boleta_pago.descuentos` y
`comprobante.respuesta_proveedor` quedaron como `json` mientras las otras 19
columnas JSON del esquema son `jsonb`.

No es cosmético: `json` guarda el texto literal y **no admite los operadores
ni los índices GIN de `jsonb`**. Se corrige en `b6d41e07af92`; la conversión
es segura porque todo `json` válido es `jsonb` válido.

Apareció al agregar `alembic check` al CI. Sin arreglarlo, ese chequeo
quedaba en rojo permanente — y un chequeo que siempre falla es un chequeo
que nadie mira.

## Frontera explícita: esto NO son promociones

Lo decidido acá es el **descuento manual**: lo aplica un cajero, lo autoriza un
supervisor, tiene motivo y sale en reportes.

Las **promociones** son otra cosa y no entran en este ADR:

- se definen a nivel de **marca y sucursal**, no de venta;
- son **condicionales** — se activan solas si el pedido cumple reglas
  ("segunda pizza a mitad de precio si pide dos del mismo tamaño, en los días
  en que la promoción está activa, sobre el precio base de la más barata, sin
  incluir extras");
- requieren un **motor de reglas** con vigencia, condiciones de activación y
  base de cálculo propia.

Hoy lo más cercano es `lista_precio.es_promocional`, que solo cambia el precio
de un producto en un ámbito y período; no evalúa condiciones sobre el
contenido del pedido. El motor de promociones queda pendiente en `ROADMAP.md`.

Quien construya ese motor **no debe reutilizar** `venta.descuento_*`: son
campos de un acto humano autorizado, con motivo y responsable. Mezclarlos con
un descuento automático haría imposible auditar cuál fue cuál.

## Consecuencias

**A favor**

- El PDV puede dividir cuentas, cobrar por partes y emitir un comprobante por
  pagador, con receptor distinto en cada uno.
- El salón es consultable: mapa de mesas, ocupación, ventas por mesa.
- Los descuentos son auditables y reportables.
- Migración sin backfill: todo lo agregado es nullable o trae
  `server_default`. Una venta anterior es una venta con una sola cuenta.
- El mostrador deja de perder al cliente que no quiere dar su DNI: se
  registra por teléfono y el documento entra después.

**En contra**

- `venta_id` deja de identificar un único comprobante. Todo código que asuma
  «un comprobante por venta» debe usar `por_venta_y_grupo` o
  `todos_de_venta`; `por_venta` quedó documentado como «el primero».
- `grupo_cobro` es un entero sin entidad detrás: nada impide un grupo 7 sin
  grupos 1-6. Se valida en el caso de uso (`grupo_cobro` debe existir entre
  los ítems), no en el esquema.
- El replay del hub (ADR-009) transporta cuatro campos más por venta y uno por
  ítem y por pago. Los lotes viejos siguen entrando: los campos nuevos son
  opcionales y `grupo_cobro` asume 1.
- `persona.numero_documento` ya no garantiza estar presente. Todo código que
  lo lea debe tolerar `NULL` — el camino de emisión ya lo hace
  (`_cliente_para_sunat` cae al documento genérico manteniendo el nombre).
  El `downgrade` de `e1c4a9d6b038` rellena las personas sin documento con un
  genérico derivado del id, porque el `NOT NULL` fallaría con ellas.

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| `venta.mesa_numero` como entero, sin tabla | Sin catálogo por sucursal no hay zonas, ni capacidad, ni validación de existencia |
| `mesa` en el módulo `users` | Obligaría a `sales` a importar dominio ajeno o a abrir un contrato público solo para esto |
| Entidad `cuenta_venta` | Refactor de tres tablas en uso para una expresividad que nadie pide todavía |
| Reutilizar `venta_item.descuento` para el descuento de orden | Pierde motivo y autorizador — justo la traza que justifica el PIN de supervisor |
| Emitir siempre desde `cliente` registrado | Obligaría a registrar un cliente por cada factura pedida en caja |
| Entidad `extra` propia, separada de `producto_comercial` | Habría que duplicar precio por lista, aparición en carta y descuento de insumos. El extra ya es "algo con receta que se vende": es un producto |
| `autorizado_por` como campo del request | Firma falsificable: cualquiera atribuye un descuento al supervisor sin que esté presente |
| Que el supervisor inicie sesión para autorizar | Obliga a cerrar la sesión del cajero en plena atención; en la práctica termina en PIN compartido |
| Exigir DNI para registrar cliente | El cliente que no quiere darlo no se registra, y se pierde su historial. El teléfono cumple la misma función identificatoria y es más fácil de pedir |
| Guardar el nombre del cliente ligero en `cliente` en vez de `persona` | Duplicaría la fuente única de datos de personas naturales (RN-GEN-007): dos lugares donde vive el mismo nombre |
| Columna `cliente.identificado` | El dato ya está en el documento. Una columna aparte se desincroniza en cuanto alguien complete el DNI sin actualizarla |
