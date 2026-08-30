import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import {
  AjustesCliente,
  type Ajuste,
  type OpcionAlmacen,
  type OpcionSku,
} from "./ajustes-cliente";

type Params = Promise<{ ajuste?: string; estado?: string }>;

type Almacen = { id: string; nombre: string };
type Sku = { id: string; codigo: string; articulo_nombre: string; controla_lote: boolean };

export default async function AjustesPage({
  searchParams,
}: {
  searchParams: Params;
}) {
  const { token, usuario } = await obtenerSesion();
  const filtros = await searchParams;

  // Sin filtro explícito se muestran los pendientes: la pantalla existe para
  // aprobarlos o rechazarlos, no para leer el histórico. Salvo que se llegue
  // desde un reporte, donde el ajuste puede estar ya resuelto.
  const estado = filtros.estado ?? (filtros.ajuste ? "" : "pendiente");

  let ajustes: Ajuste[];
  try {
    const query = new URLSearchParams(estado ? { estado } : {});
    ajustes = (
      await apiFetch<Pagina<Ajuste>>(`/api/v1/inventory/ajustes?${query}`, { token })
    ).items;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los ajustes de inventario."
        : "No se pudieron cargar los ajustes.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  // Las opciones del formulario no bloquean el listado: sin permiso de
  // catálogo se ve la tabla igual y el disparador queda inerte, que es mejor
  // que una pantalla en blanco por un 403 de otra consulta.
  const [almacenes, skus] = await Promise.all([
    apiFetch<Almacen[]>("/api/v1/almacenes", { token }).catch(() => []),
    apiFetch<Sku[]>("/api/v1/inventory/skus", { token }).catch(() => []),
  ]);

  return (
    <AjustesCliente
      ajustes={ajustes}
      resaltado={filtros.ajuste ?? null}
      estado={estado}
      permisos={usuario.permisos}
      almacenes={almacenes.map((a): OpcionAlmacen => ({ id: a.id, nombre: a.nombre }))}
      skus={skus.map(
        (s): OpcionSku => ({
          id: s.id,
          etiqueta: `${s.articulo_nombre} (${s.codigo})`,
          controlaLote: s.controla_lote,
        }),
      )}
    />
  );
}
