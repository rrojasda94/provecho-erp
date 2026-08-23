import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { filtrosDe, queryDeFiltros } from "@/lib/filtros";
import { obtenerSesion } from "@/lib/sesion";

import { ConteosCliente, type Conteo, type ProgramaConteo } from "./conteos-cliente";

type Params = Promise<{
  almacen?: string;
  estado?: string;
  sucursal?: string;
  marca?: string;
}>;

type Almacen = { id: string; nombre: string };
type Sucursal = { id: string; nombre: string };
type Marca = { id: string; nombre: string };
type Categoria = { id: string; nombre: string; frecuencia_conteo: string | null };

/**
 * Conteos: la toma de inventario del almacén (ADR-019).
 *
 * Junto al listado va el calendario derivado (`/conteos/programa`), que es lo
 * que dice **qué toca contar hoy**: sin él la pantalla sería una lista de lo
 * ya hecho, que no ayuda a nadie a empezar.
 */
export default async function ConteosPage({
  searchParams,
}: {
  searchParams: Params;
}) {
  const { token, usuario } = await obtenerSesion();
  const filtros = await searchParams;

  const query = queryDeFiltros(filtros);

  let conteos: Conteo[];
  try {
    conteos = (
      await apiFetch<Pagina<Conteo>>(`/api/v1/inventory/conteos?${query}`, { token })
    ).items;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los conteos."
        : "No se pudieron cargar los conteos.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  const [almacenes, sucursales, marcas, categorias, programa] = await Promise.all([
    apiFetch<Almacen[]>("/api/v1/almacenes", { token }).catch(() => []),
    apiFetch<Sucursal[]>("/api/v1/sucursales", { token }).catch(() => []),
    apiFetch<Marca[]>("/api/v1/marcas", { token }).catch(() => []),
    apiFetch<Categoria[]>("/api/v1/inventory/categorias", { token }).catch(() => []),
    apiFetch<ProgramaConteo[]>(
      `/api/v1/inventory/conteos/programa?${query}`,
      { token },
    ).catch(() => []),
  ]);

  return (
    <ConteosCliente
      conteos={conteos}
      programa={programa}
      almacenes={almacenes}
      sucursales={sucursales.map((s) => ({ id: s.id, nombre: s.nombre }))}
      marcas={marcas.map((m) => ({ id: m.id, nombre: m.nombre }))}
      categorias={categorias.map((c) => ({ id: c.id, nombre: c.nombre }))}
      nombreDeAlmacen={Object.fromEntries(almacenes.map((a) => [a.id, a.nombre]))}
      filtros={filtrosDe(filtros)}
      permisos={usuario.permisos}
    />
  );
}
