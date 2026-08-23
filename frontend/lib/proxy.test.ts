/**
 * El proxy del navegador (`app/api/proxy/[...ruta]/route.ts`) **no toca lo
 * que pasa por él**, en las dos direcciones (ADR-048).
 *
 * Es el eslabón que nadie probaba: los tests de backend atacan a FastAPI con
 * `TestClient` y el proxy queda fuera del camino, así que un endpoint podía
 * estar perfecto y llegar corrupto al navegador igual. Pasó: la plantilla de
 * recetas se servía como `.xlsx` de verdad y el proxy la decodificaba a
 * texto UTF-8 —un ZIP no sobrevive eso— y la reetiquetaba `application/json`,
 * con lo que el navegador guardaba un `plantilla.json` ilegible. La subida
 * estaba rota por lo mismo del otro lado: un `Content-Type` fijo le borraba
 * el `boundary` al `multipart`.
 *
 * Acá se fija el comportamiento en milisegundos y sin levantar nada. El
 * recorrido de punta a punta —descargar, abrir con openpyxl, subir e
 * importar— vive en `uso/importador-recetas.spec.ts`; este test existe para
 * que una regresión se vea en `npm test` y no dos suites después.
 *
 * Corre con `npm test`.
 */

import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import path from "node:path";
import test from "node:test";
import { pathToFileURL } from "node:url";

const RAIZ = path.join(import.meta.dirname, "..");

/**
 * `cookies()` de Next lee el contexto de una request que acá no existe: sin
 * reemplazo, importar la ruta revienta antes del primer `assert`. El doble
 * va como módulo `data:` —soportado por el ESM de Node— para no dejar un
 * archivo suelto en `lib/` que después parezca código de la app.
 */
const STUB_NEXT_HEADERS =
  "data:text/javascript," +
  encodeURIComponent(
    "export const cookies = async () => ({" +
      "  get: () => (globalThis.tokenDePrueba" +
      "    ? { value: globalThis.tokenDePrueba }" +
      "    : undefined)," +
      "});",
  );

/** Mismo par de agujeros que `contrato.test.ts`: el alias `@/` y los imports
 * sin extensión los resuelve el bundler, y esto corre sin bundler. */
registerHooks({
  resolve(especificador, contexto, siguiente) {
    if (especificador === "next/headers") {
      return { url: STUB_NEXT_HEADERS, shortCircuit: true };
    }
    const destino = especificador.startsWith("@/")
      ? pathToFileURL(path.join(RAIZ, especificador.slice(2))).href
      : especificador;
    const relativo = destino.startsWith("./") || destino.startsWith("file:");
    if (relativo && !/\.tsx?$/.test(destino)) {
      try {
        return siguiente(`${destino}.ts`, contexto);
      } catch {
        // No era un `.ts` del proyecto: sigue la resolución normal.
      }
    }
    return siguiente(destino, contexto);
  },
});

// --- El doble de `fetch` ------------------------------------------------------

type Llamada = { url: string; init: RequestInit };

let ultima: Llamada | null = null;
let responder: () => Response = () => new Response(null, { status: 204 });

globalThis.fetch = (async (url: string | URL, init: RequestInit = {}) => {
  ultima = { url: String(url), init };
  return responder();
}) as typeof fetch;

const global_ = globalThis as unknown as { tokenDePrueba?: string };
global_.tokenDePrueba = "token-de-prueba";

type Ruta = (
  req: Request,
  ctx: { params: Promise<{ ruta: string[] }> },
) => Promise<Response>;

const proxy = (await import(
  pathToFileURL(path.join(RAIZ, "app", "api", "proxy", "[...ruta]", "route.ts")).href
)) as { GET: Ruta; POST: Ruta; DELETE: Ruta };

const RUTA = ["api", "v1", "inventory", "recetas", "plantilla"];

function contexto(ruta = RUTA) {
  return { params: Promise.resolve({ ruta }) };
}

/** Los primeros bytes de cualquier `.xlsx`: la firma de un ZIP, seguida de
 * bytes que **no son UTF-8 válido**. Es lo que hace de este dato una prueba
 * y no una decoración — con texto ASCII, un proxy que decodifica pasa igual. */
const XLSX = new Uint8Array([0x50, 0x4b, 0x03, 0x04, 0xff, 0xfe, 0x00, 0x80, 0xc3]);

const cuerpoDe = async (r: Response) => Buffer.from(await r.arrayBuffer());

// --- La bajada ----------------------------------------------------------------

