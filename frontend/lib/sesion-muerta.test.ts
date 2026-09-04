/**
 * La regla que este archivo protege: un 401 del navegador se anuncia **una
 * vez** y corta el tráfico que venía atrás. El KDS refresca cada 3 s y el
 * PDV guarda su borrador cada 800 ms; sin la bandera, la primera sesión
 * vencida disparaba una andanada de 401 que nadie miraba, para siempre.
 * Corre con `npm test`.
 */

import assert from "node:assert/strict";
import test, { beforeEach } from "node:test";

import { ErrorApi } from "./cliente-api.ts";
import { estaMuerta, marcarMuerta, reiniciar, suscribir } from "./sesion-muerta.ts";

beforeEach(() => reiniciar());

test("arranca viva", () => {
  assert.equal(estaMuerta(), false);
});

test("avisa una sola vez, aunque lleguen veinte 401 seguidos", () => {
  let avisos = 0;
  suscribir(() => {
    avisos += 1;
  });
  for (let i = 0; i < 20; i += 1) marcarMuerta();
  assert.equal(avisos, 1);
  assert.equal(estaMuerta(), true);
});

test("quien se suscribe después de la muerte no recibe el aviso: lo pregunta", () => {
  marcarMuerta();
  let aviso = false;
  suscribir(() => {
    aviso = true;
  });
  assert.equal(aviso, false);
  // Por eso el componente consulta `estaMuerta()` al montar y no espera solo
  // la notificación: el PDV dispara su primer fetch en el mismo tick.
  assert.equal(estaMuerta(), true);
});

test("desuscribirse deja de recibir", () => {
  let avisos = 0;
  const cancelar = suscribir(() => {
    avisos += 1;
  });
  cancelar();
  marcarMuerta();
  assert.equal(avisos, 0);
});

test("el corte en seco lanza un 401 sin salir a la red", async () => {
  // `pedir` sale por `fetch`: si la bandera no cortara antes, esto reventaría
  // con un error de red en vez de con el 401. No hay servidor detrás.
  const { pedir } = await import("./cliente-api.ts");
  marcarMuerta();
  await assert.rejects(
    () => pedir("/kds/cola"),
    (e: unknown) => e instanceof ErrorApi && e.status === 401,
  );
});
