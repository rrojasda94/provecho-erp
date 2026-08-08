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
