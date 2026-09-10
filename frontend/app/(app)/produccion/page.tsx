import Link from "next/link";

import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { primeroElDe } from "@/lib/destinos";
import { obtenerSesion } from "@/lib/sesion";

import { OrdenesCliente, type Almacen, type Articulo, type Orden } from "./ordenes-cliente";

// Antes se pedía la página por defecto (50) sin forma de ver el resto: el
// único indicio de que faltaban órdenes era `AvisoRecortado`, sin ningún
// enlace para llegar a ellas.
const PAGE_SIZE = 20;

export default async function ProduccionPage({
  searchParams,
}: {
  searchParams: Promise<{ orden?: string; page?: string }>;
}) {
  const { token, usuario } = await obtenerSesion();
  // `?orden=<id>` es a donde llega `production.no_conformidad_detectada`: la
  // orden reportada sube al tope de la lista (ADR-036).
  const { orden, page = "1" } = await searchParams;

  try {
    // Los catálogos que alimentan un desplegable se piden al tope de página
    // (`PAGE_SIZE_MAXIMO`, 200) y no con el defecto de 50: el campo filtra sobre
    // lo que recibió, así que lo que no vino no existe para quien busca — y nada
    // en pantalla lo dice. Para el catálogo de artículos, que no cabe ni en 200,
    // el propio campo busca contra el servidor (`?q=`); esto es solo lo que
    // ofrece antes de teclear.
    const [ordenes, articulos, almacenes] = await Promise.all([
      apiFetch<Pagina<Orden>>(
        `/api/v1/production/ordenes?page=${page}&page_size=${PAGE_SIZE}`,
        { token },
      ),
      apiFetch<Pagina<Articulo>>("/api/v1/inventory/articulos?page_size=200", {
        token,
      }),
      apiFetch<Almacen[]>("/api/v1/almacenes", { token }),
    ]);
    return (
      <div className="flex flex-col gap-4">
        <OrdenesCliente
          ordenes={primeroElDe(ordenes.items, orden ?? null, (o) => o.id)}
          total={ordenes.total}
          articulos={articulos.items}
          almacenes={almacenes}
          permisos={usuario.permisos}
        />
        <Paginador pagina={ordenes} />
      </div>
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver producción."
        : "No se pudieron cargar las órdenes de producción.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}

/** Mismo patrón que `/auditoria`: la única forma real de llegar al resto de
 * las órdenes cuando pasan de una página, en vez de solo decir cuántas faltan. */
function Paginador({ pagina }: { pagina: Pagina<Orden> }) {
  const paginas = Math.max(1, Math.ceil(pagina.total / pagina.page_size));
  if (paginas <= 1) return null;
  const enlace = (n: number) => `/produccion?page=${n}`;
  return (
    <div className="flex items-center gap-4 text-sm">
      <span className="text-gray">
        {pagina.total} órdenes · página {pagina.page} de {paginas}
      </span>
      {pagina.page > 1 && (
        <Link
          href={enlace(pagina.page - 1)}
          className="font-semibold text-primary hover:underline"
        >
          ← Anterior
        </Link>
      )}
      {pagina.page < paginas && (
        <Link
          href={enlace(pagina.page + 1)}
          className="font-semibold text-primary hover:underline"
        >
          Siguiente →
        </Link>
      )}
    </div>
  );
}
