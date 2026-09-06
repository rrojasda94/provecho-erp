import Link from "next/link";

import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { Cambio } from "./cambio";
import { Filtros } from "./filtros";

type Registro = {
  id: string;
  ts: string;
  usuario_id: string | null;
  entidad: string;
  entidad_id: string | null;
  accion: string;
  datos_antes: Record<string, unknown> | null;
  datos_despues: Record<string, unknown> | null;
  sucursal_id: string | null;
};

/** Las tablas que hoy dejan rastro. Se ofrecen como lista porque escribir
 * «ventas» en vez de «venta» devuelve cero filas y se lee como que no pasó
 * nada — el peor resultado posible en una pantalla de auditoría. */
const ENTIDADES = [
  "venta",
  "comprobante",
  "orden_compra",
  "movimiento_dinero",
  "asiento",
  "ajuste",
  "transferencia",
  "trabajador",
  "usuario",
  "empresa",
  "persona",
  "parametro_empresa",
];

/** Los filtros como los espera la API. `desde`/`hasta` viajan con hora: la
 * API recibe `datetime`, y sin ella el rango de un día se corta a la
 * medianoche del «hasta» y deja fuera todo lo del día. */
function consulta(f: {
  entidad: string;
  accion: string;
  desde: string;
  hasta: string;
  page: string;
}): URLSearchParams {
  const query = new URLSearchParams({ page: f.page, page_size: "50" });
  if (f.entidad) query.set("entidad", f.entidad);
  if (f.accion) query.set("accion", f.accion);
  if (f.desde) query.set("desde", `${f.desde}T00:00:00`);
  if (f.hasta) query.set("hasta", `${f.hasta}T23:59:59`);
  return query;
}

/** Id → username, o vacío. Los nombres son un lujo, no un requisito: un
 * contador tiene `auditoria.leer` y no `users.gestionar`, así que si el
 * listado responde 403 se muestra el id y la pantalla sigue sirviendo. */
async function nombresDeUsuario(token: string): Promise<Map<string, string>> {
  try {
    const usuarios = await apiFetch<Pagina<{ id: string; username: string }>>(
      "/api/v1/users?page_size=200",
      { token },
    );
    return new Map(usuarios.items.map((u) => [u.id, u.username] as const));
  } catch {
    return new Map();
  }
}

function TablaRastro({
  registros,
  nombres,
}: {
  registros: Registro[];
  nombres: Map<string, string>;
}) {
  if (registros.length === 0) {
    return (
      <p className="rounded bg-cream px-3 py-2 text-sm text-gray">
        No hay cambios registrados con esos filtros.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[52rem] border-collapse text-sm">
        <thead>
          <tr className="border-b border-gray/30 text-left text-xs uppercase text-gray">
            <th className="py-2 pr-4 font-semibold">Cuándo</th>
            <th className="py-2 pr-4 font-semibold">Quién</th>
            <th className="py-2 pr-4 font-semibold">Qué</th>
            <th className="py-2 pr-4 font-semibold">Acción</th>
            <th className="py-2 font-semibold">Cambio</th>
          </tr>
        </thead>
        <tbody>
          {registros.map((r) => (
            <tr key={r.id} className="border-b border-gray/15 align-top">
              <td className="py-2 pr-4 cifra whitespace-nowrap">
                {r.ts.slice(0, 19).replace("T", " ")}
              </td>
              <td className="py-2 pr-4">
                <Quien usuarioId={r.usuario_id} nombres={nombres} />
              </td>
              <td className="py-2 pr-4">
                <span className="font-semibold text-dark">{r.entidad}</span>
                {r.entidad_id && (
                  <span className="ml-1 cifra text-xs text-gray">
                    {r.entidad_id.slice(0, 8)}
                  </span>
                )}
              </td>
              <td className="py-2 pr-4">{r.accion}</td>
              <td className="py-2">
                <Cambio antes={r.datos_antes} despues={r.datos_despues} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Sin usuario es el propio sistema: un barrido programado, un listener. No
 * es un dato faltante y no se dibuja como tal. */
function Quien({
  usuarioId,
  nombres,
}: {
  usuarioId: string | null;
  nombres: Map<string, string>;
}) {
  if (!usuarioId) return <span className="text-gray">el sistema</span>;
  const nombre = nombres.get(usuarioId);
  if (nombre) return <>{nombre}</>;
  return <span className="cifra text-xs">{usuarioId.slice(0, 8)}</span>;
}

function Paginador({
  pagina,
  filtros,
}: {
  pagina: Pagina<Registro>;
  filtros: { entidad: string; accion: string; desde: string; hasta: string };
}) {
  const paginas = Math.max(1, Math.ceil(pagina.total / pagina.page_size));
  const enlace = (n: number) => {
    const q = new URLSearchParams({ ...filtros, page: String(n) });
    for (const [k, v] of [...q]) if (!v) q.delete(k);
    return `/auditoria?${q}`;
  };
  return (
    <div className="flex items-center gap-4 text-sm">
      <span className="text-gray">
        {pagina.total} cambios · página {pagina.page} de {paginas}
      </span>
      {pagina.page > 1 && (
        <Link href={enlace(pagina.page - 1)} className="font-semibold text-primary hover:underline">
          ← Anterior
        </Link>
      )}
      {pagina.page < paginas && (
        <Link href={enlace(pagina.page + 1)} className="font-semibold text-primary hover:underline">
          Siguiente →
        </Link>
      )}
    </div>
  );
}

/**
 * El rastro de cambios: quién tocó qué, cuándo y con qué valor anterior.
 *
 * `GET /api/v1/auditoria` existía con sus filtros y su alcance por tenant, y
 * **no lo llamaba ninguna pantalla**: el `audit_log` que el ERP viene
 * escribiendo desde ADR-031 solo se podía leer con una consulta a la base.
 * Auditar era pedirle a alguien que contara qué hizo.
 */
export default async function AuditoriaPage({
  searchParams,
}: {
  searchParams: Promise<{
    entidad?: string;
    accion?: string;
    desde?: string;
    hasta?: string;
    page?: string;
  }>;
}) {
  const { token } = await obtenerSesion();
  const { entidad = "", accion = "", desde = "", hasta = "", page = "1" } = await searchParams;

  let pagina: Pagina<Registro>;
  try {
    pagina = await apiFetch<Pagina<Registro>>(
      `/api/v1/auditoria?${consulta({ entidad, accion, desde, hasta, page })}`,
      { token },
    );
  } catch (e) {
    return (
      <p className="text-secondary">
        {e instanceof ApiError && e.status === 403
          ? "Tu usuario no tiene permiso para leer el rastro de cambios."
          : "No se pudo cargar el rastro de cambios."}
      </p>
    );
  }

  const nombres = await nombresDeUsuario(token);

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-heading text-xl text-dark">Auditoría</h1>
      <p className="text-sm text-gray">
        Quién tocó qué, cuándo y con qué valor anterior. Solo se lee: el rastro
        lo escribe el caso de uso que hace el cambio, nunca el cliente — un
        endpoint de escritura convertiría la auditoría en algo que el auditado
        puede dictar.
      </p>

      <Filtros
        entidad={entidad}
        accion={accion}
        desde={desde}
        hasta={hasta}
        entidades={ENTIDADES}
      />

      <TablaRastro registros={pagina.items} nombres={nombres} />

      <Paginador pagina={pagina} filtros={{ entidad, accion, desde, hasta }} />
    </div>
  );
}
