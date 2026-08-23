import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { LotesCliente, type SaldoLote } from "./lotes-cliente";

type Params = Promise<{ lote?: string }>;

export default async function LotesPage({ searchParams }: { searchParams: Params }) {
  const { token } = await obtenerSesion();
  const { lote } = await searchParams;

  let saldos: SaldoLote[];
  try {
    saldos = await apiFetch<SaldoLote[]>("/api/v1/inventory/lotes", { token });
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los lotes."
        : "No se pudieron cargar los lotes.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return <LotesCliente saldos={saldos} resaltado={lote ?? null} />;
}
