# ADR-009 — Modo offline del PDV: hub local por sucursal

- Estado: aceptado. Fase 1 (diseño y plumbing base) 2026-07-26; **fase 2
  (motor de sync) 2026-07-27, ver "Fase 2" al final**
- Fecha: 2026-07-26 (fase 1) / 2026-07-27 (fase 2)

## Contexto

El PDV depende hoy de la API en la nube (Supabase + backend en VPS/GHCR).
Un corte de internet en la sucursal —común en Tarapoto— deja al restaurante
sin poder vender. El usuario pidió que funcione en tres formas de cliente
(webapp, Android, PC instalado) usando **equipos en la misma red local**, lo
que descarta un diseño puramente "cada dispositivo se las arregla solo": los
dispositivos de una misma sucursal deben verse entre sí durante el corte
(dos mozos no pueden vender la misma mesa dos veces sin saberlo).

Ningún frontend de PDV existe todavía (solo el scaffold de Next.js) — este
ADR fija la arquitectura de datos/sync antes de que se construya cualquier
cliente, para que los tres (web/Android/PC) construyan contra el mismo
contrato.

## Decisión

**Hub local dedicado por sucursal** (mini-PC o Raspberry Pi, siempre
encendido) que corre **la misma imagen Docker del backend**, apuntando a su
**propio Postgres local** — no una versión recortada del ERP, la misma
aplicación. Todos los dispositivos de la sucursal (tablets PDV, KDS,
Android, PC) le hablan **siempre** al hub por LAN, nunca directo a la nube.
El hub es quien decide si está en línea con la nube o no; los clientes ni
lo saben.

```
                    ┌─────────────────────────┐
                    │   Nube (Supabase + API)  │
                    └────────────▲─────────────┘
                                 │ sync periódico (API REST existente)
                                 │ solo cuando hay internet
                    ┌────────────┴─────────────┐
                    │   Hub local (sucursal)    │
                    │   misma imagen Docker     │
                    │   Postgres local propio   │
                    └────────────▲─────────────┘
                                 │ LAN (siempre, con o sin internet)
              ┌──────────────────┼──────────────────┐
        ┌─────┴─────┐     ┌──────┴──────┐     ┌──────┴──────┐
        │  PDV web   │     │  PDV Android │     │  PDV / KDS  │
        │  (tablet)  │     │  (celular)   │     │  (PC local) │
        └────────────┘     └──────────────┘     └─────────────┘
```

**Alcance offline** (decidido con el usuario): catálogo (`producto_comercial`,
`receta`, `categoria`, `medio_pago`), ventas/cobro/anulación, y KDS. Por
necesidad lógica —no pedida explícitamente, pero indispensable— también
`usuario`/`rol`/`permiso`/`usuario_rol`/`rol_permiso`/`usuario_sucursal`:
sin RBAC local, nadie puede autenticarse en el hub durante el corte. Y por
la misma razón, `articulo`/`stock`/`sku` de `inventory`: el listener
`sales.venta_confirmada → inventory` ya corre en el mismo proceso del hub
(es el mismo backend), así que si el catálogo pero no el stock estuviera
replicado, la venta fallaría al intentar descontar insumos.

**Fuera de alcance offline, a propósito**: histórico más allá del turno
actual, RRHH, contabilidad, reportes — nada de eso se opera desde el PDV.
`comprobante` se crea localmente en estado `pendiente` pero **la emisión a
Factiliza ocurre solo en la nube, después del sync** — el hub nunca llama a
SUNAT. Esto evita tener que correr Celery/Redis/worker en un Raspberry Pi.

**Transporte del sync: la propia API REST del ERP**, no un protocolo de
replicación aparte. El hub se autentica contra la nube con una cuenta de
servicio (`usuario.tipo=agente_ia`, una por sucursal, permisos mínimos de
lectura de catálogo/stock/usuarios y escritura de ventas/movimientos) usando
el mismo `/auth/login` que ya existe. Dos direcciones:

- **Descendente (nube → hub)**: el hub llama periódicamente a los endpoints
  de lectura que ya existen (`GET /sales/productos`, `/medios-pago`,
  `GET /inventory/stock`, `GET /users/users|roles|permisos`) filtrados por
  `empresa_id`/`sucursal_id`, y hace upsert local. Watermark por
  `updated_at` (ya presente en todo modelo vía `TimestampMixin`) — no hace
  falta tabla de control aparte.
- **Ascendente (hub → nube)**: cuando el hub confirma conectividad, repite
  hacia la nube las mismas llamadas que ya ejecutó localmente
  (`POST /ventas`, `/pagos`, `/anular`), con la **misma `idempotency_key`**
  generada al momento de crear cada cosa offline. La nube las trata como
  cualquier request normal — no hace falta lógica de replicación especial
  del lado servidor.

