"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { RecetaEditor } from "@/components/catalogo/receta-editor";
import {
  catalogoApi,
  type Articulo,
  type RecetaDetalle,
  type UnidadMedida,
} from "@/lib/catalogo";
import { ErrorApi } from "@/lib/cliente-api";

/**
 * Una receta vista fuera de un producto: mismo editor, más la pregunta que
 * solo tiene sentido acá — **qué produce**.
 *
 * Una receta de venta la consume `producto_comercial`; una de cocina produce
 * un artículo inventariable (`receta.articulo_id`): masa, salsa, fondo. Esa
 * segunda es la "subreceta", y hasta ahora no había dónde declararla.
 */
export function FichaReceta({
  receta,
  articulos,
  unidades,
}: {
  receta: RecetaDetalle;
  articulos: Articulo[];
  unidades: UnidadMedida[];
}) {
  const router = useRouter();
  const [produce, setProduce] = useState(receta.articulo_id ?? "");
  const [error, setError] = useState("");

  // Solo artículos que la cocina produce: marcar una receta como productora
  // de un insumo comprado mezclaría dos flujos de abastecimiento distintos.
  const subrecetas = articulos.filter((a) => a.tipo === "subreceta" && !a.archivado);

  async function borrar() {
    if (!window.confirm(`¿Borrar la receta "${receta.nombre}" y sus insumos?`)) return;
    setError("");
    try {
      await catalogoApi.eliminarReceta(receta.id);
      router.push("/catalogo/recetas");
    } catch (e) {
      // El 409 nombra al producto que la está usando: es exactamente lo que
      // hace falta para desatascarse, así que se muestra tal cual.
      setError(e instanceof ErrorApi ? e.message : "No se pudo borrar la receta.");
    }
  }

  async function asignar(articuloId: string) {
    setError("");
    setProduce(articuloId);
    try {
      await catalogoApi.editarReceta(receta.id, { articulo_id: articuloId });
      router.refresh();
    } catch (e) {
      setProduce(receta.articulo_id ?? "");
      setError(e instanceof ErrorApi ? e.message : "No se pudo asignar el artículo.");
    }
  }

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <div className="flex items-center justify-between">
        <Link href="/catalogo/recetas" className="text-sm text-gray hover:text-primary">
          ← Recetas
        </Link>
        <button
          type="button"
          onClick={borrar}
          className="text-xs font-semibold text-secondary hover:underline"
          title="Solo si ningún producto comercial la usa"
        >
          Borrar receta
        </button>
      </div>

      <section className="rounded-lg border border-gray/20 bg-white p-4">
        <RecetaEditor
          recetaId={receta.id}
          nombreSugerido={receta.nombre}
          articulos={articulos}
          unidades={unidades}
          onRecetaCreada={(id) => router.push(`/catalogo/recetas/${id}`)}
        />
      </section>

      <section className="rounded-lg border border-gray/20 bg-white p-4">
        <h2 className="mb-1 font-heading text-lg text-dark">
          ¿Qué produce?
        </h2>
        <p className="mb-3 text-xs text-gray">
          Déjalo vacío si es la receta de algo que se vende. Elige un artículo
          si la cocina la prepara para usarla después (masa, salsa): ahí
          producción sabe qué explotar y qué stock genera.
        </p>
        {subrecetas.length === 0 ? (
          <p className="text-sm text-gray">
            No hay artículos de tipo <strong>subreceta</strong> todavía. Créalos
            en{" "}
            <Link href="/inventario/articulos" className="text-primary hover:underline">
              Inventario → Artículos
            </Link>
            .
          </p>
        ) : (
          <select
            value={produce}
            onChange={(e) => e.target.value && asignar(e.target.value)}
            className="min-w-64 text-sm"
            aria-label="Artículo que produce la receta"
          >
            <option value="">No produce un artículo (receta de venta)</option>
            {subrecetas.map((a) => (
              <option key={a.id} value={a.id}>
                {a.nombre}
              </option>
            ))}
          </select>
        )}
        {error && (
          <p role="alert" className="mt-2 text-sm font-semibold text-secondary">
            {error}
          </p>
        )}
      </section>
    </div>
  );
}
