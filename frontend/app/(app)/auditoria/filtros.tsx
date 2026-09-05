"use client";

import { useRouter } from "next/navigation";

/**
 * Qué se busca en el rastro. Vive en la URL, no en estado del cliente: «los
 * cambios de venta del martes» es una dirección que se pega en un correo
 * cuando se está reclamando algo, que es justo cuando se mira esta pantalla.
 */
export function Filtros({
  entidad,
  accion,
  desde,
  hasta,
  entidades,
}: {
  entidad: string;
  accion: string;
  desde: string;
  hasta: string;
  /** Las tablas que ya tienen rastro. Se ofrecen las que existen en vez de
   * un campo libre: escribir «ventas» en vez de «venta» devuelve cero filas
   * y parece que no pasó nada. */
  entidades: string[];
}) {
  const router = useRouter();

  const navegar = (cambios: Record<string, string>) => {
    const query = new URLSearchParams({ entidad, accion, desde, hasta, ...cambios });
    for (const [k, v] of [...query]) if (!v) query.delete(k);
    router.push(`/auditoria?${query}`);
  };

  return (
    <div className="flex flex-wrap items-end gap-4">
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Qué se tocó
        <select value={entidad} onChange={(e) => navegar({ entidad: e.target.value })}>
          <option value="">Todo</option>
          {entidades.map((e) => (
            <option key={e} value={e}>
              {e}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Acción
        <input
          value={accion}
          onChange={(e) => navegar({ accion: e.target.value })}
          placeholder="crear, anular, autorizar..."
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Desde
        <input type="date" value={desde} onChange={(e) => navegar({ desde: e.target.value })} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Hasta
        <input type="date" value={hasta} onChange={(e) => navegar({ hasta: e.target.value })} />
      </label>
    </div>
  );
}
