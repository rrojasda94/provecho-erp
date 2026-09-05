/**
 * La regla que este archivo protege: un asiento que cuadra en plata cuadra
 * también en el código. Antes se comparaba `debe === haber` sobre sumas de
 * flotantes, así que 0.10 + 0.20 contra 0.30 —tres líneas perfectamente
 * normales— dejaba «Registrar» apagado y el panel diciendo «Diferencia:
 * 0.00». Corre con `npm test`.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { aCentavos, cuadreDe } from "./cuadre.ts";

test("0.10 + 0.20 contra 0.30 cuadra", () => {
  const { debe, haber, cuadra } = cuadreDe([
    { tipo: "debe", monto: "0.10" },
    { tipo: "debe", monto: "0.20" },
    { tipo: "haber", monto: "0.30" },
  ]);
  assert.equal(cuadra, true);
  assert.equal(debe, 0.3);
  assert.equal(haber, 0.3);
  // El caso exacto que fallaba: la suma en flotante no es 0.3.
  assert.notEqual(0.1 + 0.2, 0.3);
});

test("una diferencia real sigue sin cuadrar, y se puede mostrar", () => {
  const { debe, haber, cuadra } = cuadreDe([
    { tipo: "debe", monto: "100.00" },
    { tipo: "haber", monto: "99.99" },
  ]);
  assert.equal(cuadra, false);
  assert.equal((debe - haber).toFixed(2), "0.01");
});

test("un asiento de puros ceros no cuadra: no documenta nada", () => {
  assert.equal(cuadreDe([{ tipo: "debe", monto: 0 }, { tipo: "haber", monto: 0 }]).cuadra, false);
});

test("una línea a medio escribir cuenta cero, no NaN", () => {
  const { debe, cuadra } = cuadreDe([
    { tipo: "debe", monto: "" },
    { tipo: "debe", monto: "5.00" },
    { tipo: "haber", monto: "5.00" },
  ]);
  assert.equal(debe, 5);
  assert.equal(cuadra, true);
});

test("los montos llegan como texto o como número, indistinto", () => {
  assert.equal(aCentavos("12.34"), 1234);
  assert.equal(aCentavos(12.34), 1234);
  assert.equal(aCentavos("no es plata"), 0);
});

test("un importe largo no arrastra el error del flotante", () => {
  const lineas = Array.from({ length: 3 }, () => ({ tipo: "debe", monto: "0.07" }));
  const { debe, cuadra } = cuadreDe([...lineas, { tipo: "haber", monto: "0.21" }]);
  assert.equal(debe, 0.21);
  assert.equal(cuadra, true);
});
