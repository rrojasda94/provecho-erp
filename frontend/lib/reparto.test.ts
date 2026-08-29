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
    notaCocina: "",
    consumoMotivo: null,
    consumoAutorizacion: null,
    descuento: null,
    cupon: null,
    promociones: [],
    ...extra,
  } as Borrador;
}

test("el reparto suma al total del pedido", () => {
  assert.equal(totalBorrador(pedido({ costoEntrega: 5 })), 85);
});

test("sin cotizar todavía, el total es solo lo consumido", () => {
  assert.equal(totalBorrador(pedido()), 80);
});

test("la promoción baja el total y el descuento se toma sobre lo que queda", () => {
  // Mismo orden que el servidor (ADR-076): 80 de lista − 40 de promoción =
  // 40, y el 10 % firmado se toma sobre 40. Al revés, el supervisor estaría
  // regalando el doble de lo que aprobó.
  const conPromo = pedido({
    promociones: [{ nombre: "2x1", monto: 40 }],
    descuento: { modo: "porcentaje", valor: 10, motivo: "cortesia" },
  });
  assert.equal(totalBorrador(conPromo), 36);
});

test("un consumo de personal vale cero, reparto incluido", () => {
  const consumo = pedido({ costoEntrega: 5, consumoMotivo: "fin_semana" });
  assert.equal(totalBorrador(consumo), 0);
});
