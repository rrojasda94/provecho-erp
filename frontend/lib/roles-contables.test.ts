import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

import { CLAVES_ROL } from "./roles-contables.ts";

/**
 * Que el formulario de categorías ofrezca exactamente los roles que la API
 * acepta.
 *
 * `AsientoContableConfig` lleva `additionalProperties: false` (el
 * `extra="forbid"` del esquema Pydantic), así que un rol de más acá es un 422
 * al guardar y uno de menos es una cuenta que no se puede configurar por
 * pantalla. Se compara contra el contrato exportado por el mismo motivo que
 * el resto de `contrato.test.ts`: es el eslabón que `tsc` no puede ver.
 */
test("los roles del formulario son los del contrato", () => {
  const contrato = JSON.parse(
    readFileSync(
      path.join(import.meta.dirname, "..", "..", "docs", "architecture", "openapi.json"),
      "utf8",
    ),
  );
  const delContrato = Object.keys(
    contrato.components.schemas.AsientoContableConfig.properties,
  );
  assert.deepEqual([...CLAVES_ROL].sort(), [...delContrato].sort());
});

test("el esquema no admite roles inventados", () => {
  const contrato = JSON.parse(
    readFileSync(
      path.join(import.meta.dirname, "..", "..", "docs", "architecture", "openapi.json"),
      "utf8",
    ),
  );
  // Es lo que impide que un rol mal escrito quede guardado sin hacer nada: el
  // asiento lo ignoraría en silencio y el error aparecería cerrando el mes.
  assert.equal(
    contrato.components.schemas.AsientoContableConfig.additionalProperties,
    false,
  );
});
