import assert from "node:assert/strict";
import test from "node:test";

import {
  MAXIMO_EXTRAS_DE_PAGO,
  precioUnitario,
  recargoDeValores,
  validar,
  valorEnConflicto,
  type ExtraOpcion,
  type Opciones,
  type Seleccion,
} from "./opciones.ts";

const extra = (id: string, precio: string, sobre: Partial<ExtraOpcion> = {}): ExtraOpcion => ({
  id,
  nombre: `Extra ${id}`,
  precio,
  maximo: null,
  grupo_id: null,
  grupo_nombre: null,
  grupo_minimo: 0,
  grupo_maximo: null,
  ...sobre,
});

/** Pizza Mitad x Mitad: dos mitades (Hawaiana suma 3 en la primera), sin repetir sabor. */
const MITAD: Opciones = {
  extras: [extra("queso", "6.00", { maximo: 2 }), extra("tocino", "8.00"), extra("champi", "5.00")],
  atributos: [
    {
      id: "m1",
      nombre: "Mitad 1",
      display: "radio",
      valores: [
        { id: "h1", nombre: "Hawaiana", precio_extra: "3.00" },
        { id: "p1", nombre: "Peperoni", precio_extra: "0.00" },
      ],
    },
    {
      id: "m2",
      nombre: "Mitad 2",
      display: "radio",
      valores: [
        { id: "h2", nombre: "Hawaiana", precio_extra: "0.00" },
        { id: "p2", nombre: "Peperoni", precio_extra: "0.00" },
      ],
    },
  ],
  exclusiones: [
    ["h1", "h2"],
    ["p1", "p2"],
  ],
};

const sel = (valores: Seleccion["valores"], extras: Seleccion["extras"] = {}): Seleccion => ({
  valores,
  extras,
});

test("sin elegir las dos mitades no se puede agregar", () => {
  assert.equal(validar(MITAD, sel({})), "Elige Mitad 1");
  assert.equal(validar(MITAD, sel({ m1: "h1" })), "Elige Mitad 2");
  assert.equal(validar(MITAD, sel({ m1: "h1", m2: "p2" })), null);
});

test("el mismo sabor en las dos mitades no es una mitad y mitad", () => {
  assert.match(validar(MITAD, sel({ m1: "h1", m2: "h2" })) ?? "", /combinación/);
  assert.equal(valorEnConflicto(MITAD, sel({ m1: "h1" }), "h2"), true);
  assert.equal(valorEnConflicto(MITAD, sel({ m1: "h1" }), "p2"), false);
  // Cambiar de idea sobre el mismo valor no choca consigo mismo.
  assert.equal(valorEnConflicto(MITAD, sel({ m1: "h1" }), "h1"), false);
});

test("el precio suma el recargo de los sabores y los extras", () => {
  const s = sel({ m1: "h1", m2: "p2" }, { queso: 2, tocino: 1 });
  assert.equal(recargoDeValores(MITAD, s), 3);
  assert.equal(precioUnitario(40, MITAD, s), 40 + 3 + 2 * 6 + 8);
});

test("máximo 3 extras de pago y el tope de cada extra", () => {
  const v = { m1: "h1", m2: "p2" };
  assert.equal(validar(MITAD, sel(v, { queso: 2, tocino: 1 })), null);
  assert.equal(
    validar(MITAD, sel(v, { queso: 2, tocino: 1, champi: 1 })),
    `Máximo ${MAXIMO_EXTRAS_DE_PAGO} extras por producto`,
  );
  assert.match(validar(MITAD, sel(v, { queso: 3 })) ?? "", /admite hasta 2/);
});

test("un grupo obligatorio exige elegir y su sabor no cuenta para el tope", () => {
  const sabor = { grupo_id: "g", grupo_nombre: "Sabor", grupo_minimo: 1, grupo_maximo: 1 };
  const op: Opciones = {
    extras: [
      extra("a", "0.00", sabor),
      extra("b", "0.00", sabor),
      extra("queso", "6.00"),
      extra("tocino", "8.00"),
      extra("champi", "5.00"),
    ],
    atributos: [],
    exclusiones: [],
  };
  assert.equal(validar(op, sel({}, { queso: 1 })), "Elige Sabor");
  assert.match(validar(op, sel({}, { a: 1, b: 1 })) ?? "", /Sabor admite hasta 1/);
  assert.equal(validar(op, sel({}, { a: 1, queso: 1, tocino: 1, champi: 1 })), null);
});

test("un producto sin opciones se agrega tal cual", () => {
  const vacio: Opciones = { extras: [], atributos: [], exclusiones: [] };
  assert.equal(validar(vacio, sel({})), null);
  assert.equal(precioUnitario(29.9, vacio, sel({})), 29.9);
});
