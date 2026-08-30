import assert from "node:assert/strict";
import test from "node:test";

import { cuerpoDeFactura, faltaEnLaFactura } from "./factura-proveedor.ts";

/** Un `FormData` de mentira: `node:test` corre sin DOM. */
function campos(valores: Record<string, string>) {
  return { get: (nombre: string) => valores[nombre] ?? null };
}

test("un campo vacío desaparece en vez de viajar como cadena vacía", () => {
  // Es el bug que esto existe para evitar: `fecha_emision: ""` contra un
  // `date | None` del contrato es un 422, y el formulario manda "" por el
  // solo hecho de tener el campo dibujado.
  const cuerpo = cuerpoDeFactura(
    campos({ serie: "F001", correlativo: "12" }),
    "clave-1",
  );
  assert.equal(cuerpo.fecha_emision, undefined);
  assert.equal(cuerpo.total, undefined);
  assert.equal(cuerpo.emisor_num_doc, undefined);
  assert.equal("fecha_emision" in JSON.parse(JSON.stringify(cuerpo)), false);
});

test("el IGV tiene tres estados y no dos", () => {
  const sinElegir = cuerpoDeFactura(campos({ gravado_igv: "" }), "k");
  const gravada = cuerpoDeFactura(campos({ gravado_igv: "si" }), "k");
  const exonerada = cuerpoDeFactura(campos({ gravado_igv: "no" }), "k");

  // Sin elegir manda el régimen de la empresa (ADR-081): no es lo mismo que
  // afirmar que la operación no lleva IGV.
  assert.equal(sinElegir.gravado_igv, undefined);
  assert.equal(gravada.gravado_igv, true);
  assert.equal(exonerada.gravado_igv, false);
});

test("los valores por defecto son los del formulario", () => {
  const cuerpo = cuerpoDeFactura(campos({}), "k");
  assert.equal(cuerpo.tipo, "factura");
  assert.equal(cuerpo.sustento, "contrato_credito");
});

test("una factura sin serie o sin número no se manda", () => {
  assert.match(
    faltaEnLaFactura(cuerpoDeFactura(campos({ correlativo: "1" }), "k")) ?? "",
    /serie/,
  );
  assert.match(
    faltaEnLaFactura(cuerpoDeFactura(campos({ serie: "F001" }), "k")) ?? "",
    /número/,
  );
  assert.equal(
    faltaEnLaFactura(cuerpoDeFactura(campos({ serie: "F001", correlativo: "1" }), "k")),
    null,
  );
});
