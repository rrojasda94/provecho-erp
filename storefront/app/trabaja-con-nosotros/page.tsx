import type { Metadata } from "next";

import { apiFetch } from "@/lib/api";

export const metadata: Metadata = {
  title: "Trabaja con nosotros",
  description: "Vacantes abiertas en Charlie's Pizzas.",
};

type Contenido = { contenido: { trabaja?: { titulo?: string; cuerpo?: string } } };
type Convocatoria = {
  token: string;
  puesto: string;
  sucursal_nombre: string | null;
  vacantes: number;
  jornada_horas_semana: string | null;
  fecha_limite: string | null;
  url_postular: string;
};

export default async function TrabajaPage() {
  const [datos, convocatorias] = await Promise.all([
    apiFetch<Contenido>("/api/v1/storefront/publico/contenido"),
    apiFetch<Convocatoria[]>("/api/v1/storefront/publico/convocatorias"),
  ]);
  const trabaja = datos?.contenido?.trabaja;

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-4 py-8">
      <h1 className="font-display text-3xl uppercase text-negro">
        {trabaja?.titulo ?? "Trabaja con nosotros"}
      </h1>
      {trabaja?.cuerpo && <p className="text-humo">{trabaja.cuerpo}</p>}

      <div className="flex flex-col gap-3">
        {(convocatorias ?? []).map((c) => (
          <a
            key={c.token}
            href={c.url_postular}
            target="_blank"
            rel="noreferrer"
            className="sombra-dura flex items-center justify-between rounded-lg border-2 border-negro bg-white p-4"
          >
            <div>
              <h2 className="font-bold text-negro">{c.puesto}</h2>
              <p className="text-xs text-humo">
                {c.sucursal_nombre ?? "Cualquier local"} · {c.vacantes}{" "}
                {c.vacantes === 1 ? "vacante" : "vacantes"}
                {c.jornada_horas_semana && ` · ${c.jornada_horas_semana} h/semana`}
              </p>
            </div>
            <span className="rounded bg-verde px-3 py-1 text-xs font-bold uppercase text-negro">
              Postular
            </span>
          </a>
        ))}
        {(!convocatorias || convocatorias.length === 0) && (
          <p className="text-sm text-humo">
            No hay vacantes abiertas en este momento. Vuelve a mirar pronto.
          </p>
        )}
      </div>
    </div>
  );
}
