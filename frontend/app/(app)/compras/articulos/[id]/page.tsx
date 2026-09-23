import { FichaKardex } from "@/components/kardex/ficha-kardex";

/** La ficha del artículo vista desde Compras: se llega desde las líneas de
 * una orden de compra, para decidir a cuánto y cuándo volver a comprar. */
export default async function ArticuloCompraPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <FichaKardex id={id} />;
}
