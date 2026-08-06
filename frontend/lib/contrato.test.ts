/**
 * Contrato cliente↔servidor: que lo que el PDV **manda** valide contra el
 * `requestBody` de `docs/architecture/openapi.json`, y que lo que el
 * contrato **devuelve** lo pueda leer el cliente sin romperse.
 *
 * Es el test que faltaba, y el más barato de los que existen: corre en
 * milisegundos, no levanta servidores y no es flaky. Los dos bugs que
 * costaron un día de caja rota eran desacuerdos de contrato, no de
 * comportamiento:
 *
 * - La apertura mandaba `monto_apertura` cuando el servidor ya esperaba
 *   `monto_declarado` (ADR-025) → 422. Lo caza `validar()` como "el
 *   contrato lo exige y no viaja" + "el contrato no conoce este campo".
 * - `GET /ventas` pasó a devolver `{items, total, …}` (ADR-026) y el
 *   cliente lo leía como array → pantalla en blanco. Lo caza alimentar al
 *   cliente con una respuesta **generada desde el contrato** y exigirle que
 *   la lea bien.
 *
 * No reemplaza a `tsc`: los tipos de `lib/pdv.ts` ya obligan a cada
 * pantalla a armar el cuerpo correcto. Esto verifica el eslabón que falta
 * — que esos tipos y el contrato sigan diciendo lo mismo.
 *
 * Corre con `npm test`. El `registerHooks` está porque el resto del código
 * importa sin extensión (convención del proyecto, resuelta por Next/tsc) y
 * Node ESM resuelve por ruta real.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { registerHooks } from "node:module";
import path from "node:path";
import test from "node:test";

registerHooks({
  resolve(especificador, contexto, siguiente) {
    if (especificador.startsWith("./") && !especificador.endsWith(".ts")) {
      try {
        return siguiente(`${especificador}.ts`, contexto);
      } catch {
        // No era un `.ts` del proyecto: sigue la resolución normal.
      }
    }
    return siguiente(especificador, contexto);
  },
});

const { api } = await import("./pdv.ts");

// --- El contrato ------------------------------------------------------------

/** Solo los campos de OpenAPI que este test mira. Declararlos evita el
 * `any` y deja escrito hasta dónde llega la validación de abajo. */
type Esquema = {
  $ref?: string;
  type?: string;
  format?: string;
  properties?: Record<string, Esquema>;
  required?: string[];
  items?: Esquema;
  anyOf?: Esquema[];
  additionalProperties?: boolean | Esquema;
};

type ConCuerpo = { content?: Record<string, { schema?: Esquema }> };
type Operacion = { requestBody?: ConCuerpo; responses?: Record<string, ConCuerpo> };
type Contrato = {
  paths: Record<string, Record<string, Operacion>>;
  components: { schemas: Record<string, Esquema> };
};

const contrato: Contrato = JSON.parse(
  readFileSync(
    path.join(import.meta.dirname, "..", "..", "docs", "architecture", "openapi.json"),
    "utf-8",
  ),
);

function resolver(esquema: Esquema | undefined): Esquema | undefined {
  if (!esquema?.$ref) return esquema;
  return resolver(contrato.components.schemas[esquema.$ref.split("/").pop()!]);
}

/** De `/api/proxy/api/v1/sales/ventas/<uuid>/pagos?x=1` a la plantilla
 * `/api/v1/sales/ventas/{venta_id}/pagos`. Un endpoint renombrado o movido
 * no encuentra plantilla y el test lo dice por su nombre. */
function plantillaDe(url: string): string | null {
  const partes = url.replace("/api/proxy", "").split("?")[0].split("/");
  const encaja = (plantilla: string) => {
    const esperadas = plantilla.split("/");
    return (
      esperadas.length === partes.length &&
      esperadas.every((seg, i) => seg.startsWith("{") || seg === partes[i])
    );
  };
  return Object.keys(contrato.paths).find(encaja) ?? null;
}

function operacionDe(url: string, metodo: string): Operacion | undefined {
  const plantilla = plantillaDe(url);
  return plantilla ? contrato.paths[plantilla][metodo.toLowerCase()] : undefined;
}

