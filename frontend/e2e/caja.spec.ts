import { expect, test, type Page } from "@playwright/test";

import { ENCARGADO, contar, dialogo, ingresar } from "./util";

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

const PRODUCTO = "Pizza E2E";

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

// `serial`: estas pruebas se pasan el estado de la caja entre ellas —la
// primera la abre y la cierra, la segunda la vuelve a abrir— y el orden de
// declaración es el orden de ejecución. Sin esto, un fallo en la primera
// hace fallar a las siguientes con "no aparece el diálogo de apertura", un
// síntoma que no dice nada del error real. En serie quedan **saltadas** y el
// reporte señala una sola causa.
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

  test("un rechazo del servidor deja el formulario abierto con lo tecleado", async ({
    page,
  }) => {
    // El candado que solo existe en pantalla: si el PIN del encargado no
    // valida, el diálogo **no** puede limpiarse. Recontar el cajón entero
    // porque alguien tecleó mal seis dígitos es la clase de fricción que
    // termina en un conteo inventado — y el conteo es la evidencia sobre la
    // que se calcula el descuadre de todo el turno.
    await ingresar(page);
    await page.goto("/pdv");
    await expect(dialogo(page).getByText("Apertura de caja")).toBeVisible();

    await contar(page, { "100": 1, "50": 2 });
    await dialogo(page).getByTestId("apertura-declarado").fill("200");
    await dialogo(page).getByTestId("apertura-usuario").fill(ENCARGADO.usuario);
    await dialogo(page).getByTestId("apertura-pin").fill("000000");
    await dialogo(page).getByRole("button", { name: "Abrir caja" }).click();

    await expect(page.getByText(/No se pudo abrir la caja|credencial/i)).toBeVisible({
      timeout: 15_000,
    });
    // Lo que importa no es el aviso, es que nada se perdió.
    await expect(dialogo(page).getByText("Apertura de caja")).toBeVisible();
    await expect(dialogo(page).getByTestId("denom-100")).toHaveValue("1");
    await expect(dialogo(page).getByTestId("denom-50")).toHaveValue("2");
    await expect(dialogo(page).getByTestId("apertura-declarado")).toHaveValue("200");
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

  test("los campos de caja se encuentran por su nombre accesible", async ({
    page,
  }) => {
    // El resto de este archivo maneja los diálogos por `data-testid`, que es
    // un atributo nuestro: existe aunque el campo no tenga nombre para un
    // lector de pantalla. Por eso nadie vio que estos `<input>` tenían solo
    // `placeholder` —que desaparece al escribir y no es nombre accesible—
    // hasta que un agente que navega por el árbol de accesibilidad no
    // encontró el PIN y no pudo cerrar la caja. Esta prueba busca por
    // etiqueta a propósito: falla si el nombre se pierde otra vez.
    //
    // Entra con la caja **abierta** —la dejó así la prueba anterior— y la
    // cierra, que es el orden en que este archivo se pasa el estado.
    await ingresar(page);
    await page.goto("/pdv");

    await page.getByTestId("estado-caja").click();
    await expect(dialogo(page).getByText("Cierre de caja")).toBeVisible();

    await expect(dialogo(page).getByLabel("A dónde va el efectivo")).toBeVisible();
    await expect(dialogo(page).getByLabel("Usuario de quien recibe")).toBeVisible();
    await expect(dialogo(page).getByLabel("PIN de quien recibe")).toBeVisible();
    await expect(
      dialogo(page).getByLabel("Si hay descuadre, a quién se le atribuye"),
    ).toBeVisible();

    // Cerrar por etiqueta y no por `data-testid`: así la prueba no solo mira
    // que el nombre exista, sino que alcanza para operar la caja con él.
    await dialogo(page).getByTestId(/^lote-/).first().fill("0");
    await dialogo(page)
      .getByLabel("A dónde va el efectivo")
      .selectOption("local_caja_fuerte");
    await dialogo(page).getByLabel("Usuario de quien recibe").fill(ENCARGADO.usuario);
    await dialogo(page).getByLabel("PIN de quien recibe").fill(ENCARGADO.pin);
    await dialogo(page).getByRole("button", { name: "Cerrar caja" }).click();
    await expect(page.getByTestId("estado-caja")).toContainText("Caja cerrada", {
      timeout: 15_000,
    });

    // Con la caja cerrada el PDV vuelve a exigir apertura: es el único
    // momento en que ese diálogo se puede inspeccionar.
    await page.reload();
    await expect(dialogo(page).getByText("Apertura de caja")).toBeVisible();
    await expect(
      dialogo(page).getByLabel("El encargado declara entregar"),
    ).toBeVisible();
    await expect(dialogo(page).getByLabel("Usuario del encargado")).toBeVisible();
    await expect(dialogo(page).getByLabel("PIN del encargado")).toBeVisible();
  });
});
