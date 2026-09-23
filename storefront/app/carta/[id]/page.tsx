import { notFound } from "next/navigation";
import type { Metadata } from "next";

import { apiFetch } from "@/lib/api";
import { URL_SITIO } from "@/lib/sitio";

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
  if (!producto) return { title: "Producto" };
  const imagen = producto.fotos[0];
  return {
    title: producto.nombre,
    description: producto.descripcion ?? undefined,
    openGraph: {
      title: producto.nombre,
      description: producto.descripcion ?? undefined,
      url: `${URL_SITIO}/carta/${id}`,
      images: imagen ? [imagen] : undefined,
    },
  };
}

function jsonLdDe(id: string, producto: ProductoDetalle) {
  return {
    "@context": "https://schema.org",
    "@type": "Product",
    name: producto.nombre,
    description: producto.descripcion ?? undefined,
    image: producto.fotos[0],
    url: `${URL_SITIO}/carta/${id}`,
    offers: {
      "@type": "Offer",
      priceCurrency: "PEN",
      price: producto.precio_desde,
      availability: producto.disponible
        ? "https://schema.org/InStock"
        : "https://schema.org/OutOfStock",
    },
  };
}

export default async function ProductoPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const producto = await apiFetch<ProductoDetalle>(`/api/v1/storefront/publico/productos/${id}`);
  if (!producto) notFound();

  return (
    <>
      <script
        type="application/ld+json"
         
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLdDe(id, producto)) }}
      />
      <DetalleProducto producto={producto} />
    </>
  );
}
