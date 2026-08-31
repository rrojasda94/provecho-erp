import { expect, test, type Page } from "@playwright/test";

import { contar, dialogo, ingresar } from "../e2e/util";
import { auditar, EN_VUELO } from "./auditoria";

/**
 * Que todas las pantallas se puedan **usar** en las tres medidas reales del
 * grupo: el teléfono del encargado, la tablet de cocina y mostrador, y la PC
 * de oficina.
 *
 * No compara píxeles contra una imagen de referencia —eso se rompe con cada
 * cambio de copy— sino que afirma dos cosas que sí son bugs cuando fallan:
 * que ningún control quede dibujado fuera de un contenedor que lo recorta
 * (una opción que existe y no se puede tocar) y que todo diálogo modal quede
 * centrado en la pantalla.
 *
 * Nació de encontrar las dos cosas rotas a la vez (2026-08-18): el
 * `animation-fill-mode: both` de `.revelar` dejaba un `transform` identidad
 * computado, que convierte al contenedor en bloque contenedor de todo
 * `position: fixed` —los diecisiete diálogos aparecían pegados a la esquina
 * superior izquierda—, y el PDV escondía el ticket entero bajo 60rem, o sea
 * en toda tablet vertical.
 */

const MEDIDAS = [
  { nombre: "movil", width: 390, height: 844 },
  { nombre: "tablet", width: 820, height: 1180 },
  { nombre: "pc", width: 1440, height: 900 },
];

/** Todo módulo del shell `(app)` con pantalla de lista, más los raros que no
 * caen dentro (KDS, PDV). Quedan afuera las fichas de detalle con `[id]`
 * dinámico (`/ventas/[id]`, `/catalogo/productos/[id]`, etc.): no hay un id
 * fijo que apunte siempre a un registro sembrado, y su layout es el mismo
 * molde de ficha que ya audita `DialogoFormulario` en cada lista. */
const RUTAS = [
  "/",
  "/dashboard",
  "/inventario",
  "/inventario/stock",
  "/inventario/articulos",
  "/inventario/lotes",
  "/inventario/ajustes",
  "/inventario/categorias",
  "/inventario/skus",
  "/inventario/unidades-medida",
  "/inventario/devoluciones",
  "/catalogo",
  "/catalogo/productos",
  "/catalogo/recetas",
  "/compras",
  "/compras/ordenes-compra",
  "/compras/directas",
  "/compras/facturas",
  "/compras/proveedores",
  "/contabilidad",
  "/contabilidad/caja",
  "/contabilidad/pagos",
  "/contabilidad/periodos",
  "/contabilidad/plan-cuentas",
  "/gerencia",
  "/gerencia/decisiones",
  "/gerencia/divisas",
  "/gerencia/parametros",
  "/marketing",
  "/marketing/contenido",
  "/organizacion",
  "/organizacion/almacenes",
  "/organizacion/empresas",
  "/organizacion/marcas",
  "/organizacion/sucursales",
  "/produccion",
  "/reportes",
  "/reportes/distribucion",
  "/reportes/emitidos",
  "/reportes/escalamientos",
  "/rrhh",
  "/rrhh/contratacion",
  "/rrhh/trabajadores",
  "/usuarios",
  "/usuarios/personas",
  "/usuarios/roles",
  "/ventas",
  "/ventas/clientes",
  "/kds",
];

const ABRIDORES = /^(Nuev|Crear|Registrar|Agregar|Proponer|Importar|Editar|Ajustar|Configurar)/i;

const PRODUCTO = "Pizza E2E";

type Falla = { donde: string; clase: string; detalle: string };

/** Espera a que se vaya el esqueleto de carga (`EsqueletoPantalla`,
 * `aria-busy`) de las pantallas del shell `(app)`. Un `waitForTimeout` fijo
 * corre la misma carrera que el propio ERP resuelve con `loading.tsx`: en
 * frío, `next dev` compila la ruta la primera vez que se pide y puede tardar
 * más que cualquier número fijo razonable.
 *
 * El selector pide `aria-busy="true"` y no la sola presencia del atributo.
 * `DialogoFormulario` monta su `<form aria-busy={pendiente}>` dentro de un
 * `<dialog>` cerrado que **siempre** está en el DOM, y React escribe los
 * `aria-*` booleanos como texto: en reposo eso es un `aria-busy="false"`
 * que `[aria-busy]` casa igual y que no se va nunca. Con eso, toda pantalla
 * con un diálogo de alta —catálogo, organización, proveedores, plan de
 * cuentas: catorce de las cuarenta y tres— se comía los 60 s enteros de
 * espera. Tres medidas por catorce rutas son cuarenta y dos minutos de
 * reloj tirados, y son los que hacían que este caso no llegara nunca al
 * final de su recorrido. */
