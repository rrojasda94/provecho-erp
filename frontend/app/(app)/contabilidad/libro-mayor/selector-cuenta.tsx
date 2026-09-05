"use client";

import { useRouter } from "next/navigation";
import { useMemo } from "react";

import { Combobox } from "@/components/ui/combobox";

import type { Cuenta } from "../asientos-cliente";

/**
 * Qué cuenta y qué rango. Los tres viven en la URL y no en estado del
 * cliente: el mayor de una cuenta en un periodo es una dirección que se
 * comparte y se recarga — mismo criterio que la jornada de ventas.
 */
export function SelectorCuenta({
  cuentas,
  cuenta,
  desde,
  hasta,
}: {
  cuentas: Cuenta[];
  cuenta: string;
  desde: string;
  hasta: string;
}) {
  const router = useRouter();

  const navegar = (cambios: Record<string, string>) => {
    const query = new URLSearchParams({ cuenta, desde, hasta, ...cambios });
    for (const [k, v] of [...query]) if (!v) query.delete(k);
    router.push(`/contabilidad/libro-mayor?${query}`);
  };

  // Solo las activas y una sola vez: el PCGE son ~424 cuentas y rearmar la
  // lista en cada tecla del buscador se nota.
  const opciones = useMemo(
    () =>
      cuentas
        .filter((c) => c.activa)
        .map((c) => ({ valor: c.id, etiqueta: `${c.codigo} · ${c.nombre}` })),
    [cuentas],
  );

  return (
    <div className="flex flex-wrap items-end gap-4">
      <label className="flex min-w-64 flex-col gap-1 text-sm font-semibold">
        Cuenta
        <Combobox
          name="cuenta"
          etiqueta="Cuenta"
          marcador="Elegir cuenta..."
          value={cuenta}
          alCambiar={(v) => navegar({ cuenta: v ?? "" })}
          opciones={opciones}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Desde
        <input
          type="date"
          value={desde}
          onChange={(e) => navegar({ desde: e.target.value })}
        />
        <span className="text-xs font-normal text-gray">Vacío = desde el principio</span>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Hasta
        <input
          type="date"
          value={hasta}
          onChange={(e) => navegar({ hasta: e.target.value })}
        />
      </label>
    </div>
  );
}
