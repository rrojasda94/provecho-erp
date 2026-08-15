# Trabajar en varias ramas a la vez

Este proyecto se construye con varias sesiones de agente corriendo en
paralelo, cada una en su propio worktree. Eso multiplica el trabajo, pero solo
si las ramas se ven entre sí. El 2026-08-08 no se veían y salieron **cuatro
PRs distintos arreglando exactamente el mismo bug** (#40, #46, #47, #48): tres
se cerraron sin mergear. La misma tarde, tres ramas pidieron el mismo número
de ADR y dos re-encadenaron la misma migración.

Ninguna de esas colisiones era un problema de código. Eran de visibilidad.

## Antes de empezar una rama

```bash
gh pr list --state open          # ¿alguien ya está en esto?
git fetch origin --prune
```

Si lo que ibas a hacer ya tiene rama, sumate a esa. Dos arreglos del mismo
bug no se promedian: uno se tira.

## Apenas hay un commit

Abrir el **PR en borrador**. No al terminar: al empezar.

```bash
git push -u origin <rama>
gh pr create --draft --title "..." --body "qué se está haciendo"
```

Un PR en borrador cuesta nada y es lo único que hace visible una rama antes de
estar lista. Sin él, la rama existe solo en el disco de quien la empezó.

## Los recursos que se numeran solos

Son los que chocan sin que el contenido se contradiga. **El segundo que llega
renumera**, siempre, y lo hace antes de mergear:

| Recurso | Qué mirar | Qué hace el segundo |
|---|---|---|
| ADR | `docs/architecture/adr/` | Renombra su archivo al siguiente libre y arregla las referencias. `tests/test_repo_coherencia.py` falla si quedan dos con el mismo número |
| Migración Alembic | `alembic heads` | Re-encadena su `down_revision` a la cabeza nueva. El job `backend` falla con dos cabezas |
| Changelog | `changelog.d/` | Nada: un archivo por cambio, no hay punto de inserción compartido |
| Deuda técnica | `docs/roadmap/deuda/<área>.md` | Nada, salvo que sean de la misma área |

## Los recursos que no se numeran solos: puertos y bases

Los de arriba chocan al mergear. Éstos chocan **mientras se trabaja**, que es
peor: el síntoma no dice "otro agente", dice `EADDRINUSE`, o —el modo de
falla caro— Playwright **reusa el servidor del otro worktree** y la suite
corre contra código que no es el suyo, en verde.

Cada sesión toma un **slot**, el mismo número para todo:

| Slot | `E2E_PUERTO_API` | `E2E_PUERTO_WEB` | Base Postgres de trabajo |
|---|---|---|---|
| 0 (defecto) | 8100 | 3100 | `provecho` |
| 1 | 8101 | 3101 | `provecho_slot1` |
| 2 | 8102 | 3102 | `provecho_slot2` |
| N | `810N` | `310N` | `provecho_slotN` |

```bash
# Playwright, las dos suites
E2E_PUERTO_API=8101 E2E_PUERTO_WEB=3101 npm run test:e2e
E2E_PUERTO_API=8101 E2E_PUERTO_WEB=3101 npm run test:uso

# Trabajo manual contra la API: base propia, en el `.env` del worktree
DATABASE_URL=postgresql+psycopg://provecho:provecho@localhost:5432/provecho_slot1
```

El **8100 del slot 0 suele estar tomado por el `docker-compose`** de la
máquina, así que un agente que corra con los valores por defecto choca contra
él sin que haya ningún otro agente involucrado. Tomar un slot desde el
principio evita esa media hora.

Las **suites de Playwright no necesitan Postgres**: corren contra un SQLite
desechable (`e2e.db`) en la raíz del worktree, que ya es propio de cada uno.
La base por slot es para el trabajo manual contra la API y las pantallas de
desarrollo, donde dos agentes sí compartirían datos.

`pytest` tampoco necesita coordinación: usa SQLite en memoria.

### El intérprete de Python

Un worktree **no tiene `.venv` propio** — el entorno vive una sola vez en la
raíz del repo principal. Los scripts de la suite lo resuelven solos
(`frontend/e2e/interprete.mjs`): `.venv` del worktree → `.venv` del repo
principal (por `git rev-parse --git-common-dir`) → `python` del PATH. `PYTHON`
sigue mandando sobre todo si hace falta apuntar a otro lado. **Nunca
commitear una ruta absoluta**: son distintas en cada máquina.

## Integrar `main`, no esperar a que duela

`main` exige que la rama esté al día antes de mergear. Integrarla seguido
—no una vez al final— es la diferencia entre resolver tres líneas y resolver
un archivo entero.

```bash
git fetch origin && git merge origin/main
```

## Cerrar el worktree

Cuando el PR se mergea, el worktree ya no sirve:

```bash
git worktree remove .claude/worktrees/<nombre>
```

Dejarlos vivos es cómo se llega a dieciocho, y con dieciocho nadie sabe cuál
tiene trabajo de verdad. Dos veces —`frontend/lib/carga.ts` y el checkout
principal— hubo trabajo terminado que nunca llegó a `main` porque su rama
nunca tuvo PR.
