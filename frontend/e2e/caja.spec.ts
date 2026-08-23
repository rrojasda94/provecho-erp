import { expect, test, type Page } from "@playwright/test";

import { contar, dialogo, ingresar } from "./util";

/**
 * El flujo del dinero de punta a punta: abrir caja → vender → cobrar →
 * cerrar caja.
 *
 * Es el camino donde un error cuesta plata, y es exactamente el que estuvo
 * roto un día entero sin que nadie lo notara (2026-08-04/05): los diálogos
 * del PDV mandaban el contrato anterior a ADR-025 y la API respondía 422.
 * Ningún test lo vio porque hasta hoy nada tocaba estas pantallas.
 *
 * **Sin PIN de nadie** desde ADR-049: abrir y cerrar son actos del cajero
 * con su propia sesión (RN-MDP-008). La firma del encargado que recibe el
 * efectivo no está acá porque no está en el PDV — vive en
 * `/contabilidad/caja` y se recorre en `uso/caja-custodia.spec.ts`.
 *
 * Datos: `python -m src.seeders.seed` + `python -m src.seeders.e2e` sobre
 * `e2e.db`.
 */

const PRODUCTO = "Pizza E2E";

async function abrirCaja(page: Page, { declarado }: { declarado: string }) {
  await contar(page, { "100": 1, "50": 2 }); // 200.00
  await dialogo(page).getByTestId("apertura-declarado").fill(declarado);
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
    // Acotado al ticket: el mismo importe aparece también en el botón que
    // alterna carta/pedido, que existe solo en el ancho angosto y acá está
    // oculto — un `getByText` suelto lo encontraba primero y esperaba 15 s a
    // que se hiciera visible algo que en esta medida no se ve.
    await expect(page.locator(".pdv-der").getByText(/S\/ 25\.00/).first()).toBeVisible();

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

    // El botón de consulta está donde se teclea el documento del receptor
    // (addendum de ADR-041). Con un número a medias **no sale a la red**:
    // cada consulta gasta cuota de un proveedor pago, así que un largo que
    // no es ni DNI ni RUC se rechaza acá y no allá.
    const buscar = dialogo(page).getByRole("button", { name: "Buscar DNI / RUC" });
    await expect(buscar).toBeVisible();
    await dialogo(page).getByLabel("Documento del receptor").fill("2061007");
    await buscar.click();
    await expect(dialogo(page).getByRole("status")).toContainText(/8 dígitos/);
    // Y la venta sigue sin documento, que es el caso normal en un mostrador
    // (RN-PER-005): se limpia y se cobra igual.
    await dialogo(page).getByLabel("Documento del receptor").fill("");

    // Sin tocar nada más: el diálogo llega con el medio por defecto y el
    // monto igual al total, y sin documento se emite boleta a Clientes
    // varios.
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
    await dialogo(page).getByRole("button", { name: "Cerrar caja" }).click();

    await expect(page.getByTestId("estado-caja")).toContainText("Caja cerrada", {
      timeout: 15_000,
    });
  });

  test("un rechazo del servidor deja el formulario abierto con lo tecleado", async ({
    page,
  }) => {
    // El candado que solo existe en pantalla: si el servidor rechaza la
    // apertura, el diálogo **no** puede limpiarse. Recontar el cajón entero
    // porque algo falló del otro lado es la clase de fricción que termina en
    // un conteo inventado — y el conteo es la evidencia sobre la que se
    // calcula el descuadre de todo el turno.
    //
    // El rechazo se simula interceptando la llamada. Antes lo provocaba un
    // PIN mal tecleado, pero desde ADR-049 la apertura no pide PIN y no
    // quedó ninguna forma de que el servidor la rechace **desde esta
    // pantalla**: los montos salen de un conteo por denominaciones fijas y
    // el diálogo solo aparece cuando no hay caja abierta. Lo que este caso
    // prueba es el manejo de error del cliente, así que fabricar la
    // respuesta es exactamente lo que corresponde.
    await ingresar(page);
    await page.route("**/api/proxy/api/v1/accounting/cajas/apertura", (ruta) =>
      ruta.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({ detail: "ya hay una caja abierta en este punto de venta" }),
      }),
    );
    await page.goto("/pdv");
    await expect(dialogo(page).getByText("Apertura de caja")).toBeVisible();

    await contar(page, { "100": 1, "50": 2 });
    await dialogo(page).getByTestId("apertura-declarado").fill("200");
    await dialogo(page).getByRole("button", { name: "Abrir caja" }).click();

    await expect(page.getByText(/No se pudo abrir la caja|ya hay una caja/i)).toBeVisible({
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
    // encontró un campo y no pudo cerrar la caja. Esta prueba busca por
    // etiqueta a propósito: falla si el nombre se pierde otra vez.
    //
    // Los campos de firma ya no están (ADR-049); lo que queda son los dos
    // `<select>` del cierre y el monto declarado de la apertura, que son
    // exactamente los que no tienen `<label>` propio y dependen de su
    // `aria-label`.
    //
    // Entra con la caja **abierta** —la dejó así la prueba anterior— y la
    // cierra, que es el orden en que este archivo se pasa el estado.
    await ingresar(page);
    await page.goto("/pdv");

    await page.getByTestId("estado-caja").click();
    await expect(dialogo(page).getByText("Cierre de caja")).toBeVisible();

    await expect(dialogo(page).getByLabel("A dónde va el efectivo")).toBeVisible();
    await expect(
      dialogo(page).getByLabel("Si hay descuadre, a quién se le atribuye"),
    ).toBeVisible();

    // Cerrar por etiqueta y no por `data-testid`: así la prueba no solo mira
    // que el nombre exista, sino que alcanza para operar la caja con él.
    await dialogo(page).getByTestId(/^lote-/).first().fill("0");
    await dialogo(page)
      .getByLabel("A dónde va el efectivo")
      .selectOption("local_caja_fuerte");
    await dialogo(page)
      .getByLabel("Si hay descuadre, a quién se le atribuye")
      .selectOption("cajero");
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
    // Y no queda nada que firmar: la apertura ya no pide credenciales de
    // nadie (RN-MDP-008). Se afirma la ausencia porque volver a pedirlas
    // sería una regresión silenciosa — la pantalla seguiría funcionando.
    await expect(dialogo(page).getByLabel(/^Usuario /)).toHaveCount(0);
    await expect(dialogo(page).getByLabel(/^PIN /)).toHaveCount(0);
  });
});
