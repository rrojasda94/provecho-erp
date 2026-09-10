import Link from "next/link";

import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import {
  ESTADOS_ENTREGA,
  ETIQUETA_ESTADO_ENTREGA,
  type EntregaHistorial,
  type Repartidor,
} from "@/lib/delivery";
import { obtenerSesion } from "@/lib/sesion";

import EntregasCliente from "./entregas-cliente";

type Filtros = { estado: string; repartidor_id: string; desde: string; hasta: string; page: string };

function consulta(f: Filtros): URLSearchParams {
  const q = new URLSearchParams({ page: f.page, page_size: "20" });
  if (f.estado) q.set("estado", f.estado);
  if (f.repartidor_id) q.set("repartidor_id", f.repartidor_id);
  if (f.desde) q.set("desde", f.desde);
  if (f.hasta) q.set("hasta", f.hasta);
  return q;
}

function FiltrosForm({
  filtros,
  repartidores,
}: {
  filtros: Filtros;
  repartidores: Repartidor[];
}) {
  return (
    <form
      method="get"
      className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-card p-3 text-sm"
    >
      <label className="flex flex-col gap-1">
        <span className="text-gray">Estado</span>
        <select name="estado" defaultValue={filtros.estado} className="rounded border px-2 py-1.5">
          <option value="">Todos</option>
          {ESTADOS_ENTREGA.map((e) => (
            <option key={e} value={e}>
              {ETIQUETA_ESTADO_ENTREGA[e]}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-gray">Repartidor</span>
        <select
          name="repartidor_id"
          defaultValue={filtros.repartidor_id}
          className="rounded border px-2 py-1.5"
        >
          <option value="">Todos</option>
          {repartidores.map((r) => (
            <option key={r.id} value={r.id}>
              {r.nombre ?? r.id}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-gray">Desde</span>
        <input type="date" name="desde" defaultValue={filtros.desde} className="rounded border px-2 py-1.5" />
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-gray">Hasta</span>
        <input type="date" name="hasta" defaultValue={filtros.hasta} className="rounded border px-2 py-1.5" />
      </label>
      <button type="submit" className="rounded border border-border px-3 py-1.5">
        Filtrar
      </button>
    </form>
  );
}

function Paginador({ pagina, filtros }: { pagina: Pagina<EntregaHistorial>; filtros: Filtros }) {
  const paginas = Math.max(1, Math.ceil(pagina.total / pagina.page_size));
  const enlace = (n: number) => {
    const q = consulta({ ...filtros, page: String(n) });
    return `/delivery/entregas?${q}`;
  };
  return (
    <div className="flex items-center gap-4 text-sm">
      <span className="text-gray">
        {pagina.total} entregas · página {pagina.page} de {paginas}
      </span>
      {pagina.page > 1 ? <Link href={enlace(pagina.page - 1)}>← Anterior</Link> : null}
      {pagina.page < paginas ? <Link href={enlace(pagina.page + 1)}>Siguiente →</Link> : null}
    </div>
  );
}

export default async function EntregasPage({
  searchParams,
}: {
  searchParams: Promise<{
    estado?: string;
    repartidor_id?: string;
    desde?: string;
    hasta?: string;
    page?: string;
  }>;
}) {
  const { token } = await obtenerSesion();
  const parametros = await searchParams;
  const filtros: Filtros = {
    estado: parametros.estado ?? "",
    repartidor_id: parametros.repartidor_id ?? "",
    desde: parametros.desde ?? "",
    hasta: parametros.hasta ?? "",
    page: parametros.page ?? "1",
  };

  let pagina: Pagina<EntregaHistorial>;
  try {
    pagina = await apiFetch<Pagina<EntregaHistorial>>(
      `/api/v1/delivery/entregas?${consulta(filtros)}`,
      { token },
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver el historial de entregas."
        : "No se pudo cargar el historial de entregas.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  const repartidores = await apiFetch<Repartidor[]>("/api/v1/delivery/repartidores", {
    token,
  }).catch(() => []);

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-heading text-xl text-dark">Historial de entregas</h1>
      <FiltrosForm filtros={filtros} repartidores={repartidores} />
      <EntregasCliente items={pagina.items} />
      <Paginador pagina={pagina} filtros={filtros} />
    </div>
  );
}
