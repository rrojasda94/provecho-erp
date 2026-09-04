import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import {
  MermasCliente,
  type Merma,
  type OpcionAlmacen,
  type OpcionSku,
} from "./mermas-cliente";

type Almacen = { id: string; nombre: string };
type Sku = { id: string; codigo: string; articulo_nombre: string };

export default async function MermasPage() {
  const { token, usuario } = await obtenerSesion();

  let mermas: Merma[];
  try {
    mermas = await apiFetch<Merma[]>("/api/v1/inventory/mermas", { token });
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver las mermas."
        : "No se pudieron cargar las mermas.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  // Los catálogos del formulario no bloquean el listado: sin ellos la tabla
  // se ve igual y el botón de registrar queda inerte, que es mejor que una
  // pantalla en blanco por un 403 de otra consulta. Mismo criterio que
  // Devoluciones.
  const [almacenes, skus] = await Promise.all([
    apiFetch<Almacen[]>("/api/v1/almacenes", { token }).catch(() => []),
    apiFetch<Sku[]>("/api/v1/inventory/skus", { token }).catch(() => []),
  ]);

  return (
    <MermasCliente
      mermas={mermas}
      almacenes={almacenes.map((a): OpcionAlmacen => ({ id: a.id, nombre: a.nombre }))}
      skus={skus.map(
        (s): OpcionSku => ({ id: s.id, etiqueta: `${s.articulo_nombre} (${s.codigo})` }),
      )}
      permisos={usuario.permisos}
    />
  );
}
