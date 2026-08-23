import { expect, test } from "@playwright/test";

import {
  ADMIN,
  avancePinpad,
  avisoLogin,
  BLOQUEABLE,
  campoUsuario,
  CAJERO,
  FANTASMA,
  ingresar,
  PINPAD_LOGIN,
  tecleaPinLogin,
} from "./util";

/**
 * Sesión y permisos visuales: los dos casos que la estrategia de pruebas
 * (`docs/engineering/testing-strategy.md`) da por justificados además del
 * flujo del dinero.
 *
 * 1. **Que la sesión funcione.** Si el login, la cookie o el guard se
 *    rompen, no importa qué más ande — y ninguna de las tres piezas vive
 *    entera de un solo lado: la cookie la pone una Server Action, el guard
 *    corre en el servidor y el redirect lo resuelve el cliente.
 * 2. **El gate de módulo por permiso** (ADR-013 y su enmienda de
 *    2026-08-03). Es el único caso donde *ver* ya es el privilegio, y el
 *    filtro del home es solo UX: lo que decide es el `layout.tsx`. Probarlo
 *    entrando por URL directa es la única forma de verificar que el guard
 *    real está puesto y no solo el filtro cosmético.
 *
 * A partir de ADR-050 se suma **cómo** se entra, que es parte de lo mismo:
 * el PIN se teclea en el pinpad y el login ya no tiene campo de contraseña.
 * Es un candado que solo existe en pantalla —del lado del servidor no hay
 * diferencia entre un PIN escrito y uno tocado—, y por eso entra en el
 * techo de `docs/engineering/testing-strategy.md` en vez de irse a `uso/`.
 *
 * Sin `serial` a propósito: ninguna de estas pruebas toca el estado de la
 * caja ni deja rastro en la base, así que no se pasan nada entre ellas. La
 * única que sí deja rastro —el lockout— lo deja sobre una cuenta de
 * sacrificio que no usa nadie más (`BLOQUEABLE`).
 */

test("una ruta protegida sin sesión manda al login", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole("button", { name: "Ingresar" })).toBeVisible();
});

test("el login deja el token en una cookie httpOnly y el logout la borra", async ({
  page,
  context,
}) => {
  await ingresar(page, ADMIN);

  const token = (await context.cookies()).find((c) => c.name === "provecho_token");
  expect(token).toBeDefined();
  // `httpOnly` es la razón de ser de esta prueba: un token legible por
  // `document.cookie` lo roba cualquier XSS, y es un atributo que no se ve
  // en ninguna pantalla — se rompe en silencio.
  expect(token?.httpOnly).toBe(true);

  // Salir dejó de ser un botón suelto en la barra: vive en el menú de la
  // sesión, junto a las preferencias de presentación.
  await page.getByRole("button", { name: new RegExp(`Sesión de ${ADMIN.usuario}`, "i") }).click();
  await page.getByRole("menuitem", { name: /Cerrar sesión/i }).click();
  await expect(page).toHaveURL(/\/login/);

  // Y la sesión quedó realmente muerta, no solo la pantalla cambiada.
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);
});

test("el login se teclea en el pinpad y no tiene ningún campo de contraseña", async ({
  page,
}) => {
  await page.goto("/login");

  // La aserción que existe para que el patrón no vuelva a colarse (ADR-050).
  // No es teórica: el PIN estuvo en un `<input type="password">` hasta hoy,
  // y con el navegador ofreciendo guardarlo la tablet de la caja entra al
  // turno siguiente con la cuenta del anterior. Se mira el DOM y no el
  // comportamiento porque un `type="password"` agregado sin querer no rompe
  // ninguna otra prueba: sigue todo verde y el agujero vuelve.
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
  await expect(page.locator("input[autocomplete*='password']")).toHaveCount(0);

  const teclas = page.getByTestId(PINPAD_LOGIN);
  await expect(teclas).toBeVisible();

  // Un toque que registra es la sonda de que React ya tomó la pantalla; sin
  // esperarlo, las teclas físicas de abajo caerían en el vacío.
  await tecleaPinLogin(page, "0");
  await teclas.getByRole("button", { name: "Borrar todo" }).click();
  await expect(avancePinpad(page)).toHaveText("0 de 6 dígitos");

  // Teclado físico y región viva. En el PDV esto era una comodidad; en el
  // login es la vía principal para todo el back office, que se opera desde
  // una PC — y los puntos son `aria-hidden`, así que sin la región un lector
  // de pantalla no tendría ninguna señal de que el toque registró.
  await teclas.getByRole("button", { name: "1", exact: true }).focus();
  await page.keyboard.press("5");
  await page.keyboard.press("7");
  await expect(avancePinpad(page)).toHaveText("2 de 6 dígitos");
  await page.keyboard.press("Backspace");
  await expect(avancePinpad(page)).toHaveText("1 de 6 dígitos");
});

