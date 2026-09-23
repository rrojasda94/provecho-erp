/**
 * El `next` del login es la puerta a un open redirect: lo que acepta tiene
 * que ser exactamente las apps y el SSO, nada más. Corre con `npm test`.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { esAppInstalable, ingresoDesde, SIGUIENTE_PERMITIDO, urlIngreso } from "./ingreso.ts";

test("acepta las tres apps y el SSO, con o sin consulta", () => {
  for (const destino of [
    "/kds",
    "/kds?pantalla=abc&sucursal=1",
    "/pdv?sucursal=1",
    "/reparto",
    "/oauth/authorize?client_id=bi",
  ]) {
    assert.ok(SIGUIENTE_PERMITIDO.test(destino), destino);
  }
});

test("rechaza cualquier otro destino", () => {
  for (const destino of [
    "",
    "/",
    "/login",
    "/kdsx",
    "/kds/ingresar",
    "//evil.com",
    "https://evil.com/kds",
    "/kds?x=1 y",
  ]) {
    assert.ok(!SIGUIENTE_PERMITIDO.test(destino), destino);
  }
});

test("urlIngreso conserva la consulta y omite lo indefinido", () => {
  assert.equal(urlIngreso("/reparto"), "/reparto/ingresar?next=%2Freparto");
  const url = urlIngreso("/kds", { pantalla: "p1", sucursal: undefined });
  assert.equal(url, "/kds/ingresar?next=%2Fkds%3Fpantalla%3Dp1");
  const siguiente = new URL(url, "http://x").searchParams.get("next");
  assert.equal(siguiente, "/kds?pantalla=p1");
  assert.ok(SIGUIENTE_PERMITIDO.test(siguiente ?? ""));
});

test("ingresoDesde vuelve a la app o cae al login de siempre", () => {
  assert.equal(
    ingresoDesde("/kds", "?pantalla=p1"),
    "/kds/ingresar?next=%2Fkds%3Fpantalla%3Dp1",
  );
  assert.equal(ingresoDesde("/reparto/algo", ""), "/reparto/ingresar?next=%2Freparto");
  assert.equal(ingresoDesde("/kdsx", ""), "/login");
  assert.equal(ingresoDesde("/inventario", "?x=1"), "/login");
});

test("esAppInstalable solo acepta las tres", () => {
  assert.ok(esAppInstalable("/pdv"));
  assert.ok(!esAppInstalable("https://evil.com"));
  assert.ok(!esAppInstalable(undefined));
});