const esquemaJson = (donde: ConCuerpo | undefined): Esquema | undefined =>
  donde?.content?.["application/json"]?.schema;

// --- Validación -------------------------------------------------------------

/**
 * Valida un valor contra un schema.
 *
 * Cubre a propósito solo lo que se rompe en silencio: campo requerido que
 * no viaja, campo que el contrato no conoce (un rename mal aplicado), y
 * tipo equivocado. **No** valida `pattern`, `minLength`, `minimum` ni
 * enums — eso lo rechaza el servidor con un 422 que se ve, y replicarlo
 * acá sería mantener dos validadores desincronizándose. Si algún día hace
 * falta, la respuesta es una librería de JSON Schema, no hacer crecer esto.
 */
function validar(crudo: Esquema | undefined, valor: unknown, ruta = "cuerpo"): string[] {
  const esquema = resolver(crudo);
  if (!esquema || Object.keys(esquema).length === 0) return [];
  if (esquema.anyOf) {
    const encaja = esquema.anyOf.some((rama) => validar(rama, valor, ruta).length === 0);
    return encaja ? [] : [`${ruta}: no encaja en ninguna variante del contrato`];
  }
  if (esquema.type === "null") return valor === null ? [] : [`${ruta}: se esperaba null`];
  if (valor === null || valor === undefined) return [`${ruta}: falta`];
  return validarSegunTipo(esquema, valor, ruta);
}

function validarSegunTipo(esquema: Esquema, valor: unknown, ruta: string): string[] {
  if (esquema.type === "object") return validarObjeto(esquema, valor, ruta);
  if (esquema.type === "array") return validarArray(esquema, valor, ruta);
  return validarPrimitivo(esquema.type, valor, ruta);
}

function validarArray(esquema: Esquema, valor: unknown, ruta: string): string[] {
  if (!Array.isArray(valor)) return [`${ruta}: se esperaba un array`];
  return valor.flatMap((v, i) => validar(esquema.items, v, `${ruta}[${i}]`));
}

function validarObjeto(esquema: Esquema, valor: unknown, ruta: string): string[] {
  if (typeof valor !== "object" || Array.isArray(valor)) {
    return [`${ruta}: se esperaba un objeto`];
  }
  const campos = valor as Record<string, unknown>;
  const props = esquema.properties ?? {};
  const problemas = (esquema.required ?? [])
    .filter((requerido) => campos[requerido] === undefined)
    .map((requerido) => `${ruta}.${requerido}: el contrato lo exige y no viaja`);

  for (const [clave, sub] of Object.entries(campos)) {
    const libre = esquema.additionalProperties;
    if (props[clave]) {
      problemas.push(...validar(props[clave], sub, `${ruta}.${clave}`));
    } else if (libre) {
      problemas.push(...validar(libre === true ? {} : libre, sub, `${ruta}.${clave}`));
    } else {
      problemas.push(`${ruta}.${clave}: el contrato no conoce este campo`);
    }
  }
  return problemas;
}

const TIPOS: Record<string, string> = {
  string: "string",
  integer: "number",
  number: "number",
  boolean: "boolean",
};

function validarPrimitivo(tipo: string | undefined, valor: unknown, ruta: string): string[] {
  const esperado = tipo ? TIPOS[tipo] : undefined;
  if (!esperado) return [];
  return typeof valor === esperado ? [] : [`${ruta}: se esperaba ${tipo}`];
}

// --- Respuesta de ejemplo ---------------------------------------------------

/** Respuesta armada **desde el contrato**, no a mano: si el servidor cambia
 * la forma, el ejemplo cambia con él y el cliente que ya no la sabe leer se
 * cae acá. Genera todas las propiedades, no solo las requeridas — lo que el
 * cliente transforma suele ser opcional. */
