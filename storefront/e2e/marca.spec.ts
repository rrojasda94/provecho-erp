import { expect, test } from "@playwright/test";

/**
 * La marca en el sitio: tipografía propia (Tusker Grotesk, sin pedirle fuentes a
 * Google), logo en la cabecera, favicon y la imagen para compartir el enlace.
 */

test("tipografía, logo, favicon e imagen para compartir", async ({ page, request }) => {
  const pedidos: string[] = [];
  page.on("request", (r) => pedidos.push(r.url()));

  await page.goto("/");
  await expect(page.getByRole("img", { name: "Charlie's Pizzas" }).first()).toBeVisible();
  // Los SVG oficiales (cabecera y pie) cargaron de verdad: un <img> roto también es "visible".
  const logos = page.getByRole("img", { name: "Charlie's Pizzas" });
  expect(await logos.count()).toBeGreaterThanOrEqual(2);
  const cargaron = await logos.evaluateAll((imgs) =>
    (imgs as HTMLImageElement[]).map((i) => i.complete && i.naturalWidth > 0),
  );
  expect(cargaron.every(Boolean)).toBe(true);

  const cargadas = await page.evaluate(async () => {
    await document.fonts.ready;
    return [...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family);
  });
  expect(cargadas.some((f) => f.toLowerCase().includes("tusker"))).toBe(true);
  // Las fuentes salen del propio sitio: ni Anton ni Archivo desde Google.
  expect(pedidos.filter((u) => /fonts\.(googleapis|gstatic)\.com/.test(u))).toEqual([]);

  // Favicon y la imagen de Open Graph existen y son PNG (se piden por ruta: la
  // URL absoluta apunta al dominio público, no a este servidor de pruebas).
  for (const selector of ['link[rel="icon"]', 'meta[property="og:image"]']) {
    const destino = await page.locator(selector).first().getAttribute(
      selector.startsWith("link") ? "href" : "content",
    );
    const url = new URL(destino!, "http://localhost");
    const respuesta = await request.get(url.pathname + url.search);
    expect(respuesta.ok(), `${selector} → ${destino}`).toBe(true);
    expect(respuesta.headers()["content-type"]).toContain("image/");
  }
});
