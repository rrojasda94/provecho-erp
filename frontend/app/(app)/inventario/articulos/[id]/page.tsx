import {
  FichaKardex,
  type ParamsKardex,
} from "@/components/kardex/ficha-kardex";

/** Ficha del artículo con su kardex gráfico. También es el destino de
 * `consumos_omitidos` en el tablero (ADR-024 + ADR-036). */
export default async function ArticuloPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<ParamsKardex>;
}) {
  const { id } = await params;
  return <FichaKardex id={id} params={await searchParams} />;
}
