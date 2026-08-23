import Link from "next/link";

import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { SolicitudCliente, type SolicitudDetalle } from "./solicitud-cliente";

type Params = Promise<{ id: string }>;

type Almacen = { id: string; nombre: string };
type Sku = { id: string; codigo: string; articulo_nombre: string };

export default async function SolicitudPage({ params }: { params: Params }) {
  const { token, usuario } = await obtenerSesion();
  const { id } = await params;

  let solicitud: SolicitudDetalle;
  try {
    solicitud = await apiFetch<SolicitudDetalle>(
      `/api/v1/inventory/solicitudes/${id}`,
      { token },
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 404
        ? "Ese requerimiento no existe o no es de tu empresa."
        : "No se pudo cargar el requerimiento.";
    return (
      <div className="flex flex-col gap-3">
        <p className="text-secondary">{mensaje}</p>
        <Link href="/inventario/solicitudes" className="text-sm underline">
          Volver a Requerimientos
        </Link>
      </div>
    );
  }

  const [almacenes, skus] = await Promise.all([
    apiFetch<Almacen[]>("/api/v1/almacenes", { token }).catch(() => []),
    apiFetch<Sku[]>("/api/v1/inventory/skus", { token }).catch(() => []),
  ]);

  return (
    <SolicitudCliente
      solicitud={solicitud}
      nombreDeAlmacen={Object.fromEntries(almacenes.map((a) => [a.id, a.nombre]))}
      skus={skus.map((s) => ({
        id: s.id,
        etiqueta: `${s.articulo_nombre} (${s.codigo})`,
      }))}
      permisos={usuario.permisos}
    />
  );
}