function ejemploDe(crudo: Esquema | undefined): unknown {
  const esquema = resolver(crudo);
  if (!esquema || Object.keys(esquema).length === 0) return {};
  if (esquema.anyOf) {
    const concreta = esquema.anyOf.find((r) => resolver(r)?.type !== "null");
    return ejemploDe(concreta ?? esquema.anyOf[0]);
  }
  if (esquema.type === "object") {
    return Object.fromEntries(
      Object.entries(esquema.properties ?? {}).map(([k, v]) => [k, ejemploDe(v)]),
    );
  }
  if (esquema.type === "array") return [ejemploDe(esquema.items)];
  return ejemploPrimitivo(esquema);
}

function ejemploPrimitivo(esquema: Esquema): unknown {
  if (esquema.type === "integer" || esquema.type === "number") return 1;
  if (esquema.type === "boolean") return true;
  if (esquema.type === "null") return null;
  if (esquema.format === "uuid") return UUID;
  if (esquema.format === "date-time") return "2026-08-06T12:00:00Z";
  return "x";
}

// --- Las operaciones del PDV ------------------------------------------------

const UUID = "11111111-1111-1111-1111-111111111111";

type Caso = { nombre: string; llamar: () => Promise<unknown>; revisar?: (r: never) => void };

/** Ata `revisar` al tipo que devuelve `llamar` sin perderlo en la lista
 * heterogénea de abajo: cada caso queda tipado en su propio sitio. */
function caso<T>(nombre: string, llamar: () => Promise<T>, revisar?: (r: T) => void): Caso {
  return { nombre, llamar, revisar: revisar as ((r: never) => void) | undefined };
}

/**
 * Toda operación de `lib/pdv.ts`. La lista se compara contra el objeto
 * `api`: una operación nueva sin entrada acá hace fallar el test en vez de
 * quedar sin cubrir en silencio.
 *
 * `revisar` es la afirmación extra para las dos que **transforman** la
 * respuesta en vez de devolverla tal cual. Ahí es donde se coló ADR-026.
 */
const OPERACIONES: Caso[] = [
  caso("carta", () => api.carta(UUID, "mesa")),
  caso("mapaMesas", () => api.mapaMesas(UUID)),
  caso("buscarClientes", () => api.buscarClientes("ana")),
  caso("crearCliente", () => api.crearCliente({ nombre: "Ana" })),
  caso("mediosPago", () => api.mediosPago()),
  caso(
    "ventasDelDia",
    () => api.ventasDelDia(UUID, "pagada"),
    // El bug de ADR-026 exacto: el endpoint devuelve `{items, total, …}` y
    // el cliente tiene que desenvolverlo. Si vuelve a leerlo como array,
    // falla acá y no como una pantalla en blanco.
    (ventas) => {
      assert.ok(Array.isArray(ventas), "ventasDelDia debe devolver un array");
      assert.ok(ventas[0]?.id, "la venta desenvuelta perdió sus campos");
    },
  ),
  caso("crearVenta", () =>
    api.crearVenta({
      sucursal_id: UUID,
      punto_venta_id: UUID,
      canal: "pdv",
      modalidad: "takeout",
      idempotency_key: "venta-abcdefgh",
      items: [{ producto_comercial_id: UUID, cantidad: "1", grupo_cobro: 1, extras: [] }],
    }),
  ),
  caso("itemsDeVenta", () => api.itemsDeVenta(UUID)),
  caso("anularLineas", () =>
    api.anularLineas(UUID, {
      venta_item_ids: [UUID],
      motivo: "error de tecleo",
      autorizacion: "t",
    }),
  ),
  caso("anularVenta", () => api.anularVenta(UUID)),
  caso("registrarPago", () =>
    api.registrarPago(UUID, {
      medio_pago_id: UUID,
      monto: "25.00",
      idempotency_key: "pago-abcdefgh",
    }),
  ),
  caso("precuenta", () => api.precuenta(UUID)),
  caso("comprobante", () => api.comprobante(UUID)),
  caso("cajasAbiertas", () => api.cajasAbiertas(UUID)),
  caso("posDeSucursal", () => api.posDeSucursal(UUID)),
  caso(
    "abrirCaja",
    () =>
      api.abrirCaja({
        punto_venta_id: UUID,
        monto_declarado: "200.00",
        detalle_denominaciones: { "100": 2 },
        autorizacion: "t",
        pos_verificados: [{ pos_tarjeta_id: UUID, operativo: true }],
      }),
    // `POST /cajas/apertura` devuelve `id` y el PDV lo renombra a
    // `apertura_caja_id` para el resto del turno. Si el contrato deja de
    // traerlo, cerrar la caja fallaría mucho después y sin pista.
    (caja) => {
      assert.ok(caja.apertura_caja_id, "la apertura no trajo el id del turno");
      assert.ok(caja.abierta_desde, "la apertura no trajo desde cuándo está abierta");
    },
  ),
  caso("cerrarCaja", () =>
    api.cerrarCaja(UUID, {
      detalle_denominaciones: { "100": 2 },
      custodia: "local_caja_fuerte",
      autorizacion: "t",
      descuadre_atribucion: null,
      reportes_pos: [{ pos_tarjeta_id: UUID, monto_lote: "0" }],
    }),
  ),
  caso("registrarMovimientoCaja", () =>
    api.registrarMovimientoCaja(UUID, {
      tipo: "ingreso",
      monto: "5.00",
      motivo: "Propina orden #1",
      idempotency_key: "propina-abcdefgh",
    }),
  ),
  caso("autorizar", () => api.autorizar("encargado", "654321", "accounting.caja_relevar")),
];

