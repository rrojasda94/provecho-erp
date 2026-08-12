"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** Ítem del sidebar que sabe si es el activo.
 *
 * El shell venía sin resaltado con un motivo escrito: "exigiría un wrapper
 * cliente solo para leer el pathname, y ningún módulo tiene más de un ítem de
 * submenú aún". Ya no es cierto — compras, catálogo, inventario, usuarios,
 * rrhh y contabilidad tienen dos o más — y sin resaltado la única forma de
 * saber dónde se está era leer la URL. Es un componente cliente de doce
 * líneas; el resto del sidebar sigue siendo servidor.
 *
 * Coincidencia por prefijo: `/compras/ordenes-compra/OC-12` tiene que marcar
 * "Órdenes de compra". Comparar por igualdad dejaba cualquier ficha de
 * detalle sin ítem activo. */
export function NavModulo({ href, label }: { href: string; label: string }) {
  const pathname = usePathname();
  const activo = pathname === href || pathname.startsWith(`${href}/`);

  return (
    <Link href={href} className="nav-modulo" aria-current={activo ? "page" : undefined}>
      {label}
    </Link>
  );
}
