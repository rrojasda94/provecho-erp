import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { filtrosDe, queryDeFiltros } from "@/lib/filtros";
import { obtenerSesion } from "@/lib/sesion";

import {
  SolicitudesCliente,
  type OpcionAlmacen,
  type Solicitud,
} from "./solicitudes-cliente";

type Params = Promise<{
  almacen?: string;
  estado?: string;
  sucursal?: string;
  marca?: string;
}>;

type Almacen = { id: string; nombre: string; sucursal_id: string | null };
type Sucursal = { id: string; nombre: string; marca_id: string };
type Marca = { id: string; nombre: string };

/**
 * Requerimientos: lo que cada local le pide a su abastecedor.
 *
 * El filtro por sucursal y marca viaja en la URL y lo resuelve el servidor
 * (ADR-051): así el enlace se comparte y la página no trae de más para
 * después esconderlo en el navegador.
 */
export default async function SolicitudesPage({
  searchParams,
}: {
  searchParams: Params;
}) {
  const { token, usuario } = await obtenerSesion();
  const filtros = await searchParams;

  const query = queryDeFiltros(filtros, "almacen_solicitante_id");

  let solicitudes: Solicitud[];
  try {
    solicitudes = (
      await apiFetch<Pagina<Solicitud>>(
        `/api/v1/inventory/solicitudes?${query}`,
        { token },
      )
    ).items;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los requerimientos."
        : "No se pudieron cargar los requerimientos.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  // Igual que en Devoluciones: si falta el permiso de organización se ve la
  // tabla y el selector queda vacío, en vez de una pantalla en blanco por un
  // 403 de otra consulta.
  const [almacenes, sucursales, marcas] = await Promise.all([
    apiFetch<Almacen[]>("/api/v1/almacenes", { token }).catch(() => []),
    apiFetch<Sucursal[]>("/api/v1/sucursales", { token }).catch(() => []),
    apiFetch<Marca[]>("/api/v1/marcas", { token }).catch(() => []),
  ]);

  const nombreDeAlmacen = new Map(almacenes.map((a) => [a.id, a.nombre]));

  return (
    <SolicitudesCliente
      solicitudes={solicitudes}
      almacenes={almacenes.map(
        (a): OpcionAlmacen => ({ id: a.id, nombre: a.nombre }),
      )}
      sucursales={sucursales.map((s) => ({ id: s.id, nombre: s.nombre }))}
      marcas={marcas.map((m) => ({ id: m.id, nombre: m.nombre }))}
      nombreDeAlmacen={Object.fromEntries(nombreDeAlmacen)}
      filtros={filtrosDe(filtros)}
      permisos={usuario.permisos}
    />
  );
}
