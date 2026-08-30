/**
 * La regla que este archivo protege: el usuario nunca ve el error crudo de
 * Pydantic. Antes leía "Field required; Input should be greater than 0" —en
 * inglés y sin decir qué campo—; hoy el servidor manda el texto ya armado y
 * los campos aparte. Corre con `npm test`.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { ApiError } from "./api.ts";
import { ErrorApi } from "./cliente-api.ts";
import { estadoDeError, leerError } from "./errores.ts";

function respuesta(cuerpo: unknown, status = 422): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

test("el sobre del ERP: detalle legible y campos aparte", async () => {
  const { mensaje, campos } = await leerError(
    respuesta({
      detail: "Código: obligatorio; Cantidad: debe ser mayor que 0",
      errores: [
        { campo: "codigo", etiqueta: "Código", mensaje: "obligatorio" },
        { campo: "cantidad", etiqueta: "Cantidad", mensaje: "debe ser mayor que 0" },
      ],
    }),
  );
  assert.equal(mensaje, "Código: obligatorio; Cantidad: debe ser mayor que 0");
  assert.deepEqual(
    campos.map((c) => c.campo),
    ["codigo", "cantidad"],
  );
});

test("un error de negocio sigue siendo solo texto", async () => {
  const { mensaje, campos } = await leerError(
    respuesta({ detail: "el pago excede el saldo de la cuenta" }, 409),
  );
  assert.equal(mensaje, "el pago excede el saldo de la cuenta");
  assert.deepEqual(campos, []);
});

test("el formato crudo de FastAPI sigue siendo legible", async () => {
  // Respaldo: el hub de sucursal y cualquier API vieja pueden contestar así.
  const { mensaje } = await leerError(
    respuesta({ detail: [{ msg: "Field required" }, { msg: "Input should be > 0" }] }),
  );
  assert.equal(mensaje, "Field required; Input should be > 0");
});

test("un detalle de lista sin `msg` no escribe 'undefined'", async () => {
  const { mensaje } = await leerError(respuesta({ detail: [{ loc: ["body"] }] }, 400));
  assert.equal(mensaje, "Error 400");
});

test("un cuerpo que no es JSON cae al mensaje genérico", async () => {
  const { mensaje } = await leerError(new Response("<html>502</html>", { status: 502 }));
  assert.equal(mensaje, "Error 502");
});

test("los campos llegan a las dos clases de error del proyecto", () => {
  const campos = [{ campo: "codigo", etiqueta: "Código", mensaje: "obligatorio" }];
  assert.deepEqual(new ApiError(422, "x", undefined, campos).campos, campos);
  assert.deepEqual(new ErrorApi(422, "x", campos).campos, campos);
  assert.deepEqual(new ApiError(500, "x").campos, []);
});

test("estadoDeError pasa el mensaje del servidor y sus campos", () => {
  const campos = [{ campo: "codigo", etiqueta: "Código", mensaje: "obligatorio" }];
  const estado = estadoDeError(new ErrorApi(422, "Código: obligatorio", campos), "No se pudo.");
  assert.deepEqual(estado, { error: "Código: obligatorio", ok: false, campos });
});

test("lo que no viene de la API usa el mensaje del llamador", () => {
  // Un `TypeError: fetch failed` no le dice nada a un cajero.
  const estado = estadoDeError(new TypeError("fetch failed"), "No se pudo guardar.");
  assert.deepEqual(estado, { error: "No se pudo guardar.", ok: false });
});
