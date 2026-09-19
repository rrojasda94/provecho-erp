"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

import { simularPago } from "./actions";

/**
 * Pantalla de pago del pedido (ADR-105). Mientras el pedido espera el
 * webhook de la pasarela, vuelve a leer su estado cada pocos segundos: cuando
 * el pago se aprueba la página de servidor redirige a la confirmación, y si se
 * rechaza muestra el motivo.
 *
 * Sin credenciales reales de Izipay (`simulado`) ofrece aprobar o rechazar a
 * mano, para probar todo el circuito. Con credenciales, acá va el formulario
 * de pago de Izipay — solo cambia este bloque.
 */
export function PagoCliente({
  pedidoId,
  token,
  estado,
  simulado,
  total,
  motivo,
}: {
  pedidoId: string;
  token: string;
  estado: "pendiente" | "confirmado" | "fallido";
  simulado: boolean;
  total: string;
  motivo: string | null;
}) {
  const router = useRouter();
  const [enviando, iniciar] = useTransition();
  const [error, setError] = useState("");

  useEffect(() => {
    if (estado !== "pendiente") return;
    const reloj = setInterval(() => router.refresh(), 3000);
    return () => clearInterval(reloj);
  }, [estado, router]);

  function responder(resultado: "aprobado" | "rechazado") {
    setError("");
    iniciar(async () => {
      const r = await simularPago(pedidoId, token, resultado);
      if (!r.ok) setError(r.error ?? "No se pudo registrar el pago.");
      router.refresh();
    });
  }

  if (estado === "fallido") {
    return (
      <div className="mx-auto max-w-lg px-4 py-16 text-center">
        <h1 className="font-display text-2xl uppercase text-rojo">No se pudo completar el pago</h1>
        <p className="mt-2 text-humo">{motivo ?? "Intenta de nuevo."}</p>
        <Link href="/checkout" className="mt-4 inline-block font-bold text-verde underline">
          Intentar de nuevo
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-lg flex-col gap-4 px-4 py-16 text-center">
      <h1 className="font-display text-2xl uppercase text-negro">Paga tu pedido</h1>
      <p className="font-display text-3xl text-verde">S/ {total}</p>

      {simulado ? (
        <div className="flex flex-col gap-3 rounded-lg border-2 border-negro bg-white p-4">
          <p className="text-sm text-humo">
            <strong>Pago de prueba.</strong> Todavía no hay una cuenta de comercio de Izipay
            conectada: elige cómo termina el pago para probar el pedido.
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={enviando}
              onClick={() => responder("aprobado")}
              className="sombra-dura flex-1 rounded bg-verde px-4 py-3 font-bold uppercase text-negro disabled:opacity-50"
            >
              Aprobar pago
            </button>
            <button
              type="button"
              disabled={enviando}
              onClick={() => responder("rechazado")}
              className="flex-1 rounded border-2 border-negro px-4 py-3 font-bold uppercase disabled:opacity-50"
            >
              Rechazar pago
            </button>
          </div>
          {error && <p className="text-sm text-rojo">{error}</p>}
        </div>
      ) : (
        <p className="text-humo">
          Estamos esperando la confirmación de tu pago con Izipay. No cierres esta página.
        </p>
      )}
    </div>
  );
}
