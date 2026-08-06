import { defineConfig, devices } from "@playwright/test";

/**
 * e2e del flujo del dinero.
 *
 * Levanta la API y el frontend juntos porque una prueba de pantalla que
 * mockea el backend no habría atrapado nada de lo que esta suite existe
 * para atrapar: los dos bugs que motivaron escribirla —la apertura de caja
 * mandando el contrato pre-ADR-025 y el listado de ventas leído como array
 * tras la paginación— eran desacuerdos **entre** cliente y servidor. Con un
 * mock, los dos lados quedan de acuerdo consigo mismos y el error sigue
 * invisible.
 *
 * La API corre contra un SQLite desechable (`e2e.db`) sembrado por
 * `src.seeders.seed` + `src.seeders.e2e`, no contra la base de desarrollo:
 * una prueba que abre y cierra caja deja rastro, y ese rastro no puede caer
 * en los datos con los que alguien está trabajando.
 */
const PYTHON = process.env.PYTHON ?? "python";
const RAIZ = "..";
// Escape para iterar en local contra servidores ya levantados a mano.
const REUSAR = !!process.env.E2E_REUSAR;

export default defineConfig({
  testDir: "./e2e",
  // Sin paralelo: las pruebas comparten una sola caja por punto de venta, y
  // dos que abran caja a la vez se pisan. Serializar es más honesto que
  // inventar un punto de venta por worker para un suite de este tamaño.
  workers: 1,
  fullyParallel: false,
  // 30 s (el defecto) no alcanzan: `next dev` compila cada ruta la primera
  // vez que alguien la pide, y este recorrido toca login, home, PDV, la ruta
  // de proxy y sus diálogos. El login solo tarda ~5 s en frío. No es lentitud
  // del código sino del modo desarrollo — se compensa con tiempo en vez de
  // montar un build de producción para el suite.
  //
  // 90 s tampoco alcanzaban **en frío**: con `.next` vacío la corrida moría
  // sobre el cierre de caja, y el síntoma —"esperaba Caja cerrada"— hacía
  // pensar en un bug del cierre. Lo que se agotaba era el presupuesto del
  // test, no el `expect`. El recorrido completo tarda ~96 s en esta máquina;
  // el resto del margen es para el runner de CI, que tiene dos núcleos y
  // siempre compila en frío.
  timeout: 240_000,
  expect: { timeout: 15_000 },
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    // `localhost` y no `127.0.0.1`: Next los trata como **orígenes
    // distintos**, y en producción una Server Action cross-origin se
    // rechaza. El síntoma es un `Invalid URL` con `input: 'null'` del lado
    // del servidor y un botón que se queda en "Ingresando..." para siempre
    // — en ningún lado dice "origen". Next arranca en `localhost`, así que
    // el navegador tiene que pedir por `localhost`.
    baseURL: "http://localhost:3100",
    // Solo del intento que falla: el rastro es para depurar, no para
    // engordar el artefacto de cada corrida verde.
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "node e2e/servidor-api.mjs",
      url: "http://127.0.0.1:8100/health",
      // **Nunca reusar**: una API viva de la corrida anterior apunta a la
      // base que `globalSetup` acaba de borrar, y la suite corre contra un
      // esquema vacío dando errores que no tienen nada que ver con el
      // código. Costó media hora descubrirlo la primera vez.
      reuseExistingServer: REUSAR,
      timeout: 120_000,
    },
    {
      // `next dev` y no `build && start`: en producción Next verifica el
      // origen de las Server Actions y rechaza el POST del login con un
      // `Invalid URL` que no menciona la palabra "origen" por ningún lado.
      // Probar el build real vale la pena, pero es otro problema: queda en
      // el ROADMAP.
      command: "node e2e/servidor-web.mjs",
      url: "http://localhost:3100/login",
      // Mismo motivo, más uno propio: un Next reusado conserva el
      // `API_INTERNAL_URL` con el que arrancó y apuntaría a otra API.
      reuseExistingServer: REUSAR,
      timeout: 180_000,
    },
  ],
});