**JWT compartido**: el hub usa el **mismo `JWT_SECRET`** que la nube (fijado
al desplegar, no sincronizado dinámicamente). Un login hecho en el hub
durante el corte sigue siendo válido si la sesión llega a tocar la nube más
tarde, sin tener que reautenticar.

## Consecuencias

- **Requiere un cambio previo** (hecho en la fase 2): hoy
  `Venta`/`Pago`/`MovimientoInventario` usan `UuidPkMixin` con
  `default=uuid.uuid4` — el UUID se genera en la capa ORM de Python al
  construir el objeto, no en la base de datos. Esto significa que **ya es
  posible** pasar un `id` explícito al constructor sin migración ni cambio
  de esquema — falta solo extender la firma de `crear_venta`/`registrar_pago`
  (y equivalentes) para aceptar un `id: uuid.UUID | None = None` opcional y
  pasarlo al modelo. Sin esto, el hub y la nube generarían UUIDs distintos
  para la misma venta al reintentar el POST, y haría falta una tabla de
  mapeo hub-id↔nube-id que el diseño actual evita. Cambio pequeño,
  retrocompatible (parámetro opcional), pero toca `sales`/`inventory`.
- El hub corre **sin Celery/Redis/worker**: la emisión de comprobantes queda
  exclusivamente del lado nube. Reduce el footprint del Raspberry Pi a
  Postgres + la API, nada más.
- **Rate limit de login** (`src/core/rate_limit.py`) no aplica dentro del
  hub — es una LAN de confianza de un solo local, no internet público. Se
  documenta como decisión, no como omisión.
- Si el hub mismo se cae (no solo internet), la sucursal entera pierde el
  PDV — no hay redundancia de hub. Aceptado como riesgo por ahora; mitigación
  futura (imagen de respaldo lista para flashear) queda en deuda técnica.
- Un hub offline por días que se reconecta contra un esquema de nube ya
  migrado necesita `alembic upgrade head` también en el hub antes de
  sincronizar — mismo runbook de despliegue que la nube (ADR-008), replicado
  por sucursal.
- Descubrimiento del hub en la LAN (mDNS tipo `sucursal.local`, o IP fija
  configurada una vez por dispositivo) es una decisión de cliente, no de
  este ADR — se resuelve al construir cada app.

## Alternativas descartadas

- **Sin hub, cada dispositivo sincroniza solo (CRDT o similar)** — descartada
  por el propio requisito del usuario ("equipos en la misma red local"): sin
  un punto central en la sucursal, dos dispositivos no se ven entre sí
  durante el corte. Además, resolver conflictos de escritura concurrente
  (CRDT) es complejidad real que este dominio no necesita: con un hub único
  por sucursal, cada partición de datos (`sucursal_id`) tiene un solo
  escritor, nunca dos hubs escribiendo la misma fila.
- **Una de las cajas existentes hace de hub** (sin hardware nuevo) —
  descartada por el usuario: si esa caja se reinicia o se apaga, cae el hub
  para todo el local, incluido el KDS de cocina.
- **Replicación lógica de Postgres (hub↔nube) en vez de sync por API REST**
  — descartada: expondría la base de datos directamente entre red local y
  nube (superficie de ataque mayor que la API ya autenticada), bypassea las
  reglas de negocio y permisos de la capa de aplicación (una fila replicada
  cruda no pasa por `require_permission` ni por las validaciones de
  dominio), y Supabase gestionado restringe el acceso de superusuario que la
  replicación lógica exige.
- **Réplica completa del ERP en el hub** (todo el histórico, RRHH,
  contabilidad) — descartada por el usuario: esos módulos no se operan
  desde el PDV: replicar todo triplica el trabajo de sync para datos que un
  corte de internet no necesita resolver.
- **Motor de sync a medida con tabla `outbox` transaccional** — considerada
  y diferida: útil si cada escritura tuviera que dispararse individualmente
  hacia la nube en el instante en que ocurre, pero el diseño elegido
  sincroniza por lotes con watermark de `updated_at`, que ya cubre el caso
  sin tabla nueva. Se reconsiderará si aparece necesidad real de sync
  cuasi-instantáneo entre hub y nube.

---

## Fase 2 — Motor de sync (2026-07-27)

La fase 1 dejó la config del hub, el detector de conectividad y
`/health/sync`. Esta fase construye el motor que de verdad sincroniza, y
en el camino corrige tres supuestos de la fase 1 que no sobrevivieron al
contacto con el código.

### Lo que se mantuvo

Todo lo estructural: hub por sucursal con la misma imagen, sync por la
propia API REST (no replicación de base), autenticación con cuenta de
servicio por `/auth/login`, JWT compartido, emisión de comprobantes solo
en la nube, y el hub sin Celery/Redis.

