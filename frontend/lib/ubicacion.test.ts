import assert from "node:assert/strict";
import { test } from "node:test";

import { soloUbicacion } from "../components/direccion/ubicacion.ts";

test("un cliente entero se recorta al ancla", () => {
  // `ClienteBuscado` es `{...} & Ubicacion`: pasa como `Ubicacion` sin que el
  // tipo se queje, y esparcirlo entero mandaba `tipo: "natural"` al crear la
  // venta —que lo rechazaba con "tipo de venta inválido: natural".
  const cliente = {
    id: "c-1",
    tipo: "natural",
    nombre: "CARLOS",
    telefono: "939913861",
    numero_documento: null,
    direccion: "Jr. Comandante Chirinos 174",
    identificado: true,
    ubicacion_place_id: "p-1",
    ubicacion_lat: -6.48,
    ubicacion_lng: -76.36,
    ubicacion_plus_code: null,
    ubicacion_distrito: "Tarapoto",
  };

  assert.deepEqual(soloUbicacion(cliente), {
    ubicacion_place_id: "p-1",
    ubicacion_lat: -6.48,
    ubicacion_lng: -76.36,
    ubicacion_plus_code: null,
    ubicacion_distrito: "Tarapoto",
  });
});
