import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { LotesCliente, type SaldoLote } from "./lotes-cliente";

type Params = Promise<{ lote?: string }>;

/** El mismo tope que el default de la API. Explícito acá para poder saber si
 * la lista llegó al techo: sin pedirlo, la pantalla no puede distinguir
 * "estos son todos" de "estos son los primeros 500". */
const TOPE = 500;

export default async function LotesPage({ searchParams }: { searchParams: Params }) {
  const { token } = await obtenerSesion();
  const { lote } = await searchParams;

  let saldos: SaldoLote[];
  try {
    saldos = await apiFetch<SaldoLote[]>(
      `/api/v1/inventory/lotes?limite=${TOPE}`,
      { token },
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los lotes."
        : "No se pudieron cargar los lotes.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return (
    <LotesCliente saldos={saldos} resaltado={lote ?? null} enElTope={saldos.length >= TOPE} />
  );
}
