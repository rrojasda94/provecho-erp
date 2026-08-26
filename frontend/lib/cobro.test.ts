import assert from "node:assert/strict";
import { test } from "node:test";

import { calcularCobro, cobroBloqueado } from "./cobro.ts";
import type { MedioPago } from "./pdv.ts";

/**
 * Lo que decide cuánta plata entra y si el cobro puede salir.
 *
 * Existe como prueba por el cobro que no salía en staging: ese entorno
 * corre solo `seeders.seed`, que no daba de alta ningún medio de pago, así
 * que el diálogo no ofrecía ninguno, `medioId` quedaba en `""` y el
 * servidor respondía «Input should be a valid UUID» — un mensaje que el
 * cajero no puede entender ni corregir.
 */

const EFECTIVO: MedioPago = { id: "m1", nombre: "Efectivo", tipo: "efectivo" };
const YAPE: MedioPago = { id: "m2", nombre: "Yape", tipo: "billetera_digital" };
const MEDIOS = [EFECTIVO, YAPE];

test("sin medio de pago el cobro no se puede confirmar", () => {
  const { pagado, excede } = calcularCobro(25.23, [], "25.23", "", []);
  assert.equal(pagado, 25.23);
  assert.equal(cobroBloqueado(false, excede, pagado, 25.23, true, ""), true);
  assert.equal(cobroBloqueado(false, excede, pagado, 25.23, true, "m1"), false);
});

test("en efectivo el exceso es vuelto, no un pago de más", () => {
  const r = calcularCobro(25.23, [], "50", "m1", MEDIOS);
  assert.equal(r.vuelto, 24.77);
  assert.equal(r.aplicado, 25.23, "a la venta se le acredita el saldo, no los 50");
  assert.equal(r.excede, false);
  assert.equal(r.restante, 0);
});

test("un medio sin cajón no da vuelto: el exceso bloquea", () => {
  const r = calcularCobro(25.23, [], "50", "m2", MEDIOS);
  assert.equal(r.vuelto, 0);
  assert.equal(r.excede, true);
  assert.equal(cobroBloqueado(false, r.excede, r.pagado, 25.23, true, "m2"), true);
});

test("el segundo medio cubre lo que faltó del primero", () => {
  const r = calcularCobro(50, [{ medioId: "m2", monto: 20 }], "30", "m1", MEDIOS);
  assert.equal(r.falta, 30);
  assert.equal(r.pagado, 50);
  assert.equal(r.restante, 0);
  assert.equal(r.vuelto, 0);
});
