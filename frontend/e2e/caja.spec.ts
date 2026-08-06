import { expect, test, type Page } from "@playwright/test";

/**
 * El flujo del dinero de punta a punta: abrir caja → vender → cobrar →
 * cerrar caja.
 *
 * Es el camino donde un error cuesta plata, y es exactamente el que estuvo
 * roto un día entero sin que nadie lo notara (2026-08-04/05): los diálogos
 * del PDV mandaban el contrato anterior a ADR-025 y la API respondía 422.
 * Ningún test lo vio porque hasta hoy nada tocaba estas pantallas.
 *
 * Datos: `python -m src.seeders.seed` + `python -m src.seeders.e2e` sobre
 * `e2e.db`.
 */

const ADMIN = { usuario: "admin", pin: "123456" };
// Abrir caja exige que el encargado que releva **no** sea el cajero
// (RN-MDP-002): son dos personas, y por eso la prueba necesita dos usuarios.
const ENCARGADO = { usuario: "encargado_e2e", pin: "654321" };
const PRODUCTO = "Pizza E2E";

async function ingresar(page: Page) {
  await page.goto("/login");
  await page.getByRole("textbox").first().fill(ADMIN.usuario);
  await page.locator('input[type="password"]').fill(ADMIN.pin);
  await page.getByRole("button", { name: "Ingresar" }).click();
  // Se espera el **contenido** del destino, no la navegación: el `redirect`
  // de una Server Action lo resuelve el cliente sin recargar, así que nunca
  // se dispara el evento `load` que `waitForURL` espera por defecto y la
  // prueba se queda mirando una página que ya cambió.
  await expect(page.getByText(/Elige un módulo/i)).toBeVisible({ timeout: 30_000 });
}

/** El diálogo visible. Los de apertura y cierre están **los dos montados**
 * en el DOM —solo uno abierto— y comparten los testids del conteo por
 * denominación, así que buscar por testid a nivel de página encuentra dos
 * elementos y Playwright lo rechaza. Acotar al `dialog[open]` es también lo
 * correcto: la prueba interactúa con lo que el cajero ve. */
function dialogo(page: Page) {
  return page.locator("dialog[open]");
}

/** Teclea el conteo por denominación. Las claves son el valor del billete,
 * igual que el `detalle_denominaciones` que viaja al servidor. */
async function contar(page: Page, conteo: Record<string, number>) {
  for (const [valor, piezas] of Object.entries(conteo)) {
    await dialogo(page).getByTestId(`denom-${valor}`).fill(String(piezas));
  }
}

async function abrirCaja(page: Page, { declarado }: { declarado: string }) {
  await contar(page, { "100": 1, "50": 2 }); // 200.00
  await dialogo(page).getByTestId("apertura-declarado").fill(declarado);
  await dialogo(page).getByTestId("apertura-usuario").fill(ENCARGADO.usuario);
  await dialogo(page).getByTestId("apertura-pin").fill(ENCARGADO.pin);
  await dialogo(page).getByRole("button", { name: "Abrir caja" }).click();
  await expect(page.getByTestId("estado-caja")).toContainText("Caja abierta", {
    timeout: 15_000,
  });
}

