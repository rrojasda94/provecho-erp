/**
 * Único check de la carga del SDK de Maps.
 *
 * Existe por un bug real: `cargarMaps` resolvía en cuanto `window.google.maps`
 * existía, pero ese objeto aparece antes de que el bootstrap de `loading=async`
 * defina `importLibrary`. Quien recibía ese namespace a medio armar moría con
 * «maps.importLibrary is not a function» dentro del `.catch()` de
 * `CampoDireccion`, y el único síntoma era un campo de dirección sin buscador
 * — indistinguible de no tener clave (ADR-072).
 *
 * `promesa` es estado del módulo, así que cada caso lo importa de nuevo con una
 * query distinta para no heredar el del anterior.
 */

import assert from "node:assert/strict";
import test from "node:test";

type Ventana = { google?: { maps?: unknown } };

/** El DOM mínimo que `cargarMaps` toca: buscar, crear y colgar un `<script>`. */
function montarDom(): void {
  const escuchas = new Map<string, () => void>();
  const script = {
    id: "",
    src: "",
    async: false,
    addEventListener: (evento: string, fn: () => void) => escuchas.set(evento, fn),
  };
  Object.assign(globalThis, {
    window: {} as Ventana,
    document: {
      getElementById: () => null,
      createElement: () => script,
      head: { appendChild: () => undefined },
    },
  });
}

/** Deja el SDK como lo ve el navegador cuando terminó de cargar de verdad. */
function sdkCompleto(): void {
  (globalThis as unknown as { window: Ventana }).window.google = {
    maps: { importLibrary: async () => ({}) },
  };
}

/** Y como se ve a medio cargar: el namespace ya está, `importLibrary` no. */
function sdkAMedias(): void {
  (globalThis as unknown as { window: Ventana }).window.google = { maps: {} };
}

async function importar(caso: string) {
  return (await import(`./google-maps.ts?caso=${caso}`)) as {
    cargarMaps: (clave: string) => Promise<unknown>;
  };
}

test("sin clave rechaza y no toca el DOM", async () => {
  montarDom();
  const { cargarMaps } = await importar("sin-clave");
  await assert.rejects(cargarMaps(""), /sin clave/);
});

test("no resuelve con el namespace a medio armar", async () => {
  montarDom();
  sdkAMedias();
  const { cargarMaps } = await importar("a-medias");

  const carrera = await Promise.race([
    cargarMaps("AIzaFalsa").then(() => "resolvio"),
    new Promise((r) => setTimeout(() => r("sigue esperando"), 200)),
  ]);

  // Lo que fallaba: resolvía acá y el llamador recibía un objeto sin
  // `importLibrary`. Esperar es la respuesta correcta — el SDK sigue cargando.
  assert.equal(carrera, "sigue esperando");
});

test("resuelve en cuanto aparece importLibrary", async () => {
  montarDom();
  sdkAMedias();
  const { cargarMaps } = await importar("aparece-tarde");

  const promesa = cargarMaps("AIzaFalsa");
  setTimeout(sdkCompleto, 80);

  const maps = (await promesa) as { importLibrary: unknown };
  assert.equal(typeof maps.importLibrary, "function");
});

test("el SDK ya cargado se devuelve sin esperar", async () => {
  montarDom();
  sdkCompleto();
  const { cargarMaps } = await importar("ya-cargado");

  // Sin sondeo de por medio: un segundo campo de dirección en la misma
  // pantalla no puede tardar 50 ms en encenderse.
  const maps = (await Promise.race([
    cargarMaps("AIzaFalsa"),
    new Promise((_, rechazar) => setTimeout(() => rechazar(new Error("tardó")), 20)),
  ])) as { importLibrary: unknown };
  assert.equal(typeof maps.importLibrary, "function");
});
