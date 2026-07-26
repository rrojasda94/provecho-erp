# ADR-009 — Modo offline del PDV: hub local por sucursal

- Estado: aceptado (fase 1 — diseño y plumbing base); **fase 2 (motor de
  sync) requiere una decisión adicional, ver Consecuencias**
- Fecha: 2026-07-26

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

- **Requiere un cambio previo, no incluido en esta fase**: hoy
  `Venta`/`Pago`/`MovimientoInventario` usan `UuidPkMixin` con
  `default=uuid.uuid4` — el UUID se genera en la capa ORM de Python al
  construir el objeto, no en la base de datos. Esto significa que **ya es
  posible** pasar un `id` explícito al constructor sin migración ni cambio
  de esquema — falta solo extender la firma de `crear_venta`/`registrar_pago`
  (y equivalentes) para aceptar un `id: uuid.UUID | None = None` opcional y
  pasarlo al modelo. Sin esto, el hub y la nube generarían UUIDs distintos
  para la misma venta al reintentar el POST, y haría falta una tabla de
  mapeo hub-id↔nube-id que el diseño actual evita. Cambio pequeño,
  retrocompatible (parámetro opcional), pero toca `sales`/`inventory` y
  debe revisarse aparte — **no se implementa en este ADR**.
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
