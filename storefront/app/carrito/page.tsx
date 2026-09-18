import type { Metadata } from "next";

import { CarritoCliente } from "./carrito-cliente";

export const metadata: Metadata = { title: "Tu carrito" };

export default function CarritoPage() {
  return <CarritoCliente />;
}
