"use client";

import { useState } from "react";

import { HojaImpresion, useImpresion } from "@/components/impresion/hoja";
import {
  TicketDeComprobante,
  TicketDeTexto,
} from "@/components/impresion/ticket-comprobante";
import type {
  TicketComprobante,
  TicketTexto,
} from "@/components/impresion/tipos";
import { api, type Venta } from "@/lib/pdv";

/**
 * Lo que la caja manda al rollo de 80 mm (ADR-066): el comprobante de una
 * cuenta cobrada y la comanda de una cuenta abierta.
 *
 * Sale de `pdv-cliente.tsx` porque ahí ya viven quince responsabilidades y
 * la impresión no comparte estado con ninguna: solo necesita avisar y
 * bloquear el botón mientras pide los datos.
 *
 * Un documento a la vez. Tener dos montados dejaría salir el anterior si el
 * `print()` llega antes que la respuesta del nuevo, y en una impresora eso
 * no se deshace.
 */
export function useImpresionPdv({
  setOcupado,
  notificar,
  mensajeDe,
}: {
  setOcupado: (v: boolean) => void;
  notificar: (texto: string) => void;
  mensajeDe: (e: unknown, porDefecto: string) => string;
}) {
  const [documento, setDocumento] = useState<
    | { clase: "comprobante"; datos: TicketComprobante }
    | { clase: "texto"; datos: TicketTexto }
    | null
  >(null);
  const { imprimir } = useImpresion();

  const preparar = async (cargar: () => Promise<void>, fallo: string) => {
    setOcupado(true);
    try {
      await cargar();
      imprimir();
    } catch (e) {
      notificar(mensajeDe(e, fallo));
    } finally {
      setOcupado(false);
    }
  };

  /** Va en dos pasos —el comprobante de la venta y después su ticket—
   * porque el id del comprobante no viaja en la fila de la venta: una venta
   * dividida tiene uno por cuenta (RN-COM-018). */
  const imprimirComprobante = (venta: Venta) =>
    preparar(async () => {
      const comprobante = await api.comprobante(venta.id);
      setDocumento({
        clase: "comprobante",
        datos: await api.ticketComprobante(comprobante.id),
      });
    }, "No se pudo preparar el comprobante");

  /** Mismo endpoint que usa cocina, así que suma al contador de
   * reimpresiones y queda auditada. */
  const imprimirComanda = (venta: Venta) =>
    preparar(async () => {
      setDocumento({ clase: "texto", datos: await api.comanda(venta.id) });
    }, "No se pudo imprimir la comanda");

  /* La hoja se cuelga de `<body>`: al imprimir se esconde todo lo demás, el
     diálogo modal incluido. Por eso viaja como nodo listo y no como algo que
     la pantalla tenga que colocar en el lugar correcto. */
  const hoja = documento ? (
    <HojaImpresion>
      {documento.clase === "comprobante" ? (
        <TicketDeComprobante ticket={documento.datos} />
      ) : (
        <TicketDeTexto ticket={documento.datos} />
      )}
    </HojaImpresion>
  ) : null;

  return { imprimirComprobante, imprimirComanda, hoja };
}
