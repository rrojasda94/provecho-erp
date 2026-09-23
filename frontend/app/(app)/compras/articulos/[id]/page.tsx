import {
  FichaKardex,
  type ParamsKardex,
} from "@/components/kardex/ficha-kardex";

/** La ficha del artículo vista desde Compras: se llega desde las líneas de
 * una orden de compra, para decidir a cuánto y cuándo volver a comprar. */
export default async function ArticuloCompraPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<ParamsKardex>;
}) {
  const { id } = await params;
  return <FichaKardex id={id} params={await searchParams} />;
}
