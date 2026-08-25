import assert from "node:assert/strict";
import { test } from "node:test";

// Con extensión: `node --test` resuelve como ESM y no tiene el resolutor
// del bundler (el resto del frontend importa sin extensión, vía Next/tsc).
import {
  opcionesOfrecidas,
  ptavExcluidos,
  queFalta,
  recargoDe,
} from "./opciones-pdv.ts";
import type { AtributoDeCarta, ItemDeCarta, VarianteDeCarta } from "./pdv.ts";

/**
 * Las reglas que deciden si una línea del PDV se puede guardar.
 *
 * Existen como prueba porque el bug que las motivó no era visible desde el
 * backend: la carta no traía atributos, el configurador no dibujaba nada y
 * `queFalta` no exigía nada, así que «Guardar» quedaba habilitado y la pizza
 * se cobraba sin sabores. Todo el camino de servidor estaba en verde.
 */

const MITAD_1: AtributoDeCarta = {
  atributo_id: "a1",
  nombre: "Mitad 1",
  display: "radio",
  orden: 0,
  valores: [
    { id: "v-ame-1", nombre: "Americana", precio_extra: "0" },
    { id: "v-haw-1", nombre: "Hawaiana", precio_extra: "0" },
  ],
};

const MITAD_2: AtributoDeCarta = {
  atributo_id: "a2",
  nombre: "Mitad 2",
  display: "radio",
  orden: 1,
  valores: [
    { id: "v-ame-2", nombre: "Americana", precio_extra: "0" },
    { id: "v-haw-2", nombre: "Hawaiana", precio_extra: "2.50" },
  ],
};

/** Misma forma que el catálogo real: los atributos cuelgan de la variante
 * («Pizza MitadxMitad Familiar»), no del padre. */
function carta(): ItemDeCarta {
  const familiar: VarianteDeCarta = {
    producto_comercial_id: "p-familiar",
    nombre: "Pizza MitadxMitad Familiar",
    precio_unitario: "48.00",
    orden: 0,
    extras: [],
    atributos: [MITAD_1, MITAD_2],
    exclusiones: [["v-ame-1", "v-ame-2"], ["v-haw-1", "v-haw-2"]],
  };
  return {
    producto_comercial_id: "p-padre",
    id_interno: "V001",
    nombre: "Pizza MitadxMitad",
    categoria_id: null,
    categoria_nombre: null,
    precio_unitario: "48.00",
    variantes: [familiar],
    extras: [],
    atributos: [],
    exclusiones: [],
  };
}

test("sin elegir presentación no se ofrece nada", () => {
  // Lo que se prepara todavía no se sabe, así que ofrecer los del padre
  // armaría una línea que el servidor rechaza al enviar el pedido.
  const ofrecido = opcionesOfrecidas(carta(), undefined);
  assert.deepEqual(ofrecido.atributos, []);
  assert.deepEqual(ofrecido.exclusiones, []);
});

test("elegida la presentación, salen sus atributos", () => {
  const item = carta();
  const ofrecido = opcionesOfrecidas(item, item.variantes[0]);
  assert.deepEqual(
    ofrecido.atributos.map((a) => a.nombre),
    ["Mitad 1", "Mitad 2"],
  );
});

test("falta elegir el atributo bloquea guardar", () => {
  const item = carta();
  const variante = item.variantes[0];

  assert.equal(
    queFalta(item.variantes, variante, [], {}, variante.atributos, {}),
    "Elige Mitad 1",
  );
  assert.equal(
    queFalta(item.variantes, variante, [], {}, variante.atributos, {
      a1: "v-ame-1",
    }),
    "Elige Mitad 2",
  );
  assert.equal(
    queFalta(item.variantes, variante, [], {}, variante.atributos, {
      a1: "v-ame-1",
      a2: "v-haw-2",
    }),
    null,
  );
});

test("la exclusión apaga el mismo sabor en la otra mitad", () => {
  const exclusiones: [string, string][] = [["v-ame-1", "v-ame-2"]];

  const apagados = ptavExcluidos(exclusiones, { a1: "v-ame-1" });

  assert.ok(apagados.has("v-ame-2"), "la otra mitad no puede repetir sabor");
  assert.ok(!apagados.has("v-ame-1"), "el elegido no se apaga a sí mismo");
});

test("la exclusión vale también en el sentido inverso", () => {
  // La fila se guarda una sola vez: mirar una sola punta dejaría habilitada
  // la mitad de las pastillas que no van.
  const exclusiones: [string, string][] = [["v-ame-1", "v-ame-2"]];

  const apagados = ptavExcluidos(exclusiones, { a2: "v-ame-2" });

  assert.ok(apagados.has("v-ame-1"));
});

test("el recargo del valor elegido se suma", () => {
  assert.equal(recargoDe([MITAD_1, MITAD_2], { a1: "v-ame-1", a2: "v-haw-2" }), 2.5);
  assert.equal(recargoDe([MITAD_1, MITAD_2], { a1: "v-ame-1", a2: "v-ame-2" }), 0);
  assert.equal(recargoDe([MITAD_1, MITAD_2], {}), 0);
});

test("un producto sin atributos se sigue vendiendo igual", () => {
  // El grueso de la carta no tiene atributos: la regla nueva no puede
  // pedirle nada a una gaseosa.
  const gaseosa: ItemDeCarta = {
    producto_comercial_id: "p-gaseosa",
    id_interno: "B001",
    nombre: "Gaseosa",
    categoria_id: null,
    categoria_nombre: null,
    precio_unitario: "5.00",
    variantes: [],
    extras: [],
    atributos: [],
    exclusiones: [],
  };

  const ofrecido = opcionesOfrecidas(gaseosa, undefined);

  assert.deepEqual(ofrecido.atributos, []);
  assert.equal(queFalta([], undefined, [], {}, ofrecido.atributos, {}), null);
});
