import assert from "node:assert/strict";
import test from "node:test";

import { NOMBRE_MOTIVO, QUE_HACER, origenDe } from "./asientos-omitidos.ts";

const ID = "3f2c1d4e-5a6b-4c7d-8e9f-0a1b2c3d4e5f";

test("una venta omitida dice que es una venta y lleva a su ficha", () => {
  assert.deepEqual(origenDe("sales.venta_confirmada", ID), {
    operacion: "Venta",
    ruta: `/ventas/${ID}`,
  });
});

test("la depreciación lleva al activo, no al periodo", () => {
  assert.equal(
    origenDe("accounting.depreciacion_mensual", `${ID}:2026-08`).ruta,
    `/activos/activos/${ID}`,
  );
});

test("sin referencia legible no inventa un enlace", () => {
  assert.equal(origenDe("sales.venta_confirmada", "?").ruta, null);
});

test("un evento sin traducir se muestra tal cual", () => {
  assert.deepEqual(origenDe("rrhh.algo_nuevo", ID), {
    operacion: "rrhh.algo_nuevo",
    ruta: null,
  });
});

test("cada motivo del backend tiene nombre y qué hacer", () => {
  for (const motivo of [
    "periodo_cerrado",
    "sin_cuentas",
    "sin_plantilla",
    "error",
  ]) {
    assert.ok(NOMBRE_MOTIVO[motivo], motivo);
    assert.ok(QUE_HACER[motivo], motivo);
  }
});
