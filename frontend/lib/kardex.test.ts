import assert from "node:assert/strict";
import test from "node:test";

import {
  diasHasta,
  frecuenciaCompra,
  variacionPrecio,
  type PrecioHistorico,
} from "./kardex.ts";

test("la frecuencia de compra promedia los intervalos entre días distintos", () => {
  // Dos recepciones el mismo día cuentan como una compra.
  assert.equal(
    frecuenciaCompra([
      "2026-09-01T10:00:00Z",
      "2026-09-01T15:00:00Z",
      "2026-09-08T09:00:00Z",
      "2026-09-22T09:00:00Z",
    ]),
    11,
  );
  assert.equal(frecuenciaCompra(["2026-09-01T10:00:00Z"]), null);
});

test("diasHasta cuenta hacia adelante y hacia atrás", () => {
  assert.equal(diasHasta("2026-09-30", "2026-09-23"), 7);
  assert.equal(diasHasta("2026-09-20", "2026-09-23"), -3);
});

test("variacionPrecio compara las dos últimas compras", () => {
  const p = (costo: string): PrecioHistorico => ({
    fecha: "2026-09-01",
    costo_unitario: costo,
    cantidad: "1",
    orden_compra_id: "x",
    proveedor_id: "y",
    proveedor: null,
  });
  assert.equal(variacionPrecio([p("10"), p("12.5")]), 25);
  assert.equal(variacionPrecio([p("10")]), null);
});
