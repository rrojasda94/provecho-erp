import { KardexArticulo } from "@/components/kardex/kardex-articulo";
import { Rastro } from "@/components/shell/rastro";
import { ApiError, apiFetch } from "@/lib/api";
import { hoyEnZonaDelNegocio } from "@/lib/fechas";
import type { Kardex, PrecioHistorico } from "@/lib/kardex";
import { obtenerSesion } from "@/lib/sesion";

type Articulo = {
  id: string;
  id_interno: string;
  nombre: string;
  tipo: string;
  unidad_medida_id: string;
  costo_promedio: string;
  archivado: boolean;
  controla_lote: boolean;
  dias_alerta_vencimiento: number | null;
};

type UnidadMedida = { id: string; nombre: string };

function mensajeDeError(e: unknown): string {
  const status = e instanceof ApiError ? e.status : 0;
  if (status === 403)
    return "Tu usuario no tiene permiso para ver este artículo.";
  if (status === 404) return "Ese artículo no existe.";
  return "No se pudo cargar el artículo.";
}

/**
 * Ficha de un artículo con su kardex gráfico. La misma en Inventario y en
 * Compras: cambia por dónde se llega, no lo que se necesita saber para
 * decidir cuándo y a cuánto comprar.
 *
 * El historial de precios es de `purchases` y lo pide aparte: sin
 * `purchases.leer` la ficha se dibuja igual, sin el gráfico de precio.
 */
export async function FichaKardex({ id }: { id: string }) {
  const { token } = await obtenerSesion();

  let articulo: Articulo;
  let kardex: Kardex;
  try {
    [articulo, kardex] = await Promise.all([
      apiFetch<Articulo>(`/api/v1/inventory/articulos/${id}`, { token }),
      apiFetch<Kardex>(`/api/v1/inventory/articulos/${id}/kardex`, { token }),
    ]);
  } catch (e) {
    return <p className="text-secondary">{mensajeDeError(e)}</p>;
  }
  const [precios, unidades] = await Promise.all([
    apiFetch<PrecioHistorico[]>(
      `/api/v1/purchases/articulos/${id}/historial-precios`,
      {
        token,
      },
    ).catch(() => null),
    apiFetch<UnidadMedida[]>("/api/v1/inventory/unidades-medida", {
      token,
    }).catch(() => []),
  ]);
  const unidad =
    unidades.find((u) => u.id === articulo.unidad_medida_id)?.nombre ?? "";

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
      <h1 className="font-heading text-xl italic uppercase text-foreground">
        {articulo.nombre}
      </h1>
      <dl className="grid gap-4 rounded-lg border border-border bg-card p-4 sm:grid-cols-3">
        {datos.map(([etiqueta, valor]) => (
          <div key={etiqueta} className="flex flex-col gap-0.5">
            <dt className="text-xs font-bold uppercase text-muted-foreground">
              {etiqueta}
            </dt>
            <dd className="text-sm text-foreground">{valor}</dd>
          </div>
        ))}
      </dl>
      <KardexArticulo
        kardex={kardex}
        precios={precios}
        unidad={unidad}
        hoy={hoyEnZonaDelNegocio()}
      />
    </section>
  );
}
