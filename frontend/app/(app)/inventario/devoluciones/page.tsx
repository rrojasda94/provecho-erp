import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import {
  DevolucionesCliente,
  type Devolucion,
  type OpcionAlmacen,
  type OpcionSku,
} from "./devoluciones-cliente";

type Params = Promise<{ devolucion?: string }>;

type Almacen = { id: string; nombre: string };
type Sku = { id: string; codigo: string; articulo_nombre: string };

export default async function DevolucionesPage({
  searchParams,
}: {
  searchParams: Params;
}) {
  const { token, usuario } = await obtenerSesion();
  const { devolucion } = await searchParams;

  let devoluciones: Devolucion[];
  try {
    devoluciones = await apiFetch<Devolucion[]>("/api/v1/inventory/devoluciones", {
      token,
    });
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver las devoluciones."
        : "No se pudieron cargar las devoluciones.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  // Las opciones del formulario no bloquean el listado: sin permiso de
  // catálogo se ve la tabla igual y el botón de registrar queda inerte, que
  // es mejor que una pantalla en blanco por un 403 de otra consulta.
  const [almacenes, skus] = await Promise.all([
    apiFetch<Almacen[]>("/api/v1/almacenes", { token }).catch(() => []),
    apiFetch<Sku[]>("/api/v1/inventory/skus", { token }).catch(() => []),
  ]);

  return (
    <DevolucionesCliente
      devoluciones={devoluciones}
      resaltado={devolucion ?? null}
      almacenes={almacenes.map((a): OpcionAlmacen => ({ id: a.id, nombre: a.nombre }))}
      skus={skus.map(
        (s): OpcionSku => ({ id: s.id, etiqueta: `${s.articulo_nombre} (${s.codigo})` }),
      )}
      permisos={usuario.permisos}
    />
  );
}
