"use client";

import { ChevronLeft } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Fragment, useEffect } from "react";

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { anotarNavegacion, hayHistorialPropio } from "@/lib/historial";
import { padreDe, rastroDe } from "@/lib/rastro";

/**
 * Dónde estoy y cómo salgo, en una línea.
 *
 * Reemplaza los `← Sección` que cada ficha cableaba a mano. Dos problemas
 * tenían: no decían el camino completo (de una ficha de SKU no se sabía a qué
 * artículo pertenecía) y **subían de nivel en vez de volver** — desde el SKU,
 * el `←` llevaba al listado de artículos y no al artículo del que uno venía.
 *
 * El rastro es jerárquico (siempre el mismo camino para la misma ruta) y el
 * `←` es histórico (vuelve por donde uno vino). Son dos preguntas distintas
 * —"dónde estoy" y "cómo deshago el último paso"— y por eso son dos controles
 * y no uno.
 */
export function Rastro({
  hoja,
  volverA,
}: {
  hoja?: string;
  /** Destino del `←` cuando no hay historial propio, si el nivel de arriba
   * no alcanza. Lo usa la ficha de venta, cuya jornada necesita la sucursal
   * y la fecha del pedido para no abrirse en el día de hoy. */
  volverA?: string;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const migas = rastroDe(pathname, hoja);
  const padre = volverA ?? padreDe(migas);

  return (
    <div className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-1">
      <Link
        href={padre}
        onClick={(e) => {
          // El `href` es el fallback real, no un adorno: si no hay historial
          // propio —entró por URL directa, o recargó— el link navega solo.
          if (!hayHistorialPropio()) return;
          e.preventDefault();
          router.back();
        }}
        className="inline-flex items-center gap-1 text-sm text-gray transition-colors hover:text-dark"
      >
        <ChevronLeft size={15} strokeWidth={1.75} aria-hidden />
        Volver
      </Link>

      <Breadcrumb>
        <BreadcrumbList>
          {migas.map((miga, i) => (
            // `<>` con el separador **hermano** del ítem y no dentro: los dos
            // son `<li>`, y anidarlos daba `<li><li>`.
            <Fragment key={miga.href}>
              <BreadcrumbItem>
                {i === migas.length - 1 ? (
                  <BreadcrumbPage>{miga.label}</BreadcrumbPage>
                ) : (
                  // `render` y no `asChild`: este shadcn está sobre Base UI,
                  // igual que el `PopoverTrigger` del lienzo.
                  <BreadcrumbLink render={<Link href={miga.href}>{miga.label}</Link>} />
                )}
              </BreadcrumbItem>
              {i < migas.length - 1 && <BreadcrumbSeparator />}
            </Fragment>
          ))}
        </BreadcrumbList>
      </Breadcrumb>
    </div>
  );
}

/** Cuenta las navegaciones del shell. Va montado una sola vez en el layout de
 * `(app)`, no en cada pantalla: si viviera en la ficha solo contaría desde que
 * la ficha existe, que es justo lo que hay que saber de antes. */
export function RastreoDeNavegacion() {
  const pathname = usePathname();
  useEffect(() => {
    anotarNavegacion();
  }, [pathname]);
  return null;
}