### Decisión 1 — El ciclo empuja primero y jala después

Un ciclo es **push y después pull**, nunca al revés. Si el hub jalara
primero, sobreescribiría su `stock` local con el de una nube que todavía
no sabe nada de las ventas del corte. Empujando primero, la nube procesa
esas ventas —su propio listener descuenta su propio stock— y lo que vuelve
en el pull ya es el estado correcto. Los dos lados convergen dentro del
mismo ciclo.

Corolario: **el hub NO empuja movimientos de inventario**. El listener
`sales.venta_confirmada` corre también en la nube al recibir la venta; si
además viajaran los movimientos del hub, el consumo se contaría dos veces.
El `id` client-generado de `movimiento_inventario` (el cambio previo que
pedía la fase 1) queda igual disponible en `registrar_movimiento`, pero no
lo usa el sync.

### Decisión 2 — Endpoints `/sync/pull` y `/sync/push` en vez de reusar los públicos

La fase 1 preveía que el hub llamara a los endpoints de lectura que ya
existen (`GET /sales/productos`, `/inventory/stock`, `/users/users`). Al
implementarlo no alcanzan, por tres razones concretas:

1. **No traen lo que el hub necesita.** `ProductoOut` no expone
   `empaque_id` ni `modalidades_empaque` (sin eso el descuento de empaque
   por modalidad no funciona offline), y no hay endpoint alguno de
   `receta`, `receta_item`, `sku`, `unidad_medida` ni `punto_venta`.
2. **Nada de eso es incremental.** Ninguno filtra por `updated_at`: un hub
   que sincroniza cada minuto bajaría el catálogo entero cada vez.
3. **El PIN.** Autenticarse en el hub durante un corte exige el
   `pin_hash` del usuario, y ese campo no puede aparecer en `UsuarioOut`
   —el endpoint de administración de usuarios lo consumen humanos—, pero
   sí tiene que llegar al hub.

Por el lado ascendente pasaba lo mismo: `POST /sales/ventas` toma el
`usuario_id` del JWT (todas las ventas sincronizadas quedarían a nombre de
la cuenta del hub, perdiendo quién vendió) y calcula `fecha_orden` y
`numero_orden` con el reloj y el correlativo de la nube — el número de
orden que el cliente ya vio impreso en su comanda no coincidiría.
Agregarle cuatro campos "solo para sync" al contrato público del PDV es
peor que darle a la replicación su propia puerta.

Entonces: **dos endpoints dedicados**, cada uno con su permiso
(`sync.leer`, `sync.empujar`), y el rol `hub_sucursal` que solo tiene esos
dos. Lo importante es que **`/sync/push` no escribe filas crudas**: ejecuta
los mismos casos de uso de `sales` que atiende un PDV en línea, con sus
validaciones, su idempotencia y sus eventos. La objeción que hundió a la
replicación lógica de Postgres —"una fila replicada cruda no pasa por
`require_permission` ni por las validaciones de dominio"— sigue en pie y
este diseño la respeta.

El tenant **no es un parámetro**: sale de las asignaciones de la cuenta de
servicio, que debe tener exactamente una sucursal. Un hub no puede pedir
el catálogo de otro local ni empujarle ventas aunque arme el request a
mano.

### Decisión 3 — Tabla `sync_watermark` (una fila por recurso y dirección)

La fase 1 decía "watermark por `updated_at`, no hace falta tabla de
control aparte". No alcanza, por dos motivos:

- El hub **escribe localmente** algunas de las tablas que replica: cada
  venta offline mueve `stock`. Su propio `max(updated_at)` refleja su
  última venta, no hasta dónde leyó de la nube.
- La dirección ascendente necesita memoria durable de qué se empujó, y eso
  no lo dice ningún dato local.

Sigue **sin ser un outbox** (la alternativa descartada más abajo): es una
fila por recurso —24 filas en total—, no una por escritura. Guarda además
el último error, que es lo que `/health/sync` muestra por recurso.

Política ante fallas: un recurso que falla **no avanza su marca** y se
reintenta entero al ciclo siguiente; los demás recursos siguen su curso.
Si la nube rechaza un ítem del push, el lote no avanza tampoco — perder
una venta en silencio es peor que reintentarla para siempre, y el error
queda visible en `/health/sync`. El costo asumido: un ítem que la nube
rechaza siempre frena su recurso hasta que alguien lo mire.

### Decisión 4 — El contrato de replicación es declarativo y vive en cada módulo

`core/sync` no conoce ninguna entidad de negocio. Cada módulo declara sus
`RecursoSync` en `application/sincronizacion.py` (qué modelo, qué campos
viajan, cómo se filtra por tenant y por qué el hub lo necesita) y
`core/sync/registro.py` los ensambla en orden de dependencia, igual que
`core/app.py` ensambla los routers. Un módulo nuevo se vuelve replicable
declarando su tupla; el motor no se toca. `campos` es contrato explícito:
agregar una columna al modelo **no** la manda al hub sin que alguien lo
decida.

