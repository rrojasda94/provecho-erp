import { expect, test } from "@playwright/test";

/**
 * Recuperar la clave (RN-WEB-018): las páginas nuevas se ven y hablan con la API.
 * El correo no sale en este entorno (sin SMTP), y justamente por eso el sitio tiene
 * que responder igual: contar que "si el correo tiene cuenta, te llegó un enlace".
 */

test("recuperar la clave: enlace desde ingresar, pedido y aviso sin delatar cuentas", async ({
  page,
}) => {
  await page.goto("/cuenta/ingresar");
  await expect(page.getByRole("heading", { name: "Ingresar" })).toBeVisible();
  // Sin Client ID de Google no hay botón, y tampoco separador huérfano.
  await expect(page.getByText("o", { exact: true })).toHaveCount(0);

  await page.getByRole("link", { name: "¿Olvidaste tu contraseña?" }).click();
  await expect(page).toHaveURL(/\/cuenta\/recuperar/);
  await expect(page.getByRole("heading", { name: "Recuperar mi clave" })).toBeVisible();
  await expect(page.getByText("¿No tienes acceso a ese correo?")).toBeVisible();

  await page.getByPlaceholder("Tu email").fill("nadie-tiene-esta-cuenta@example.com");
  await page.getByRole("button", { name: "Enviarme el enlace" }).click();
  await expect(page.getByText(/Si ese correo tiene una cuenta/)).toBeVisible();
});

test("elegir la clave nueva: sin enlace completo, o con uno vencido, se explica", async ({
  page,
}) => {
  await page.goto("/cuenta/restablecer");
  await expect(page.getByText("Este enlace no está completo.")).toBeVisible();

  await page.goto("/cuenta/restablecer?token=un-enlace-que-no-existe");
  await page.getByPlaceholder("Clave nueva (mínimo 8 caracteres)").fill("clave-nueva-123");
  await page.getByPlaceholder("Repite la clave nueva").fill("clave-nueva-123");
  await page.getByRole("button", { name: "Cambiar mi clave" }).click();
  await expect(page.getByText(/El enlace venció o no es válido/)).toBeVisible();
});
