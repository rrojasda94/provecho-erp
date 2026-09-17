import { notFound } from "next/navigation";
import type { Metadata } from "next";

import { apiFetch } from "@/lib/api";

import { DetalleProducto } from "./detalle-producto";

type IngredienteDetalle = { id: string; nombre: string; descripcion: string | null; foto_url: string | null };
type Variante = { id: string; nombre: string; precio: string; disponible: boolean };
type ProductoDetalle = {
  id: string;
  nombre: string;
  descripcion: string | null;
  precio_desde: string;
  disponible: boolean;
  fotos: string[];
  variantes: Variante[];
  ingredientes_detalle: IngredienteDetalle[];
};

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const producto = await apiFetch<ProductoDetalle>(`/api/v1/storefront/publico/productos/${id}`);
  return { title: producto?.nombre ?? "Producto" };
}

export default async function ProductoPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const producto = await apiFetch<ProductoDetalle>(`/api/v1/storefront/publico/productos/${id}`);
  if (!producto) notFound();

  return <DetalleProducto producto={producto} />;
}
