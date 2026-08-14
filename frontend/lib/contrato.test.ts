/**
 * Contrato cliente↔servidor: que lo que el frontend **manda** valide contra
 * el `requestBody` de `docs/architecture/openapi.json`, y que lo que el
 * contrato **devuelve** lo pueda leer el cliente sin romperse.
 *
 * Es el más barato de los tests que existen: corre en milisegundos, no
 * levanta servidores y no es flaky. Los dos bugs que costaron un día de
 * caja rota eran desacuerdos de contrato, no de comportamiento:
 *
 * - La apertura mandaba `monto_apertura` cuando el servidor ya esperaba
 *   `monto_declarado` (ADR-025) → 422. Lo caza `validar()` como "el
 *   contrato lo exige y no viaja" + "el contrato no conoce este campo".
 * - `GET /ventas` pasó a devolver `{items, total, …}` (ADR-026) y el
 *   cliente lo leía como array → pantalla en blanco. Lo caza alimentar al
 *   cliente con una respuesta **generada desde el contrato** y exigirle que
 *   la lea bien.
 *
 * Cubre en **dos profundidades**, y conviene tener clara la diferencia:
 *
 * 1. **Los cuatro módulos importables** (`pdv`, `catalogo`, `kds`,
 *    `reportes`) exponen la API como un objeto llamable, así que se
 *    ejercitan de verdad: ruta, método, cuerpo y lectura de la respuesta.
 * 2. **Todo el resto del frontend** —Compras, Inventario, RRHH, Gerencia,
 *    Contabilidad, Marketing, Usuarios— llama desde Server Components y
 *    Server Actions, que no se pueden importar acá. Para esos hay un
 *    escaneo del código fuente al final del archivo: toda ruta que el
 *    frontend nombra tiene que existir en el contrato con ese método. Es
 *    menos, pero es sobre las ~170 llamadas.
 *
 * No reemplaza a `tsc`: los tipos de `lib/pdv.ts` ya obligan a cada
 * pantalla a armar el cuerpo correcto. Esto verifica el eslabón que falta
 * — que esos tipos y el contrato sigan diciendo lo mismo.
 *
 * Corre con `npm test`.
 */

import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { registerHooks } from "node:module";
import path from "node:path";
import test from "node:test";
import { pathToFileURL } from "node:url";

const RAIZ = path.join(import.meta.dirname, "..");

/**
 * Dos cosas que el código de la app da por hechas y Node no: el alias `@/`
 * de `tsconfig.paths` y los imports sin extensión. Las dos las resuelve el
 * bundler, y este test corre sin bundler.
 */
