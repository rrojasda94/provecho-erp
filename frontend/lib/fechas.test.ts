/**
 * La regla que este archivo protege: el mismo instante se lee igual corra
 * donde corra. Falla si alguien quita el `timeZone` explícito y deja que la
 * zona la ponga el proceso. Corre con `npm test`.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { fecha, fechaHora } from "./fechas.ts";

// Las 21:00 del 30 en Lima. En UTC ya es el 31: es exactamente el rango
// horario en el que el ERP se usa y en el que el día se corría.
const NOCHE = "2026-08-31T02:00:00Z";

/** Corre `fn` con el reloj del proceso en otra zona y lo deja como estaba. */
function conZona<T>(tz: string, fn: () => T): T {
  const previa = process.env.TZ;
  process.env.TZ = tz;
  try {
    return fn();
  } finally {
    if (previa === undefined) delete process.env.TZ;
    else process.env.TZ = previa;
  }
}

test("un instante de la noche peruana no se corre al día siguiente", () => {
  // Formato es-PE: d/m/aaaa. Lo que importa es el 30, no el 31.
  assert.ok(fecha(NOCHE).startsWith("30/"), fecha(NOCHE));
  assert.ok(fechaHora(NOCHE).startsWith("30/"), fechaHora(NOCHE));
});

test("el resultado no depende de la zona del proceso", () => {
  const enUtc = conZona("UTC", () => fechaHora(NOCHE));
  const enTokio = conZona("Asia/Tokyo", () => fechaHora(NOCHE));
  const enLima = conZona("America/Lima", () => fechaHora(NOCHE));
  assert.equal(enUtc, enTokio);
  assert.equal(enUtc, enLima);
});

test("un instante con offset explícito se convierte, no se toma literal", () => {
  // Mediodía en Madrid (UTC+2) son las 05:00 en Lima, del mismo día.
  assert.ok(fechaHora("2026-08-30T12:00:00+02:00").startsWith("30/"));
  assert.ok(fecha("2026-08-30T00:30:00+02:00").startsWith("29/"));
});
