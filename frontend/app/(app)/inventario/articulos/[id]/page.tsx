import { Rastro } from "@/components/shell/rastro";
import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

type Articulo = {
  id: string;
  id_interno: string;
  nombre: string;
  tipo: string;
  categoria_id: string | null;
  costo_promedio: string;
  archivado: boolean;
  controla_lote: boolean;
  dias_alerta_vencimiento: number | null;
};

/** Destino de `consumos_omitidos` en el tablero (ADR-024 + ADR-036): la fila
 * dice qué artículo no se movió, esto dice qué artículo es. */
export default async function ArticuloPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { token } = await obtenerSesion();

  let articulo: Articulo;
  try {
    articulo = await apiFetch<Articulo>(`/api/v1/inventory/articulos/${id}`, {
      token,
    });
  } catch (e) {
    const status = e instanceof ApiError ? e.status : 0;
    const mensaje =
      status === 403
        ? "Tu usuario no tiene permiso para ver este artículo."
        : status === 404
          ? "Ese artículo no existe."
          : "No se pudo cargar el artículo.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  const datos: [string, string][] = [
    ["Código interno", articulo.id_interno],
    ["Tipo", articulo.tipo],
    ["Costo promedio", articulo.costo_promedio],
    ["Controla lote", articulo.controla_lote ? "Sí" : "No"],
    [
      "Aviso de vencimiento",
      articulo.dias_alerta_vencimiento === null
        ? "—"
        : `${articulo.dias_alerta_vencimiento} día(s) antes`,
    ],
    ["Estado", articulo.archivado ? "Archivado" : "Activo"],
  ];

  return (
    <section className="flex flex-col gap-6">
      <Rastro hoja={articulo.nombre} />
      <h1 className="font-heading text-xl italic uppercase text-dark">
        {articulo.nombre}
      </h1>
      <dl className="grid gap-4 rounded border border-gray/20 p-4 sm:grid-cols-3">
        {datos.map(([etiqueta, valor]) => (
          <div key={etiqueta} className="flex flex-col gap-0.5">
            <dt className="text-xs font-bold uppercase text-gray">{etiqueta}</dt>
            <dd className="text-sm text-dark">{valor}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