registerHooks({
  resolve(especificador, contexto, siguiente) {
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

const { api } = await import("./pdv.ts");
const { catalogoApi } = await import("./catalogo.ts");
const { apiKds } = await import("./kds.ts");
const reportes = await import("./reportes.ts");

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

// --- Las operaciones -------------------------------------------------------

const UUID = "11111111-1111-1111-1111-111111111111";

type Caso = { nombre: string; llamar: () => Promise<unknown>; revisar?: (r: never) => void };

/** Ata `revisar` al tipo que devuelve `llamar` sin perderlo en la lista
 * heterogénea de abajo: cada caso queda tipado en su propio sitio. */
function caso<T>(nombre: string, llamar: () => Promise<T>, revisar?: (r: T) => void): Caso {
  return { nombre, llamar, revisar: revisar as ((r: never) => void) | undefined };
}

/**
 * Los cuatro módulos del frontend que exponen la API como un objeto
 * llamable, y por eso se pueden ejercitar de verdad. Cada lista se compara
 * contra su `superficie`: una operación nueva sin caso hace fallar el test
 * en vez de quedar sin cubrir en silencio.
 *
 * Todo lo demás —Compras, Inventario, RRHH, Gerencia…— llama a la API desde
 * Server Components y Server Actions, que no se pueden importar acá (piden
 * `next/headers`, cookies, un request). Esos quedan cubiertos por el escaneo
 * de rutas del final del archivo, que es menos pero es sobre **todo** el
 * frontend.
 */
const PDV: Caso[] = [
  caso("carta", () => api.carta(UUID, "mesa")),
  caso("quitables", () => api.quitables(UUID)),
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
      items: [
        {
          producto_comercial_id: UUID,
          cantidad: "1",
          grupo_cobro: 1,
          extras: [],
          // Restas de la línea (RN-PRD-004): viajan como ids de artículo.
          sin_articulo_ids: [UUID],
        },
      ],
    }),
  ),
  caso("verificarPin", () => api.verificarPin("123456")),
  caso("itemsDeVenta", () => api.itemsDeVenta(UUID)),
  caso("agregarLineas", () =>
    api.agregarLineas(UUID, [
      { producto_comercial_id: UUID, cantidad: "1", grupo_cobro: 1 },
    ]),
  ),
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

const CATALOGO: Caso[] = [
  caso("unidadesMedida", () => catalogoApi.unidadesMedida()),
  caso("crearArticulo", () =>
    catalogoApi.crearArticulo({
      id_interno: "ALB1",
      nombre: "Albahaca",
      unidad_medida_id: UUID,
      tipo: "insumo",
    }),
  ),
  caso("validarImportacion", () =>
    catalogoApi.validarImportacion(
      new File([new Uint8Array([0x50, 0x4b])], "recetas.xlsx"),
    ),
  ),
  caso("importarRecetas", () =>
    catalogoApi.importarRecetas([
      {
        fila: 2,
        nombre: "Salsa Base",
        rendimiento: "1",
        unidad: "Unidad",
        unidad_medida_id: UUID,
        produce: null,
        articulo_producido_id: null,
        ingredientes: [],
        problemas: [],
      },
    ]),
  ),
  caso(
    "articulos",
    () => catalogoApi.articulos(),
    // Mismo desenvuelto que `ventasDelDia`: `/inventory/articulos` es
    // paginado (ADR-026) y el editor de recetas quiere la lista.
    (articulos) => assert.ok(Array.isArray(articulos), "articulos debe devolver un array"),
  ),
  caso("marcas", () => catalogoApi.marcas()),
  caso("productos", () => catalogoApi.productos()),
  caso("producto", () => catalogoApi.producto(UUID)),
  caso("crearProducto", () =>
    catalogoApi.crearProducto({ id_interno: "P-001", marca_id: UUID, nombre: "Pizza" }),
  ),
  caso("editarProducto", () => catalogoApi.editarProducto(UUID, { nombre: "Pizza grande" })),
  caso("eliminarProducto", () => catalogoApi.eliminarProducto(UUID)),
  caso("crearGrupo", () =>
    catalogoApi.crearGrupo(UUID, { nombre: "Tamaño", minimo: 1, maximo: 1, orden: 1 }),
  ),
  caso("borrarGrupo", () => catalogoApi.borrarGrupo(UUID, UUID)),
  caso("vincularExtra", () => catalogoApi.vincularExtra(UUID, { extra_id: UUID, maximo: 2 })),
  caso("desvincularExtra", () => catalogoApi.desvincularExtra(UUID, UUID)),
  caso("recetas", () => catalogoApi.recetas()),
  caso("receta", () => catalogoApi.receta(UUID)),
  caso("crearReceta", () =>
    catalogoApi.crearReceta({
      nombre: "Masa",
      rendimiento_cantidad: "1",
      rendimiento_unidad_medida_id: UUID,
    }),
  ),
  caso("editarReceta", () => catalogoApi.editarReceta(UUID, { nombre: "Masa fina" })),
  caso("eliminarReceta", () => catalogoApi.eliminarReceta(UUID)),
  caso("duplicarReceta", () => catalogoApi.duplicarReceta(UUID)),
  caso("escalarReceta", () => catalogoApi.escalarReceta(UUID, "2")),
  caso("agregarItem", () =>
    catalogoApi.agregarItem(UUID, { articulo_id: UUID, cantidad: "0.25", expresion: "1000/4" }),
  ),
  caso("editarItem", () => catalogoApi.editarItem(UUID, UUID, { cantidad: "0.30" })),
  caso("eliminarItem", () => catalogoApi.eliminarItem(UUID, UUID)),
];

const KDS: Caso[] = [
  caso("cola", () => apiKds.cola(UUID)),
  caso("pantallas", () => apiKds.pantallas(UUID)),
  caso("crearPantalla", () =>
    apiKds.crearPantalla(UUID, {
      nombre: "Cocina",
      tipo: "preparacion",
      categoria_ids: [UUID],
      orden: 0,
    }),
  ),
  caso("editarPantalla", () => apiKds.editarPantalla(UUID, { nombre: "Cocina 2", activo: true })),
  caso("categorias", () => apiKds.categorias()),
  caso("avanzar", () => apiKds.avanzar(UUID, "en_preparacion")),
  caso("entregar", () => apiKds.entregar(UUID)),
];

/** `lib/reportes.ts` exporta funciones sueltas, no un objeto `api`, así que
 * la lista de abajo es la fuente y no hay chequeo automático de cobertura.
 * `guardarTablero` da dos casos: con `id` es PATCH sobre `/tableros/{id}` y
 * sin él, POST sobre `/tableros`. Son dos rutas distintas detrás de una
 * misma función, que es justo el tipo de cosa que un contrato tiene que
 * mirar por separado. */
const REPORTES: Caso[] = [
  caso("datosDeReporte", () =>
    reportes.datosDeReporte("ventas_por_dia", reportes.FILTROS_INICIALES),
  ),
  caso("listarTableros", () => reportes.listarTableros()),
  caso("listarRolesParaCompartir", () => reportes.listarRolesParaCompartir()),
  caso("crearTablero", () =>
    reportes.guardarTablero({
      nombre: "Gerencia",
      predeterminado: true,
      tarjetas: [{ codigo: "ventas_por_dia", titulo: null, visual: "barras", ancho: 2, alto: "mediano" }],
      filtros: reportes.FILTROS_INICIALES,
      rol_id: null,
    }),
  ),
  caso("editarTablero", () =>
    reportes.guardarTablero(
      {
        nombre: "Gerencia",
        predeterminado: false,
        tarjetas: [],
        filtros: reportes.FILTROS_INICIALES,
        rol_id: UUID,
      },
      UUID,
    ),
  ),
  caso("borrarTablero", () => reportes.borrarTablero(UUID)),
];

/** Con `superficie` el test compara la lista contra el objeto real del
 * módulo; sin ella (reportes) la lista es la fuente. */
const MODULOS: { nombre: string; casos: Caso[]; superficie?: object }[] = [
  { nombre: "pdv", casos: PDV, superficie: api },
  { nombre: "catalogo", casos: CATALOGO, superficie: catalogoApi },
  { nombre: "kds", casos: KDS, superficie: apiKds },
  { nombre: "reportes", casos: REPORTES },
];

// --- El arnés ---------------------------------------------------------------

type Salida = { metodo: string; url: string; cuerpo: unknown };

/** El primer 2xx que el contrato declara para la operación. Importa el
 * **código**, no solo el schema: un 204 no trae cuerpo, y responderle un
 * JSON al cliente saltearía la rama de `pedir` que existe justo porque
 * pedirle `.json()` a una respuesta vacía revienta. */
function respuestaExitosa(op: Operacion | undefined): { codigo: string; cuerpo?: ConCuerpo } {
  const codigo = Object.keys(op?.responses ?? {}).find((c) => c.startsWith("2")) ?? "200";
  return { codigo, cuerpo: op?.responses?.[codigo] };
}

/** Corre la operación con `fetch` intervenido: captura lo que sale y
 * responde con el ejemplo que el contrato promete para esa ruta. */
/**
 * El cuerpo tal como el contrato lo entiende.
 *
 * Una subida de archivo va en `multipart/form-data`, no en JSON: parsearla
 * revienta con «Unexpected token 'o'», que no dice nada. Se devuelve
 * `undefined` para que la ruta se verifique igual y la validación de esquema
 * no aplique — el contrato de un multipart no describe un objeto JSON.
 */
function cuerpoDe(body: BodyInit | null | undefined): unknown {
  if (!body) return undefined;
  if (typeof FormData !== "undefined" && body instanceof FormData) return undefined;
  return JSON.parse(String(body));
}

async function ejercitar(operacion: Caso): Promise<{ salida: Salida; resultado: unknown }> {
  let salida: Salida | null = null;
  const original = globalThis.fetch;
  // `datosDeReporte` memoiza por código+filtros: sin esto, la segunda
  // llamada de la misma operación no sale a la red y no habría nada que
  // capturar.
  reportes.limpiarCache();

  globalThis.fetch = ((url: string, opciones: RequestInit = {}) => {
    const metodo = opciones.method ?? "GET";
    salida = { metodo, url, cuerpo: cuerpoDe(opciones.body) };
    const { codigo, cuerpo } = respuestaExitosa(operacionDe(url, metodo));
    if (codigo === "204") return Promise.resolve(new Response(null, { status: 204 }));
    return Promise.resolve(
      new Response(JSON.stringify(ejemploDe(esquemaJson(cuerpo))), {
        status: Number(codigo),
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

for (const modulo of MODULOS) {
  if (modulo.superficie) {
    test(`${modulo.nombre}: toda operación del módulo está cubierta`, () => {
      const cubiertas = new Set(modulo.casos.map((c) => c.nombre));
      const faltantes = Object.keys(modulo.superficie!).filter((n) => !cubiertas.has(n));
      assert.deepEqual(faltantes, [], `operaciones de ${modulo.nombre} sin caso de contrato`);
    });
  }

  for (const operacion of modulo.casos) {
    const etiqueta = `${modulo.nombre}.${operacion.nombre}`;

    test(`${etiqueta}: la ruta existe en el contrato`, async () => {
      const { salida } = await ejercitar(operacion);
      assert.ok(
        operacionDe(salida.url, salida.metodo),
        `${salida.metodo} ${salida.url} no existe en openapi.json`,
      );
    });

    test(`${etiqueta}: el cuerpo valida contra el contrato`, async () => {
      const { salida } = await ejercitar(operacion);
      const esquema = esquemaJson(operacionDe(salida.url, salida.metodo)?.requestBody);
      if (!esquema) {
        assert.equal(salida.cuerpo, undefined, "manda cuerpo a un endpoint que no lo pide");
        return;
      }
      assert.deepEqual(validar(esquema, salida.cuerpo), []);
    });

    test(`${etiqueta}: el cliente lee la respuesta del contrato`, async () => {
      const { salida, resultado } = await ejercitar(operacion);
      const { codigo } = respuestaExitosa(operacionDe(salida.url, salida.metodo));
      if (codigo === "204") {
        assert.equal(resultado, undefined, "un 204 no trae cuerpo que leer");
        return;
      }
      assert.notEqual(resultado, undefined, "el cliente no devolvió nada");
      operacion.revisar?.(resultado as never);
    });
  }
}

// --- Rutas de todo el frontend ---------------------------------------------

/**
 * Lo de arriba ejercita de verdad los cuatro módulos importables. El resto
 * del ERP —Compras, Inventario, RRHH, Gerencia, Contabilidad, Marketing,
 * Usuarios— llama a la API desde Server Components y Server Actions, que
 * piden `next/headers` y un request y no se pueden importar en un
 * `node --test`.
 *
 * Para esos vale un escaneo del código fuente: **toda ruta que el frontend
 * nombra tiene que existir en el contrato, con ese método**. Es menos que
 * validar el cuerpo, pero cubre las ~170 llamadas de una vez y caza la
 * clase de error que hoy no cazaba nada: un endpoint renombrado o movido en
 * el backend rompe veinte pantallas y `openapi.json` se regenera tan
 * contento — el diff del contrato no sabe quién lo llamaba.
 *
 * Lo que NO cubre, dicho para que nadie lo lea como cobertura completa: el
 * cuerpo que esas pantallas arman. Eso sigue siendo trabajo de `tsc` sobre
 * tipos escritos a mano.
 */

const SALTAR = new Set(["node_modules", ".next", "test-results", "playwright-report"]);

function fuentes(dir: string, salida: string[] = []): string[] {
  for (const entrada of readdirSync(dir)) {
    if (SALTAR.has(entrada)) continue;
    const completa = path.join(dir, entrada);
    if (statSync(completa).isDirectory()) fuentes(completa, salida);
    else if (/\.tsx?$/.test(completa) && !completa.endsWith(".test.ts")) salida.push(completa);
  }
  return salida;
}

/** `pedir` habla contra el proxy y omite el prefijo; `apiFetch` va directo
 * a la API y lo lleva escrito. */
const PREFIJO = { pedir: "/api/v1", apiFetch: "" };

type Llamada = { archivo: string; ruta: string; metodo: string };

/** Recorta el argumento de la llamada contando paréntesis en vez de con una
 * expresión regular: los cuerpos traen paréntesis propios y un `.*?` se
 * corta en el primero que encuentra. */
function argumentosDe(fuente: string, desde: number): string {
  let i = desde;
  let profundidad = 1;
  while (i < fuente.length && profundidad > 0) {
    if (fuente[i] === "(") profundidad++;
    else if (fuente[i] === ")") profundidad--;
    i++;
  }
  return fuente.slice(desde, i - 1);
}

function llamadasEn(archivo: string): Llamada[] {
  const fuente = readFileSync(archivo, "utf-8");
  const encontradas: Llamada[] = [];
  for (const m of fuente.matchAll(/\b(apiFetch|pedir)\s*(?:<[^(]*?>)?\s*\(/g)) {
    const texto = argumentosDe(fuente, m.index + m[0].length);
    const ruta = texto.match(/^\s*[`"']([^`"']*)/);
    if (!ruta) continue; // la ruta llega por variable: no hay nada que leer acá
    const metodo = texto.match(/metodo:\s*"(\w+)"/);
    encontradas.push({
      archivo: path.relative(RAIZ, archivo),
      ruta: PREFIJO[m[1] as keyof typeof PREFIJO] + ruta[1],
      metodo: metodo?.[1] ?? "GET",
    });
  }
  return encontradas;
}

/**
 * Rutas cuyo último segmento es una variable que toma valores literales, no
 * un id. El escaneo no puede resolverlas solo, así que se declaran con sus
 * valores y se verifican **todos**: pasa de agujero a chequeo.
 */
const RUTAS_EXPANDIDAS: Record<string, string[]> = {
  "/api/v1/marketing/campanas/${campanaId}/${paso}": [
    "aprobacion",
    "lanzamiento",
    "cierre",
  ],
};

const TODAS = fuentes(RAIZ).flatMap(llamadasEn);

test("el escaneo encuentra las llamadas del frontend", () => {
  // Si un refactor cambia cómo se llama a la API, el escaneo devuelve cero
  // y todos los checks de abajo pasarían por vacíos. Este piso lo impide.
  assert.ok(TODAS.length > 150, `solo se encontraron ${TODAS.length} llamadas`);
});

test("toda ruta que el frontend nombra existe en el contrato", () => {
  const huerfanas = TODAS.filter((l) => !RUTAS_EXPANDIDAS[l.ruta] && !operacionDe(l.ruta, l.metodo)).map(
    (l) => `${l.archivo}: ${l.metodo} ${l.ruta}`,
  );
  assert.deepEqual(huerfanas, []);
});

test("las rutas con segmento variable existen para todos sus valores", () => {
  const declaradas = Object.keys(RUTAS_EXPANDIDAS);
  const usadas = new Set(TODAS.filter((l) => declaradas.includes(l.ruta)).map((l) => l.ruta));
  assert.deepEqual(
    [...usadas].sort(),
    declaradas.sort(),
    "hay rutas declaradas que ya nadie llama, o al revés",
  );

  const huerfanas: string[] = [];
  for (const llamada of TODAS) {
    for (const valor of RUTAS_EXPANDIDAS[llamada.ruta] ?? []) {
      const concreta = llamada.ruta.replace(/\$\{[^}]+\}$/, valor);
      if (!operacionDe(concreta, llamada.metodo)) {
        huerfanas.push(`${llamada.archivo}: ${llamada.metodo} ${concreta}`);
      }
    }
  }
  assert.deepEqual(huerfanas, []);
});
