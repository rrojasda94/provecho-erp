import { FichaKardex } from "@/components/kardex/ficha-kardex";

/** Ficha del artículo con su kardex gráfico. También es el destino de
 * `consumos_omitidos` en el tablero (ADR-024 + ADR-036). */
export default async function ArticuloPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <FichaKardex id={id} />;
}
