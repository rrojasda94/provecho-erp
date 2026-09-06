"use client";

import { useRouter } from "next/navigation";

/** Los filtros viven en la URL: «las pistas sin trabajar de la campaña de
 * verano» es una dirección que se comparte con quien tiene que llamarlas. */
export function FiltroLeads({
  atribuido,
  campana,
  campanas,
}: {
  atribuido: string;
  campana: string;
  campanas: { id: string; nombre: string }[];
}) {
  const router = useRouter();
  const navegar = (cambios: Record<string, string>) => {
    const q = new URLSearchParams({ atribuido, campana, ...cambios });
    for (const [k, v] of [...q]) if (!v) q.delete(k);
    router.push(`/marketing/leads?${q}`);
  };

  return (
    <div className="flex flex-wrap items-end gap-4">
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Estado
        <select value={atribuido} onChange={(e) => navegar({ atribuido: e.target.value })}>
          <option value="">Todos</option>
          <option value="false">Sin trabajar</option>
          <option value="true">Convertidos</option>
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Campaña
        <select value={campana} onChange={(e) => navegar({ campana: e.target.value })}>
          <option value="">Todas</option>
          {campanas.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nombre}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
