"use client";

import { useEffect, useRef } from "react";
import { toast } from "sonner";

import { apiDelivery, type Avisos } from "@/lib/delivery";

const INTERVALO_MS = 15_000;

/**
 * Beep corto sin archivo de audio: un oscilador de Web Audio. Mismo
 * criterio que "no hay push" (deuda ya declarada en
 * `docs/roadmap/deuda/modulo-delivery.md`) — esto es polling, y el sonido
 * es la única señal de que algo nuevo llegó sin tener la pantalla a la
 * vista. `resume()` recién en el primer toque: los navegadores no dejan
 * sonar audio antes de una interacción del usuario.
 */
function useBeep() {
  const ctxRef = useRef<AudioContext | null>(null);

  useEffect(() => {
    const activar = () => {
      if (!ctxRef.current) {
        try {
          ctxRef.current = new AudioContext();
        } catch {
          return;
        }
      }
      ctxRef.current.resume().catch(() => {});
    };
    window.addEventListener("pointerdown", activar, { once: true });
    return () => window.removeEventListener("pointerdown", activar);
  }, []);

  return () => {
    const ctx = ctxRef.current;
    if (!ctx) return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.3);
  };
}

function montoDe(valor: string | number | null): string {
  return valor === null ? "" : ` · Cobrar S/ ${Number(valor).toFixed(2)}`;
}

/**
 * Toast + beep en KDS y caja cuando delivery registra una entrega o
 * termina una ruta (ADR-101). Sondea `GET /delivery/avisos` con el
 * `desde` que trajo el sondeo anterior, así que nunca repite ni pierde un
 * aviso entre dos pasadas — y el primer sondeo, sin `desde`, no vuelca
 * nada viejo: el servidor le da su propio reloj como punto de partida.
 *
 * `soloRutas` es para el KDS: cocina no cobra, así que no le interesa el
 * aviso de "entrega registrada" — solo que un repartidor volvió.
 */
export function useAvisosReparto(
  sucursalId: string | undefined,
  opciones: { soloRutas?: boolean } = {},
): void {
  const soloRutas = opciones.soloRutas ?? false;
  const desdeRef = useRef<string | undefined>(undefined);
  const beep = useBeep();

  useEffect(() => {
    if (!sucursalId) return;
    let cancelado = false;

    const sondear = async () => {
      let avisos: Avisos;
      try {
        avisos = await apiDelivery.avisos(sucursalId, desdeRef.current);
      } catch {
        // Un sondeo perdido no interrumpe nada: el siguiente lo compensa.
        return;
      }
      if (cancelado) return;
      desdeRef.current = avisos.ahora;

      if (!soloRutas) {
        for (const e of avisos.entregas) {
          toast(`Pedido #${e.numero_orden ?? "—"} entregado${montoDe(e.monto_a_cobrar)}`);
          beep();
        }
      }
      for (const r of avisos.rutas_finalizadas) {
        toast(
          `${r.repartidor_nombre ?? "Un repartidor"} terminó su ruta ` +
            `(${r.entregadas} entregada(s), ${r.fallidas} fallida(s))`,
        );
        beep();
      }
    };

    sondear();
    const id = window.setInterval(sondear, INTERVALO_MS);
    return () => {
      cancelado = true;
      window.clearInterval(id);
    };
    // `beep` es una función nueva en cada render (cierra sobre `ctxRef`) y
    // no cambia el comportamiento del sondeo: no hace falta reabrir el
    // intervalo cuando cambia su identidad.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sucursalId, soloRutas]);
}