// --- El arnés ---------------------------------------------------------------

type Salida = { metodo: string; url: string; cuerpo: unknown };

/** Corre la operación con `fetch` intervenido: captura lo que sale y
 * responde con el ejemplo que el contrato promete para esa ruta. */
async function ejercitar(operacion: Caso): Promise<{ salida: Salida; resultado: unknown }> {
  let salida: Salida | null = null;
  const original = globalThis.fetch;

  globalThis.fetch = ((url: string, opciones: RequestInit = {}) => {
    const metodo = opciones.method ?? "GET";
    salida = { metodo, url, cuerpo: opciones.body ? JSON.parse(String(opciones.body)) : undefined };
    const cuerpo = ejemploDe(esquemaJson(respuestaExitosa(operacionDe(url, metodo))));
    return Promise.resolve(
      new Response(JSON.stringify(cuerpo), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
  }) as typeof fetch;

  try {
    const resultado = await operacion.llamar();
    return { salida: salida!, resultado };
  } finally {
    globalThis.fetch = original;
  }
}

const respuestaExitosa = (op: Operacion | undefined): ConCuerpo | undefined =>
  op?.responses?.["200"] ?? op?.responses?.["201"];

test("toda operación de `api` está cubierta por este test", () => {
  const cubiertas = new Set(OPERACIONES.map((o) => o.nombre));
  const faltantes = Object.keys(api).filter((nombre) => !cubiertas.has(nombre));
  assert.deepEqual(faltantes, [], "operaciones de lib/pdv.ts sin caso de contrato");
});

for (const operacion of OPERACIONES) {
  test(`${operacion.nombre}: la ruta existe en el contrato`, async () => {
    const { salida } = await ejercitar(operacion);
    assert.ok(
      operacionDe(salida.url, salida.metodo),
      `${salida.metodo} ${salida.url} no existe en openapi.json`,
    );
  });

  test(`${operacion.nombre}: el cuerpo valida contra el contrato`, async () => {
    const { salida } = await ejercitar(operacion);
    const esquema = esquemaJson(operacionDe(salida.url, salida.metodo)?.requestBody);
    if (!esquema) {
      assert.equal(salida.cuerpo, undefined, "manda cuerpo a un endpoint que no lo pide");
      return;
    }
    assert.deepEqual(validar(esquema, salida.cuerpo), []);
  });

  test(`${operacion.nombre}: el cliente lee la respuesta del contrato`, async () => {
    const { resultado } = await ejercitar(operacion);
    assert.notEqual(resultado, undefined, "el cliente no devolvió nada");
    operacion.revisar?.(resultado as never);
  });
}