// `serial`: la segunda prueba necesita la caja cerrada, y quien la cierra es
// la primera. Sin esto, un fallo en la primera hace fallar a la segunda con
// "no aparece el diálogo de apertura" — un síntoma que no dice nada del error
// real. En serie, la segunda queda **saltada** y el reporte señala una sola
// causa.
test.describe.serial("Flujo del dinero", () => {
  test("abrir caja, vender, cobrar y cerrar", async ({ page }) => {
    await ingresar(page);
    await page.goto("/pdv");

    // --- Apertura --------------------------------------------------------
    // El diálogo es bloqueante: sin caja abierta no se puede vender, y ese
    // candado es parte de lo que se prueba.
    await expect(dialogo(page).getByText("Apertura de caja")).toBeVisible();
    await abrirCaja(page, { declarado: "200" });

    // --- Venta -----------------------------------------------------------
    // Tocar el producto no lo agrega: abre su ficha (cantidad y nota para
    // cocina) y recién "Guardar" lo suma al pedido. Es deliberado —un toque
    // accidental en una pantalla táctil no debe meter una línea— y por eso
    // la prueba pasa por los dos pasos y no por un atajo.
    await page.getByRole("button", { name: new RegExp(PRODUCTO, "i") }).first().click();
    await dialogo(page).getByRole("button", { name: /Guardar/i }).click();
    await expect(page.getByText(/S\/ 25\.00/).first()).toBeVisible();

    // --- Tipo de orden ---------------------------------------------------
    // El PDV no deja salir del borrador sin tipo de orden (RN-COM-005), así
    // que el primer "Cobrar" abre el diálogo de tipo, no el de cobro. Es el
    // candado, no un rodeo: se prueba pasando por él.
    await page.getByRole("button", { name: /^Cobrar$/i }).click();
    await expect(dialogo(page).getByText("Tipo de orden")).toBeVisible();
    // "Para llevar" es el único que no pide dato extra (mesa o dirección).
    await dialogo(page).getByRole("button", { name: /Para llevar/i }).click();
    await dialogo(page).getByRole("button", { name: /^Confirmar$/ }).click();

    // --- Cobro -----------------------------------------------------------
    await page.getByRole("button", { name: /^Cobrar$/i }).click();
    await expect(dialogo(page).getByText("Cobrar", { exact: true })).toBeVisible();
    // Sin tocar nada: el diálogo llega con el medio por defecto y el monto
    // igual al total, y sin documento se emite boleta a Clientes varios.
    await dialogo(page).getByRole("button", { name: /^Confirmar pago$/ }).click();
    // El comprobante emitido cierra el cobro; sin token de Factiliza queda
    // pendiente de envío, que es justo lo que debe pasar sin proveedor.
    await expect(page.getByTestId("estado-caja")).toContainText("Caja abierta");

    // --- Cierre ----------------------------------------------------------
    await page.getByTestId("estado-caja").click();
    await expect(dialogo(page).getByText("Cierre de caja")).toBeVisible();
    // Se cuenta lo mismo que se abrió más lo cobrado en efectivo; el
    // descuadre lo calcula el servidor, no la pantalla.
    await contar(page, { "100": 2, "50": 0 });
    await dialogo(page).getByTestId(/^lote-/).first().fill("0");
    await dialogo(page).getByTestId("cierre-custodia").selectOption("local_caja_fuerte");
    await dialogo(page).getByTestId("cierre-usuario").fill(ENCARGADO.usuario);
    await dialogo(page).getByTestId("cierre-pin").fill(ENCARGADO.pin);
    await dialogo(page).getByRole("button", { name: "Cerrar caja" }).click();

    await expect(page.getByTestId("estado-caja")).toContainText("Caja cerrada", {
      timeout: 15_000,
    });
  });

  test("la diferencia entre lo contado y lo declarado no impide abrir", async ({
    page,
  }) => {
    // RN-POS-011: el local abre en su horario aunque falte sencillo. Es una
    // regla que solo se ve en la pantalla —el servidor la calcula y no
    // bloquea— y por eso vale probarla acá.
    await ingresar(page);
    await page.goto("/pdv");
    await expect(dialogo(page).getByText("Apertura de caja")).toBeVisible();

    await contar(page, { "100": 1, "50": 2 });
    await dialogo(page).getByTestId("apertura-declarado").fill("250");
    await expect(dialogo(page).getByText(/difiere en/i)).toBeVisible();

    await dialogo(page).getByTestId("apertura-usuario").fill(ENCARGADO.usuario);
    await dialogo(page).getByTestId("apertura-pin").fill(ENCARGADO.pin);
    await dialogo(page).getByRole("button", { name: "Abrir caja" }).click();
    await expect(page.getByTestId("estado-caja")).toContainText("Caja abierta", {
      timeout: 15_000,
    });
  });
});