### Lo que viaja y lo que no

Se replican 28 recursos: organización (grupo, empresa, marca, sucursal,
almacén), RBAC completo (persona, usuario, rol, permiso y sus
asignaciones), catálogo de inventario (unidades, categorías, artículos,
SKU, recetas, stock, lote y stock por lote) y catálogo comercial
(producto, medio de pago, punto de venta, pantallas KDS). Decisiones finas
dentro de eso:

- **`usuario.pin_hash` sí; `intentos_fallidos`/`bloqueado_hasta` no.** El
  hash es indispensable para autenticar offline. El lockout, en cambio, es
  estado vivo de cada lado: replicarlo bloquearía a un cajero en el local
  por intentos hechos contra la nube.
- **`persona` viaja recortada**: nombres, apellidos y documento; sin
  domicilio, teléfono, email ni fecha de nacimiento. El PDV muestra un
  nombre, no una ficha — minimización de datos (Ley 29733) sobre hardware
  que vive en un local, no en un datacenter.
- **Solo el almacén de la sucursal**, no el central de la empresa.
- **`lote` y `stock_lote` viajan** (agregados 2026-07-27 con FEFO,
  ADR-015): sin la fecha de vencimiento en el hub, la venta offline
  descontaría cualquier lote y la nube, al reprocesar el evento, elegiría
  otro. `stock_lote` lo escriben ambos lados y gana la nube en el pull,
  igual que `stock` y por la misma razón: el ciclo empuja antes de jalar.
- ~~**`receta` y `receta_item` viajan completas, sin filtro de tenant.**~~
  **Resuelto 2026-08-06** (migración `d5b81e0c37a4`): `receta` ganó su
  `empresa_id` y el hub recibe solo las de su empresa; `receta_item` se
  acota por su receta. La salida que este punto anticipaba —"cruzar
  `producto_comercial`, dominio de `sales`, desde `inventory`"— era la
  equivocada: el dueño del dato no era `sales`, era que a `receta` le
  faltaba la columna.
- **`cliente` no viaja**: una venta offline es anónima o con datos
  escritos a mano. Venta a cliente registrado exige estar en línea.
- **`venta_item.id` no se conserva** entre hub y nube (sí el de la venta):
  nada fuera del hub referencia un ítem, y el avance de KDS es local al
  local.
- **El precio cobrado sí viaja** (agregado 2026-07-27, con el precio
  server-side): el lote ascendente usa `VentaItemSyncIn`, que lleva
  `precio_unitario` y `descuento`, mientras el PDV en línea
  (`VentaItemIn`) ya no los manda — ahí el precio lo resuelve el servidor
  contra `lista_precio` (RN-PRC-003). Es deliberado: una venta ya cobrada
  conserva el precio al que se cobró. Recotizarla al reproducirla
  cambiaría el monto si la promoción venció entre el corte y el push, y la
  nube quedaría discrepando del comprobante que el cliente se llevó.
  Mismo criterio que `id`/`fecha_orden`/`numero_orden`: el replay
  reproduce un hecho, no lo vuelve a decidir. En sentido descendente el
  hub recibe `lista_precio` y `precio` (2 recursos nuevos entonces; 28 en
  total tras sumar `lote`/`stock_lote`): sin ellos no podría cotizar
  durante el corte.

### Consecuencias de la fase 2

- El hub corre **dos procesos**: la API que atiende a la LAN y el runner
  de sync (`python -m src.core.sync.runner`, servicio `sync` del
  `docker-compose.hub.yml`). Separados a propósito: si el sync se traba,
  el PDV sigue vendiendo.
- `sales.tasks.encolar` no hace nada en un hub. Sin esta guarda, cobrar
  durante un corte intentaría hablarle a un broker que en el Raspberry Pi
  no existe.
- Un `POST /sales/ventas` ahora acepta `id` del cliente. Es lo que permite
  que las tres apps (web/Android/PC) generen el identificador al crear la
  venta y no dependan del servidor para tenerlo.
- El alta de un hub es un comando: `python -m src.seeders.hub --sucursal
  <uuid> --username hub_<local>`, contra la nube.
- Queda pendiente **el frontend**: sigue sin existir un PDV que use nada
  de esto. El contrato ya está y es verificable (`GET /sync/recursos`
  documenta qué baja un hub y por qué).

### Alternativa descartada en esta fase

- **Un solo watermark global en vez de uno por recurso** — descartada: un
  error puntual en una tabla (una FK que todavía no bajó) frenaría el sync
  de todas las demás. Por recurso, el catálogo llega fresco aunque el
  stock esté fallando.
