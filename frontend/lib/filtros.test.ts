import assert from "node:assert/strict";
import { test } from "node:test";

import { filtrosDe, queryDeFiltros } from "./filtros.ts";

test("un filtro vacío no viaja en la query", () => {
  const query = queryDeFiltros({ marca: "m1", almacen: "", estado: undefined });
  assert.equal(query.toString(), "marca_id=m1");
});

test("el almacén cambia de nombre según el endpoint", () => {
  assert.equal(
    queryDeFiltros({ almacen: "a1" }, "almacen_solicitante_id").toString(),
    "almacen_solicitante_id=a1",
  );
  assert.equal(queryDeFiltros({ almacen: "a1" }).toString(), "almacen_id=a1");
});

test("los cuatro filtros ausentes quedan como texto vacío para los selectores", () => {
  assert.deepEqual(filtrosDe({}), {
    almacen: "",
    estado: "",
    sucursal: "",
    marca: "",
  });
});