async function esperarCarga(page: Page) {
  await page
    .locator('[aria-busy="true"]')
    .first()
    .waitFor({ state: "detached", timeout: 60_000 })
    .catch(() => {});
  await page.waitForTimeout(300);
}

async function revisar(page: Page, donde: string, fallas: Falla[]) {
  // Reintenta una vez: `next dev` compila cada ruta la primera vez que se la
  // pide, y en frío eso puede tardar más que la espera de después del
  // `goto()`. La pantalla queda pintando el esqueleto de carga cuando
  // `auditar()` arranca, y si termina de resolver justo en el medio, el
  // `page.evaluate()` se cae — no es un hallazgo, es la propia navegación
  // todavía en vuelo.
  //
  // Tiene dos caras y hay que reintentar por las dos. Chromium a veces
  // destruye el contexto de ejecución en el medio del `evaluate`, y a veces
  // lo deja correr sobre un documento que todavía no tiene `<html>`. Lo
  // segundo pasa en las rutas que redirigen **después** de empezar a
  // transmitir —`/inventario`, `/compras`, `/contabilidad` y el resto de las
  // raíces de módulo cargan un documento y saltan al siguiente—, así que
  // `goto()` puede volver entre los dos y la espera de `esperarCarga()`
  // engancharse al documento que está por morir.
  const enVuelo = (e: unknown) =>
    e instanceof Error &&
    (e.message.includes("Execution context was destroyed") || e.message.includes(EN_VUELO));

  try {
    for (const h of await auditar(page)) fallas.push({ donde, ...h });
  } catch (e) {
    if (!enVuelo(e)) throw e;
    // Vuelve a esperar la carga, no solo a esperar: la espera anterior se
    // enganchó al documento que se estaba yendo, así que dio por cargada una
    // pantalla que ni había empezado a pintarse.
    await page.waitForTimeout(1500);
    await esperarCarga(page);
    for (const h of await auditar(page)) fallas.push({ donde, ...h });
  }
}

/** Recorre cada diálogo que la pantalla sepa abrir y lo audita abierto. */
async function revisarDialogos(page: Page, donde: string, fallas: Falla[]) {
  for (const boton of await page.getByRole("button").all()) {
    const texto = ((await boton.textContent()) ?? "").trim();
    if (!ABRIDORES.test(texto) || !(await boton.isVisible())) continue;
    await boton.click().catch(() => {});
    await page.waitForTimeout(400);
    if (!(await page.locator("dialog[open]").count())) continue;
    await revisar(page, `${donde} → «${texto}»`, fallas);
    await page.keyboard.press("Escape");
    await page.waitForTimeout(250);
  }
}

/** Deja una caja abierta, dos pantallas de cocina y un pedido en la cola:
 * sin datos, el KDS y el ticket del PDV se auditan vacíos y no prueban nada. */
