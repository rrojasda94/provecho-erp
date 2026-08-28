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

**Barrer las referencias, no el repositorio entero.** El 2026-08-15 tres ramas
pidieron `ADR-048` el mismo día (proxy, caja y pinpad) y las tres lo
mencionaban en unos treinta archivos: ADR, ROADMAP, `00_PROJECT.md`, reglas de
negocio, comentarios de código y specs. Un `sed` global de `ADR-048` a
`ADR-049` pisa además las referencias legítimas de la rama que llegó primera,
que para entonces ya están en `main` y son correctas. La lista de archivos a
tocar es la de la propia rama:

```bash
git diff --name-only <base>..HEAD          # solo lo que tocó esta rama
```

Con dos excepciones que se revisan a mano: `ROADMAP.md` y `docs/00_PROJECT.md`
terminan nombrando **los tres** ADR, así que ahí se renumera la línea propia y
no el archivo. `openapi.json` no se edita: se regenera.

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

### Si el `webServer` de Playwright se agota esperando

`Timed out waiting 180000ms from config.webServer` con los dos puertos ya
tomados **no es un puerto ocupado**: es `next dev` compilando la primera ruta.
En un disco lento —o con dos agentes compilando a la vez— el arranque pasa
los tres minutos que Playwright espera, y el mensaje no menciona la
compilación por ningún lado.

La salida es levantar los servidores a mano, calentarlos y reusarlos con
`E2E_REUSAR`, que existe justamente para esto:

```bash
node e2e/preparar-bd.mjs          # borra e2e.db y siembra — antes de la API
node e2e/servidor-api.mjs &
node e2e/servidor-web.mjs &
curl -s -o /dev/null http://localhost:3100/login    # la primera tarda ~1 min
E2E_REUSAR=1 npx playwright test
```

El orden importa: `preparar-bd.mjs` borra `e2e.db`, y una API ya levantada lo
tiene abierto.

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

## Ramificar de una rama que todavía no se mergeó

A veces hace falta: la rama del arnés traía los puertos por slot y la suite
`uso/`, y las cuatro ramas siguientes los necesitaban para poder correr
Playwright a la vez. Salir de `origin/main` habría significado esperar.

El costo hay que saberlo de antemano. `main` se integra con **squash**, así
que cuando la base se mergea, sus commits desaparecen y aparece uno nuevo con
el mismo contenido. Git ya no reconoce que es lo mismo: al integrar `main`,
cada cambio de la base vuelve como conflicto, y con una forma que confunde
—**un lado vacío**—:

```
<<<<<<< HEAD
from src.modules.sales.application import clientes as clientes_uc
=======
>>>>>>> origin/main
```

No es que `main` haya borrado esa línea: es que la agregó por otro camino. La
regla para resolver: **quedarse con el lado que tenga el contenido**, y cuando
los dos lo tienen, quedarse con el de `main` y volver a aplicar encima lo
propio de la rama —que se lee con `git diff <base>..HEAD -- <archivo>`—. Los
conteos (tests, casos de e2e) se vuelven a **medir**, no a elegir: los dos
lados están desactualizados.

Cuando se pueda esperar a que la base entre a `main`, esperar sale más barato.

## Cerrar el worktree

Cuando el PR se mergea, el worktree ya no sirve:

```bash
git worktree remove .claude/worktrees/<nombre>
```

Dejarlos vivos es cómo se llega a dieciocho, y con dieciocho nadie sabe cuál
tiene trabajo de verdad. Dos veces —`frontend/lib/carga.ts` y el checkout
principal— hubo trabajo terminado que nunca llegó a `main` porque su rama
nunca tuvo PR.

**De a uno, mirando el resultado.** Un `for` que recorre worktrees borrándolos
tarda minutos por cada `node_modules`, y si se corta a la mitad deja uno sin su
archivo `.git`: el directorio queda, `git -C` empieza a contestar por el
repositorio principal —no falla, **contesta otra cosa**— y parece que se perdió
el trabajo. No se perdió: la rama sigue apuntando a sus commits, y se recupera
con `git worktree add <ruta-nueva> <rama>`. Pasó el 2026-08-15 con la rama de
la caja.

Además, `git worktree remove` se niega si hay algo sin commitear, y eso es una
protección, no un estorbo: **nunca `--force` sin mirar antes qué hay**. El
mismo día, siete worktrees "viejos" resultaron tener trabajo sin commitear
—cuatro ADR y dos migraciones entre ellos— aunque sus ramas no tuvieran nada
que `main` no tuviera.

**Cuándo una rama se puede borrar.** Ni el número de commits ni el diff
alcanzan: con squash, una rama mergeada sigue mostrando commits propios y
`git diff main <rama>` sigue mostrando diferencias. Lo que decide es el PR:

```bash
gh pr list --head claude/<rama> --state all --json number,state,mergedAt
git log -1 --format=%cI claude/<rama>      # ¿hay commits después del merge?
```

Mergeado y sin commits posteriores: se borra. Cualquier otra cosa: se deja y se
pregunta.
