import Link from "next/link";

import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { ConteoCliente, type ConteoDetalle } from "./conteo-cliente";

type Params = Promise<{ id: string }>;

type Almacen = { id: string; nombre: string };
type Sku = { id: string; codigo: string; articulo_nombre: string };

export default async function ConteoPage({ params }: { params: Params }) {
  const { token, usuario } = await obtenerSesion();
  const { id } = await params;

  let conteo: ConteoDetalle;
  try {
    conteo = await apiFetch<ConteoDetalle>(`/api/v1/inventory/conteos/${id}`, {
      token,
    });
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 404
        ? "Ese conteo no existe o no es de tu empresa."
        : "No se pudo cargar el conteo.";
    return (
      <div className="flex flex-col gap-3">
        <p className="text-secondary">{mensaje}</p>
        <Link href="/inventario/conteos" className="text-sm underline">
          Volver a Conteos
        </Link>
      </div>
    );
  }

  const [almacenes, skus] = await Promise.all([
    apiFetch<Almacen[]>("/api/v1/almacenes", { token }).catch(() => []),
    apiFetch<Sku[]>("/api/v1/inventory/skus", { token }).catch(() => []),
  ]);

  return (
    <ConteoCliente
      conteo={conteo}
      nombreDeAlmacen={Object.fromEntries(almacenes.map((a) => [a.id, a.nombre]))}
      etiquetaDeSku={Object.fromEntries(
        skus.map((s) => [s.id, `${s.articulo_nombre} (${s.codigo})`]),
      )}
      permisos={usuario.permisos}
    />
  );
}