async function prepararEscenario(page: Page): Promise<string[]> {
  await page.goto("/pdv");
  // Se espera a que la pantalla resuelva si hay caja antes de preguntar por
  // el diálogo: preguntarlo de una encuentra cero, se salta la apertura, y
  // los treinta minutos siguientes se van esperando una carta que sin caja
  // abierta no se pide. El síntoma es el bloqueo por inactividad del PDV
  // encima de todo, que no menciona la caja por ningún lado.
  await expect(page.getByTestId("estado-caja")).toBeVisible();
  if (await dialogo(page).getByText("Apertura de caja").isVisible()) {
    await contar(page, { "100": 1, "50": 2 });
    await dialogo(page).getByTestId("apertura-declarado").fill("200");
    await dialogo(page).getByRole("button", { name: "Abrir caja" }).click();
  }
  await expect(page.getByTestId("estado-caja")).toContainText("Caja abierta");

  // Pestaña nueva antes de marcar: los borradores son del punto de venta y
  // sobreviven a la corrida anterior (ADR-074), así que el PDV abre con la
  // cuenta que dejó otro recorrido. Sobre una orden ya enviada el botón dice
  // "Enviar aumento", no "Enviar", y la espera se iba entera al timeout.
  await page.getByRole("button", { name: "Nuevo pedido" }).click();

  await page.getByRole("button", { name: new RegExp(PRODUCTO, "i") }).first().click();
  await dialogo(page).getByRole("button", { name: /Guardar/i }).click();
  await page.getByRole("button", { name: /^Enviar$/i }).click();
  await expect(dialogo(page).getByText("Tipo de orden")).toBeVisible();
  await dialogo(page).getByRole("button", { name: /Para llevar/i }).click();
  await dialogo(page).getByRole("button", { name: /^Confirmar$/ }).click();
  await page.getByRole("button", { name: /^Enviar$/i }).click();
  await page.waitForTimeout(2000);

  await page.goto("/kds");
  for (const [nombre, tipo] of [
    ["Horno responsive", "Preparación"],
    ["Pase responsive", "Despacho"],
  ]) {
    await page.getByRole("button", { name: "Nueva pantalla" }).click();
    await dialogo(page).getByPlaceholder("Horno, Barra, Despacho…").fill(nombre);
    await dialogo(page).getByRole("button", { name: tipo, exact: true }).click();
    await dialogo(page).getByRole("button", { name: "Guardar" }).click();
    await expect(page.getByRole("link", { name: new RegExp(nombre) })).toBeVisible();
  }

  return page
    .getByRole("link", { name: /responsive/ })
    .evaluateAll((as) => as.map((a) => (a as HTMLAnchorElement).getAttribute("href")!));
}

/** La landing del QR y sus términos. Van en un test aparte y **sin
 * `ingresar()`** a propósito: la abre un cliente del restaurante desde su
 * teléfono, sin cuenta, y auditarla con sesión no probaría lo que importa —
 * que no rebote al login. El teléfono es su medida principal, no una más. */
const RUTAS_PUBLICAS = ["/reconocerte", "/reconocerte/terminos"];

test("la landing pública se usa sin cuenta en las tres medidas", async ({ page }) => {
  test.setTimeout(300_000);
  const fallas: Falla[] = [];

  for (const medida of MEDIDAS) {
    await page.setViewportSize({ width: medida.width, height: medida.height });
    for (const ruta of RUTAS_PUBLICAS) {
      await page.goto(ruta);
      await esperarCarga(page);
      // Sin sesión y sin redirección: es la única superficie del front que
      // tiene que responder igual a alguien que nunca inició sesión.
      expect(new URL(page.url()).pathname).toBe(ruta);
      await revisar(page, `${ruta} @ ${medida.nombre}`, fallas);
    }
  }

  expect(fallas.map((f) => `${f.donde} · ${f.clase}: ${f.detalle}`)).toEqual([]);
});

test("toda pantalla se puede usar en teléfono, tablet y PC", async ({ page }) => {
  test.setTimeout(1_800_000);
  await ingresar(page);
  const estaciones = await prepararEscenario(page);
  const fallas: Falla[] = [];

  for (const medida of MEDIDAS) {
    await page.setViewportSize({ width: medida.width, height: medida.height });

    for (const ruta of [...RUTAS, ...estaciones]) {
      await page.goto(ruta);
      await esperarCarga(page);
      await revisar(page, `${ruta} @ ${medida.nombre}`, fallas);
      await revisarDialogos(page, `${ruta} @ ${medida.nombre}`, fallas);
    }

    await page.goto("/pdv");
    await page.waitForTimeout(1500);
    await revisar(page, `/pdv @ ${medida.nombre}`, fallas);
    await revisarDialogos(page, `/pdv @ ${medida.nombre}`, fallas);

    // El ticket comparte celda con la carta en tablet vertical y teléfono:
    // se llega por el botón de la barra, y hay que auditarlo con él delante.
    const cambiar = page.getByTestId("cambiar-panel");
    if (await cambiar.isVisible()) {
      await cambiar.click();
      await page.waitForTimeout(600);
      await revisar(page, `/pdv (ticket) @ ${medida.nombre}`, fallas);
      await expect(page.getByRole("button", { name: /^Cobrar$/i })).toBeVisible();
    }
  }

  expect(fallas.map((f) => `${f.donde} · ${f.clase}: ${f.detalle}`)).toEqual([]);
});
