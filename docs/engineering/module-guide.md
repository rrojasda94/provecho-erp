# Cómo crear un módulo

Checklist completo, de principio a fin, para agregar un módulo nuevo a
Provecho. Existe porque la estructura de un módulo sí es replicable —los ocho
módulos actuales tienen exactamente la misma forma— pero **activarlo requiere
tocar siete lugares fuera del módulo**, y olvidarse de uno da errores que no
apuntan a la causa (tabla que Alembic no ve, permiso que nadie puede tener,
módulo que no aparece en el home).

Reglas de fondo (por qué las capas son así, qué no se puede importar):
[engineering-guide.md](engineering-guide.md). Este documento es el "en qué
orden y qué archivos toco".

**Módulo de referencia: `purchases`.** Es el más chico que está completo —
dominio, casos de uso, repositorios, router, eventos publicados y consumidos.
Léelo antes de escribir nada; copiarlo es la vía correcta.

## 0. Antes de escribir código

1. `src/modules/<modulo>/README.md`: objetivo, responsabilidades, casos de
   uso, eventos que publica/consume, endpoints, entidades, reglas,
   dependencias. **Va primero** (regla de CLAUDE.md: especificación antes de
   implementación).
2. Reglas nuevas → [../domain/business-rules.md](../domain/business-rules.md)
   con código `RN-<área>-nnn`. Estados → [../domain/state-machines.md](../domain/state-machines.md).
   Términos → [../foundation/glossary.md](../foundation/glossary.md).
3. Eventos nuevos → fila en [../architecture/events.md](../architecture/events.md)
   ANTES de publicarlos. Nombre `<modulo>.<hecho_en_pasado>`.
4. Si hay una alternativa de diseño real, ADR en `../architecture/adr/`.

## 1. El módulo

```
src/modules/<modulo>/
  README.md
  __init__.py
  domain/          reglas puras (rules.py). Sin FastAPI, SQLAlchemy ni red.
  application/     casos de uso, uno por archivo. errors.py, scope.py.
                   listeners.py SOLO si consume eventos de otro módulo.
                   queries_publicas.py SOLO si otro módulo debe leerlo.
  infrastructure/
    models/        modelos SQLAlchemy, uno por archivo, reexportados en
                   __init__.py.
    repositories.py
  api/
    routers.py     endpoints
    schemas.py     Pydantic de entrada/salida
```

Crear solo las capas que se implementan. Dependencias permitidas:
`api → application → domain`; `infrastructure` implementa lo que el dominio
declara. Al dominio de otro módulo **nunca** se entra: eventos o contrato
público (`api.deps`, `application.queries_publicas`).

## 2. Los siete registros fuera del módulo

| # | Qué | Dónde | Si falta |
|---|-----|-------|----------|
| 1 | Router | [`src/core/app.py`](../../src/core/app.py) — import + `include_router(..., prefix="/api/v1")` | El módulo no existe para el mundo |
| 2 | Tag OpenAPI | mismo `app.py`, `TAGS_METADATA` | `/docs` agrupa sin explicar qué es |
| 3 | Listeners | mismo `app.py`, `<modulo>_listeners.register()` | Los eventos llegan a nadie |
| 4 | Modelos | [`src/core/models_registry.py`](../../src/core/models_registry.py) | **Alembic no ve las tablas** y `autogenerate` propone borrarlas |
| 5 | Migración | `alembic revision --autogenerate -m "..."` (revisar a mano) | La tabla no existe en la base |
| 6 | Permisos | `PERMISOS` y `ROLES` en [`src/seeders/seed.py`](../../src/seeders/seed.py) | Todo endpoint responde 403: el permiso no se le puede dar a nadie |
| 7 | Frontend | `MODULOS` en [`frontend/lib/modulos.ts`](../../frontend/lib/modulos.ts) + carpeta en `frontend/app/(app)/<modulo>/` | El módulo no aparece en el home ni en el sidebar |

Tres de los siete están cubiertos por tests: 1, 4 y 6 fallan en
`tests/test_arquitectura.py` si te los saltas. Los otros cuatro son
disciplina — el 5 lo caza `alembic check` en CI, el 2, 3 y 7 no los caza
nadie.

### Detalle de los que tienen trampa

**4 — `models_registry.py`.** `Base.metadata` se puebla solo con los modelos
importados. Alembic y los tests leen de ahí. Un módulo con modelos y sin su
línea de import genera una migración que **borra** tablas ajenas.

**6 — permisos.** Código `<modulo>.<verbo>` (`purchases.aprobar`,
`inventory.contar`). Se declara en `PERMISOS`, se asigna a los roles que
corresponda en `ROLES`, y se exige en el endpoint con
`Depends(require_permission(CODIGO))`. Los códigos van en constantes al tope
de `routers.py`, no como literales sueltos. Deny por defecto: sin permiso
declarado el endpoint queda abierto solo si es deliberado (catálogos de
referencia), y eso se comenta en el código.

**7 — frontend.** `prefijoPermiso` filtra el ícono del home; el guard real va
en el `layout.tsx` del módulo. El grid no es control de acceso.

## 3. Tenant, auditoría, idempotencia

- Toda consulta se escopa por empresa/marca/sucursal (ADR-004,
  [`src/core/tenant.py`](../../src/core/tenant.py)). Pedir datos de otro
  tenant es 403 y se resuelve en `core`, no en cada router.
- Operaciones con dinero: idempotencia por clave del cliente.
- Cambios sensibles: auditoría con
  [`src.shared.auditoria.registrar`](../../src/shared/auditoria.py) (quién,
  qué, cuándo, dónde, valor anterior/nuevo; ADR-031). Se audita el acto de
  autoridad —aprobar, autorizar, anular, descontar, pagar, anonimizar—, no
  cada `UPDATE`. Va en la misma sesión que el cambio, y con `empresa_id`/
  `sucursal_id` si el caso de uso los tiene a mano: sin ellos la fila solo
  la puede leer un superusuario.

## 4. Pruebas y cierre

- `tests/test_<modulo>.py` en el mismo commit que el comportamiento.
  Dominio aislado; infraestructura contra base.
- `ruff check src tests` y `eslint` en verde.
- `CHANGELOG.md` (Unreleased) y `ROADMAP.md` (fila del módulo + lo diferido
  en Deuda técnica) actualizados en el mismo cambio.
- `docs/product/modules.md` apunta al README del módulo nuevo.

## Lo que todavía no es automático

No hay `scaffold` ni manifiesto por módulo: el registro de los siete puntos
es manual, y por eso un módulo **no es removible borrando su carpeta** — deja
imports rotos en `core`. Está declarado como deuda técnica en
`ROADMAP.md` → Deuda técnica → Transversal. Mientras tanto, esta lista es el
contrato.
