import type { PlaywrightTestConfig } from "@playwright/test";

/**
 * Lo que comparten las dos suites de Playwright: **cómo se levanta el
 * sistema**. Qué se prueba con él es lo que las distingue (ADR-047).
 *
 * - `playwright.config.ts` → `e2e/`: el techo de tres casos de
 *   `docs/engineering/testing-strategy.md`. Rápida, obligatoria en CI.
 * - `playwright.uso.config.ts` → `uso/`: recorridos completos con captura en
 *   cada hito. Lenta, y **no bloquea un merge**.
 *
 * Este archivo existe para que ese arranque —dos servidores, sus puertos,
 * sus tiempos y las tres razones por las que no se reusan— se corrija en un
 * solo lugar. Copiarlo garantizaba que una de las dos copias envejeciera, y
 * la que envejece es siempre la que se corre menos.
 */

// Puertos parametrizables porque el repo se trabaja con **varias sesiones de
// agente en paralelo**, cada una en su worktree. Con los dos puertos fijos en
// el código, la segunda suite que arranca choca contra la primera: la API se
// cae con `EADDRINUSE` o —peor— Next reusa el servidor del otro worktree y
// las pruebas corren contra código que no es el suyo.
// El esquema de slots (`810N` / `310N`) está en
// `docs/engineering/trabajo-en-paralelo.md`.
export const PUERTO_API = process.env.E2E_PUERTO_API ?? "8100";
export const PUERTO_WEB = process.env.E2E_PUERTO_WEB ?? "3100";

// `localhost` y no `127.0.0.1`: Next los trata como **orígenes distintos**, y
// en producción una Server Action cross-origin se rechaza. El síntoma es un
// `Invalid URL` con `input: 'null'` del lado del servidor y un botón que se
// queda en "Ingresando..." para siempre — en ningún lado dice "origen". Next
// arranca en `localhost`, así que el navegador tiene que pedir por
// `localhost`.
export const BASE_URL = `http://localhost:${PUERTO_WEB}`;

// Escape para iterar en local contra servidores ya levantados a mano.
const REUSAR = !!process.env.E2E_REUSAR;

/**
 * La API contra un SQLite desechable y el frontend en modo desarrollo.
 *
 * Se levantan los dos de verdad porque una prueba de pantalla que mockea el
 * backend no habría atrapado nada de lo que estas suites existen para
 * atrapar: los dos bugs que motivaron escribirlas —la apertura de caja
 * mandando el contrato pre-ADR-025 y el listado de ventas leído como array
 * tras la paginación— eran desacuerdos **entre** cliente y servidor. Con un
 * mock, los dos lados quedan de acuerdo consigo mismos y el error sigue
 * invisible.
 */
export const servidores: PlaywrightTestConfig["webServer"] = [
  {
    command: "node e2e/servidor-api.mjs",
    url: `http://127.0.0.1:${PUERTO_API}/health`,
    // **Nunca reusar**: una API viva de la corrida anterior apunta a la base
    // que el paso de preparación acaba de borrar, y la suite corre contra un
    // esquema vacío dando errores que no tienen nada que ver con el código.
    // Costó media hora descubrirlo la primera vez.
    reuseExistingServer: REUSAR,
    timeout: 120_000,
  },
  {
    // `next dev` y no `build && start`: en producción Next verifica el origen
    // de las Server Actions y rechaza el POST del login con un `Invalid URL`
    // que no menciona la palabra "origen" por ningún lado. Probar el build
    // real vale la pena, pero es otro problema: queda en el ROADMAP.
    command: "node e2e/servidor-web.mjs",
    url: `${BASE_URL}/login`,
    // Mismo motivo, más uno propio: un Next reusado conserva el
    // `API_INTERNAL_URL` con el que arrancó y apuntaría a otra API.
    reuseExistingServer: REUSAR,
    timeout: 180_000,
  },
];