test("un PIN equivocado no borra el usuario tecleado", async ({ page }) => {
  // Con el usuario borrado en cada intento fallido, volver a escribirlo es
  // la fricción que termina en "dejá la sesión abierta". React 19 lo hacía
  // solo: resetea los campos no controlados de un `<form action>` cuando la
  // acción termina, también cuando devolvió error.
  await page.goto("/login");
  await campoUsuario(page).fill(FANTASMA.usuario);
  await tecleaPinLogin(page, FANTASMA.pin);

  await expect(avisoLogin(page)).toHaveAttribute("data-motivo", "credenciales");
  await expect(campoUsuario(page)).toHaveValue(FANTASMA.usuario);
  // Y el pinpad quedó vacío: si no, los seis puntos siguen llenos y no hay
  // dónde teclear de nuevo sin borrar a mano.
  await expect(avancePinpad(page)).toHaveText("0 de 6 dígitos");
});

test("una cuenta bloqueada avisa distinto que un PIN equivocado", async ({ page }) => {
  // Los tres rechazos del login —401, 423 y 429— llegaban con el mismo texto
  // genérico, y quien los recibe necesita cosas distintas: volver a teclear,
  // esperar quince minutos, o llamar a un supervisor. Con un solo texto las
  // tres terminan igual: probando de nuevo hasta bloquear la cuenta.
  await page.goto("/login");
  const aviso = avisoLogin(page);

  // Referencia: el rechazo por credenciales, sobre un usuario que no existe
  // para no gastarle intentos a nadie.
  await campoUsuario(page).fill(FANTASMA.usuario);
  await tecleaPinLogin(page, FANTASMA.pin);
  await expect(aviso).toHaveAttribute("data-motivo", "credenciales");
  const porCredenciales = await aviso.textContent();

  // Y ahora la cuenta de sacrificio, hasta agotar los cinco intentos que
  // `rules.MAX_INTENTOS_FALLIDOS` permite; el quinto ya responde 423.
  //
  // Se reintenta hasta ver el bloqueo en vez de contar exactamente cinco:
  // un reintento de CI encuentra la cuenta ya bloqueada de la corrida
  // anterior, y contar asumiría que siempre se arranca de cero. Cada vuelta
  // teclea seis dígitos y espera la respuesta — el pinpad se vacía al
  // enviar, así que no hay que borrarlo entre intentos.
  await campoUsuario(page).fill(BLOQUEABLE.usuario);
  await expect(async () => {
    await tecleaPinLogin(page, "999999");
    await expect(aviso).toHaveAttribute("data-motivo", "bloqueo", { timeout: 5_000 });
  }).toPass({ timeout: 90_000 });

  await expect(aviso).toContainText("15 minutos");
  expect(await aviso.textContent()).not.toBe(porCredenciales);
});

test("el cajero no ve Catálogo, ni entrando por URL", async ({ page }) => {
  // El cajero tiene `sales.crear`/`sales.cobrar` pero no
  // `sales.gestionar_catalogo`: con el filtro por prefijo veía y leía toda
  // la carta. Administrarla es acto de supervisor, no de quien vende con
  // ella.
  await ingresar(page, CAJERO);

  await expect(page.getByRole("link", { name: /Ventas/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /Catálogo/i })).toHaveCount(0);

  await page.goto("/catalogo/productos");
  await expect(page.getByText(/Sin permiso/i)).toBeVisible();
  await expect(page.getByText(/Pizza E2E/)).toHaveCount(0);
});

test("el admin sí ve Catálogo y lo puede abrir", async ({ page }) => {
  // La contraparte del caso anterior: sin esto, un gate que esconde el
  // módulo para *todos* pasaría por bueno.
  await ingresar(page, ADMIN);

  await page.getByRole("link", { name: /Catálogo/i }).click();
  await expect(page.getByText(/Sin permiso/i)).toHaveCount(0);
  await expect(page.getByText(/Pizza E2E/).first()).toBeVisible({ timeout: 30_000 });
});
