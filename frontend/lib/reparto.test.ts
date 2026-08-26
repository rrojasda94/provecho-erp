/**
 * Único check de la aritmética del reparto en el ticket del PDV
 * (RN-COM-041). Es plata en pantalla: si el total que el cajero le dice al
 * cliente no incluye el flete, el cobro y el ticket cuentan historias
 * distintas. El monto que manda es el que recalcula el servidor
 * (`total_a_cobrar`, con sus propias pruebas) — esto verifica que la vista
 * diga lo mismo.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { totalBorrador, type Borrador } from "../app/pdv/tipos.ts";

function pedido(extra: Partial<Borrador> = {}): Borrador {
  return {
    id: "b1",
    tipo: "delivery",
    mesaId: null,
    mesaNumero: null,
    comensales: null,
    direccion: "Jr. Lima 200",
    costoEntrega: null,
    ubicacion: null,
    cliente: null,
    lineas: [
      {
        id: "l1",
        productoId: "p1",
        nombre: "Pizza",
        precio: 40,
        cantidad: 2,
        nota: "",
        extras: [],
        restas: [],
        grupoCobro: 1,
      },
    ],
    ventaId: null,
    numeroOrden: null,
    hora: "12:00",
    consumoMotivo: null,
    consumoAutorizacion: null,
    ...extra,
  } as Borrador;
}

test("el reparto suma al total del pedido", () => {
  assert.equal(totalBorrador(pedido({ costoEntrega: 5 })), 85);
});

test("sin cotizar todavía, el total es solo lo consumido", () => {
  assert.equal(totalBorrador(pedido()), 80);
});

test("un consumo de personal vale cero, reparto incluido", () => {
  const consumo = pedido({ costoEntrega: 5, consumoMotivo: "fin_semana" });
  assert.equal(totalBorrador(consumo), 0);
});
