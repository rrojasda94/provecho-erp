"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { grupoDe, type ItemSubmenu } from "@/lib/navegacion";

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
export function NavModulo({ item }: { item: ItemSubmenu }) {
  const pathname = usePathname();
  // Un grupo con pestañas está activo en cualquiera de ellas: `/inventario/
  // lotes` marca "Stock" aunque el href del grupo sea `/inventario/stock`.
  const activo = (item.pestanas ?? [item]).some(
    (p) => pathname === p.href || pathname.startsWith(`${p.href}/`),
  );

  return (
    <Link href={item.href} className="nav-modulo" aria-current={activo ? "page" : undefined}>
      {item.label}
    </Link>
  );
}

/** Las pestañas del grupo en el que cae la ruta, arriba del contenido. Sin
 * grupo no dibuja nada: los módulos sin pestañas quedan como estaban. */
export function PestanasSeccion({ items }: { items: ItemSubmenu[] }) {
  const pathname = usePathname();
  const grupo = grupoDe(items, pathname);
  if (!grupo?.pestanas) return null;

  return (
    <nav aria-label={grupo.label} className="pestanas-seccion print:hidden">
      {grupo.pestanas.map((p) => {
        const activa = pathname === p.href || pathname.startsWith(`${p.href}/`);
        return (
          <Link key={p.href} href={p.href} aria-current={activa ? "page" : undefined}>
            {p.label}
          </Link>
        );
      })}
    </nav>
  );
}
