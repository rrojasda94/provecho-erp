import assert from "node:assert/strict";
import test from "node:test";

import {
  diasHasta,
  estadoDeSede,
  frecuenciaCompra,
  leerAmbito,
  queryDeAmbito,
  variacionPrecio,
  type KardexAlmacen,
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

const ID = "3f2c1d4e-5a6b-4c7d-8e9f-0a1b2c3d4e5f";

test("el ámbito se lee de la URL y lo raro es la empresa", () => {
  assert.deepEqual(leerAmbito(`almacen:${ID}`), { tipo: "almacen", id: ID });
  assert.deepEqual(leerAmbito(`sucursal:${ID}`), { tipo: "sucursal", id: ID });
  assert.equal(leerAmbito("almacen:no-es-un-id"), null);
  assert.equal(leerAmbito("empresa:x"), null);
  assert.equal(leerAmbito(undefined), null);
  assert.equal(
    queryDeAmbito({ tipo: "sucursal", id: ID }),
    `sucursal_id=${ID}`,
  );
  assert.equal(queryDeAmbito(null), "");
});

test("una sede bajo el mínimo es peligro; reponer en una semana, alerta", () => {
  const fila = (
    stock: string,
    minimo: string | null,
    proxima: string | null,
  ): KardexAlmacen => ({
    almacen_id: ID,
    almacen: "Local",
    sucursal_id: null,
    sucursal: null,
    stock,
    stock_minimo: minimo,
    consumo_diario: "1",
    proxima_compra: proxima,
    reposiciones_90_dias: 0,
  });
  assert.equal(
    estadoDeSede(fila("3", "4", "2026-09-23"), "2026-09-23"),
    "peligro",
  );
  assert.equal(
    estadoDeSede(fila("10", "4", "2026-09-28"), "2026-09-23"),
    "alerta",
  );
  assert.equal(estadoDeSede(fila("50", "4", "2026-10-30"), "2026-09-23"), null);
  assert.equal(estadoDeSede(fila("50", null, null), "2026-09-23"), null);
});
