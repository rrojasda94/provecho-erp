import type { Metadata } from "next";

import { apiFetch } from "@/lib/api";

export const metadata: Metadata = {
  title: "Nosotros",
  description: "La historia de Charlie's Pizzas, desde 2006 en Tarapoto.",
};

type Contenido = {
  contenido: {
    nosotros?: {
      titulo?: string;
      parrafos?: string[];
      hitos?: { anio: string; texto: string }[];
    };
  };
};

export default async function NosotrosPage() {
  const datos = await apiFetch<Contenido>("/api/v1/storefront/publico/contenido");
  const nosotros = datos?.contenido?.nosotros;

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-4 py-8">
      <h1 className="revelar font-display text-3xl uppercase text-negro">
        {nosotros?.titulo ?? "Nuestra historia"}
      </h1>

      <div className="revelar flex flex-col gap-4 text-humo">
        {(nosotros?.parrafos ?? []).map((p, i) => (
          <p key={i}>{p}</p>
        ))}
      </div>

      {nosotros?.hitos && nosotros.hitos.length > 0 && (
        <ol className="revelar flex flex-col gap-3 border-l-4 border-verde pl-4">
          {nosotros.hitos.map((h, i) => (
            <li key={i}>
              <span className="font-display text-verde">{h.anio}</span>
              <p className="text-sm text-humo">{h.texto}</p>
            </li>
          ))}
        </ol>
      )}

      <p className="revelar font-display text-xl uppercase text-verde">A tu manera</p>
    </div>
  );
}
