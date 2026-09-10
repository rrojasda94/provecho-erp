"use client";

import { useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import { enlaceWhatsApp, type ParadaReparto } from "@/lib/delivery";

/**
 * Fallback manual del aviso al cliente (ADR-098): copiar el enlace de
 * seguimiento o abrirlo ya armado en `wa.me`. Vive siempre en la tarjeta —
 * con el aviso automático configurado es un refuerzo; sin él, es la única
 * vía.
 */
export default function AvisoParada({
  parada,
  whatsappHabilitado,
}: {
  parada: ParadaReparto;
  whatsappHabilitado: boolean;
}) {
  const [copiado, setCopiado] = useState(false);

  if (!parada.enlace_seguimiento) return null;

  const enlace = parada.enlace_seguimiento;
  const texto = `Tu pedido${parada.numero_orden ? ` #${parada.numero_orden}` : ""} va en camino: ${enlace}`;
  const waHref = enlaceWhatsApp(parada.cliente_telefono, texto);

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-gray">
      {!whatsappHabilitado ? <span>Sin aviso automático —</span> : null}
      <button
        type="button"
        className="rounded bg-cream px-2 py-0.5"
        onClick={async () => {
          await navigator.clipboard.writeText(enlace);
          setCopiado(true);
        }}
      >
        {copiado ? "Copiado" : "Copiar enlace"}
      </button>
      {waHref ? (
        <a
          href={waHref}
          target="_blank"
          rel="noreferrer"
          className={buttonVariants({ variant: "outline", size: "xs" })}
        >
          Enviar por WhatsApp
        </a>
      ) : null}
    </div>
  );
}
