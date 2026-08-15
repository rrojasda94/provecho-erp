# ADR-047 — Dos suites de Playwright: `e2e` con techo, `uso` sin él

- **Estado:** aceptada
- **Fecha:** 2026-08-15
- **Contexto:** pruebas, CI, trabajo en paralelo
- **Relacionado:** `docs/engineering/testing-strategy.md`,
  `docs/engineering/trabajo-en-paralelo.md`, ADR-008 (entrega continua)

## Contexto

`docs/engineering/testing-strategy.md` fijó un techo explícito: los e2e
cubren **tres cosas** —que la sesión funcione, un flujo del dinero completo,
y los candados que solo existen en pantalla— y "lo que no entra acá no se
escribe como e2e". El techo no era arbitrario. Un e2e cuesta minutos, corre
con un solo worker, y es **check requerido**: cada caso que se agrega es
tiempo que paga todo merge del repo, incluido el arreglo urgente de caja que
no toca ninguna pantalla.

Al mismo tiempo apareció una necesidad que el techo bloquea. Nadie puede
mirar el ERP sin instalarlo: para revisar si una pantalla se puede usar de
verdad —si el recorrido de vender una pizza con variantes y extras tiene
sentido, si los mensajes de error dicen algo— hay que levantar la API, el
frontend, sembrar la base y hacer los clics a mano. Eso lo hace una persona
por vez, se pierde apenas cierra la terminal, y no queda evidencia de cómo
se veía la pantalla el martes.

Un recorrido con capturas resuelve eso. Pero escribirlo dentro de `e2e/`
rompe el techo, y romper el techo tiene consecuencias concretas: la suite
pasa de 4 minutos a 15, y una etiqueta que cambió en el rediseño deja `main`
en rojo sin que nada esté roto. Eso ya pasó (2026-08-06: el rediseño cambió
un subtítulo y se cayeron siete pruebas).

## Decisión

**Dos suites, con propósitos distintos y consecuencias distintas.**

| | `frontend/e2e/` | `frontend/uso/` |
|---|---|---|
| Pregunta | ¿arranca y se hablan? | ¿esto se puede usar? |
| Techo | **Sí**: las tres cosas de la estrategia | No |
| Entregable | el verde | las **capturas** |
| `screenshot` / `trace` | `on-failure` | `on` |
| Reintentos en CI | 1 | 0 |
| Check requerido | **sí** | **no** (`continue-on-error`) |
| Artefacto en CI | `if: failure()` | `if: always()` |

**El techo de tres casos sigue vigente para `e2e` y no se toca.** Lo que
cambia es que ahora hay adónde mandar lo que no entra: antes la única salida
era agregarlo igual o no escribirlo.

**`uso` no puede bloquear un merge.** Es la propiedad que hace que las dos
suites puedan convivir. Un recorrido largo se cae por cosas que no son bugs
—una etiqueta nueva, un runner con dos núcleos que compila en frío— y un
check requerido que falla por ruido se vuelve un check que la gente aprende a
ignorar. Queda fuera de los seis jobs del ruleset y además con
`continue-on-error: true`.

**El arranque es el mismo y vive en un solo lugar** (`playwright.comun.ts`):
los dos servidores, sus puertos, sus tiempos y las tres razones por las que
nunca se reusan. Copiar esa configuración garantizaba que una de las dos
copias envejeciera, y la que envejece es siempre la que se corre menos.

**Los datos los sigue sembrando `src/seeders/e2e.py`**, no el test — la regla
no cambia por cambiar de suite. Por eso el seeder se amplió en el mismo
cambio: carta con variantes, grupo obligatorio y extras; stock real;
proveedor y orden de compra.

## Alternativas descartadas

**Subir el techo de `e2e` y meter todo ahí.** Es lo que el techo existe para
evitar. La suite crece hasta que su duración obliga a que alguien la
"arregle" borrando casos, y los que se borran son los del flujo del dinero
—los largos— no los baratos.

**Etiquetar (`@lento`) dentro de la misma suite y filtrar por tag.** Más
barato de montar, pero deja las dos en la misma config: o las capturas se
guardan siempre —y el artefacto de cada corrida verde engorda por casos que
no las necesitan— o no se guardan nunca, que es lo mismo que no tener la
suite. La diferencia entre las dos no es qué casos corren, es `screenshot`,
`trace`, `retries` y si bloquea el merge. Eso es una configuración distinta,
no un filtro.

**Un repositorio o herramienta aparte para los recorridos.** Duplica el
arranque de servidores y el seeder, que es exactamente lo que ya cuesta
mantener. Y una suite que no está en el repo no se corre en CI.

## Consecuencias

- `npm run test:uso` en `frontend/package.json`, con la misma preparación de
  base que `test:e2e` (misma `e2e.db` desechable, mismo seeder).
- Job `uso` en `.github/workflows/ci.yml`, **fuera de los seis requeridos**.
  Sube `frontend/test-results/` siempre.
- `outputDir` separado por suite (`test-results/e2e`, `test-results/uso`).
  Playwright **borra el `outputDir` entero** antes de correr: compartirlo
  hacía que la última suite en correr fuera la única con capturas.
- Las capturas **nunca se versionan**: `test-results/` y `playwright-report/`
  ya están en `.gitignore`.
- Esta rama deja **una sola spec de humo** (`uso/humo.spec.ts`). No prueba
  nada que `e2e/sesion.spec.ts` no pruebe mejor: prueba el arnés. Los
  recorridos reales los escriben las ramas que los necesiten.
- Riesgo aceptado: una suite que no bloquea es una suite que se puede
  pudrir sin que nadie se entere. La mitigación es que su salida sea un
  artefacto que se mira, no un verde que se ignora — pero si nadie lo mira,
  se pudre igual. Si eso pasa, la respuesta es borrarla, no volverla
  obligatoria.