test("una descarga binaria llega byte por byte", async () => {
  responder = () =>
    new Response(XLSX, {
      headers: {
        "Content-Type":
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": 'attachment; filename="plantilla-recetas.xlsx"',
      },
    });

  const respuesta = await proxy.GET(
    new Request("http://web/api/proxy/api/v1/inventory/recetas/plantilla"),
    contexto(),
  );

  assert.deepEqual(await cuerpoDe(respuesta), Buffer.from(XLSX));
});

test("el tipo y el nombre del archivo son los que mandó la API", async () => {
  responder = () =>
    new Response(XLSX, {
      headers: {
        "Content-Type":
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": 'attachment; filename="plantilla-recetas.xlsx"',
      },
    });

  const respuesta = await proxy.GET(
    new Request("http://web/api/proxy/api/v1/inventory/recetas/plantilla"),
    contexto(),
  );

  assert.equal(
    respuesta.headers.get("content-type"),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  );
  assert.equal(
    respuesta.headers.get("content-disposition"),
    'attachment; filename="plantilla-recetas.xlsx"',
  );
});

test("la query viaja y el token se agrega del lado del servidor", async () => {
  responder = () => new Response("[]", { headers: { "Content-Type": "application/json" } });

  await proxy.GET(
    new Request("http://web/api/proxy/api/v1/inventory/recetas?tipo=subreceta"),
    contexto(["api", "v1", "inventory", "recetas"]),
  );

  assert.match(ultima!.url, /\/api\/v1\/inventory\/recetas\?tipo=subreceta$/);
  const cabeceras = ultima!.init.headers as Record<string, string>;
  assert.equal(cabeceras.Authorization, "Bearer token-de-prueba");
});

// --- La subida ----------------------------------------------------------------

test("un multipart conserva su boundary y su cuerpo", async () => {
  responder = () => new Response("{}", { headers: { "Content-Type": "application/json" } });

  const tipo = "multipart/form-data; boundary=----limite-inventado-1234";
  await proxy.POST(
    new Request("http://web/api/proxy/api/v1/inventory/recetas/importar/validar", {
      method: "POST",
      headers: { "Content-Type": tipo },
      body: XLSX,
    }),
    contexto(["api", "v1", "inventory", "recetas", "importar", "validar"]),
  );

  const cabeceras = ultima!.init.headers as Record<string, string>;
  assert.equal(cabeceras["Content-Type"], tipo);
  assert.deepEqual(Buffer.from(ultima!.init.body as ArrayBuffer), Buffer.from(XLSX));
});

test("un POST de JSON sigue siendo JSON", async () => {
  responder = () =>
    new Response('{"id":"1"}', { status: 201, headers: { "Content-Type": "application/json" } });

  const respuesta = await proxy.POST(
    new Request("http://web/api/proxy/api/v1/inventory/recetas", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nombre: "Salsa" }),
    }),
    contexto(["api", "v1", "inventory", "recetas"]),
  );

  const cabeceras = ultima!.init.headers as Record<string, string>;
  assert.equal(cabeceras["Content-Type"], "application/json");
  assert.equal(Buffer.from(ultima!.init.body as ArrayBuffer).toString(), '{"nombre":"Salsa"}');
  assert.equal(respuesta.status, 201);
  assert.deepEqual(await respuesta.json(), { id: "1" });
});

// --- Lo que ya funcionaba y no puede dejar de funcionar ------------------------

test("el detalle del error vuelve tal cual", async () => {
  responder = () =>
    new Response('{"detail":"el pago excede el saldo de la cuenta"}', {
      status: 409,
      headers: { "Content-Type": "application/json" },
    });

  const respuesta = await proxy.POST(
    new Request("http://web/api/proxy/api/v1/sales/pagos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }),
    contexto(["api", "v1", "sales", "pagos"]),
  );

  assert.equal(respuesta.status, 409);
  assert.deepEqual(await respuesta.json(), {
    detail: "el pago excede el saldo de la cuenta",
  });
});

test("un 204 no arrastra cuerpo", async () => {
  responder = () => new Response(null, { status: 204 });

  const respuesta = await proxy.DELETE(
    new Request("http://web/api/proxy/api/v1/inventory/recetas/1", { method: "DELETE" }),
    contexto(["api", "v1", "inventory", "recetas", "1"]),
  );

  assert.equal(respuesta.status, 204);
  assert.equal(respuesta.body, null);
});

test("sin cookie de sesión no se llama a la API", async () => {
  global_.tokenDePrueba = undefined;
  ultima = null;
  try {
    const respuesta = await proxy.GET(
      new Request("http://web/api/proxy/api/v1/inventory/recetas/plantilla"),
      contexto(),
    );
    assert.equal(respuesta.status, 401);
    assert.equal(ultima, null);
  } finally {
    global_.tokenDePrueba = "token-de-prueba";
  }
});
