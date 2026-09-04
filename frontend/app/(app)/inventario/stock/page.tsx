import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { tienePermiso } from "@/lib/permisos";
import { obtenerSesion } from "@/lib/sesion";

import { StockCliente, type FilaStock, type OpcionSku } from "./stock-cliente";

type Params = Promise<{
  almacen?: string;
  sucursal?: string;
  categoria?: string;
  bajo?: string;
  q?: string;
}>;

type Opcion = { id: string; nombre: string };

/** El tope de `page_size` del contrato (ADR-026). La tabla pagina del lado
 * del cliente sobre lo que recibe; cuando el catálogo pase de esto hará
 * falta cablear los controles al servidor — la deuda ya está anotada en
 * `docs/roadmap/deuda/contrato-de-api.md`. */
const MAXIMO = 200;

/**
 * Niveles de stock.
 *
 * `GET /inventory/stock` existe desde el primer slice y ninguna pantalla lo
 * consumía: lo único que mostraba saldos era la ficha de un SKU, y a esa solo
 * se llegaba desde el reporte de stock bajo mínimo, sabiendo de antemano qué
 * SKU mirar. La pregunta que nadie podía responder era la primera: qué hay.
 */
/** Los filtros de la URL, traducidos a los nombres del contrato. Aparte de
 * la página para no cargarle su complejidad a la función que además hace
 * cinco llamadas y decide qué error mostrar. */
function queryDeStock(filtros: Awaited<Params>): URLSearchParams {
  const query = new URLSearchParams({ page_size: String(MAXIMO) });
  const pares: [string, string | undefined][] = [
    ["almacen_id", filtros.almacen],
    ["sucursal_id", filtros.sucursal],
    ["categoria_id", filtros.categoria],
    ["q", filtros.q],
  ];
  for (const [clave, valor] of pares) if (valor) query.set(clave, valor);
  if (filtros.bajo === "1") query.set("bajo_minimo", "true");
  return query;
}

type Sku = { id: string; codigo: string; articulo_nombre: string };

export default async function StockPage({ searchParams }: { searchParams: Params }) {
  const { token, usuario } = await obtenerSesion();
  const filtros = await searchParams;
  const query = queryDeStock(filtros);

  let pagina: Pagina<FilaStock>;
  try {
    pagina = await apiFetch<Pagina<FilaStock>>(
      `/api/v1/inventory/stock?${query}`,
      { token },
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver el stock."
        : "No se pudo cargar el stock.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  const [almacenes, sucursales, categorias, skus] = await Promise.all([
    apiFetch<Opcion[]>("/api/v1/almacenes", { token }).catch(() => []),
    apiFetch<Opcion[]>("/api/v1/sucursales", { token }).catch(() => []),
    apiFetch<Opcion[]>("/api/v1/inventory/categorias", { token }).catch(() => []),
    apiFetch<Sku[]>("/api/v1/inventory/skus", { token }).catch(() => []),
  ]);

  return (
    <StockCliente
      filas={pagina.items}
      total={pagina.total}
      recortado={pagina.total > pagina.items.length}
      almacenes={almacenes}
      sucursales={sucursales}
      categorias={categorias}
      skus={skus.map(
        (s): OpcionSku => ({
          id: s.id,
          etiqueta: `${s.articulo_nombre} (${s.codigo})`,
        }),
      )}
      puedeDeclarar={tienePermiso(
        usuario.permisos,
        "inventory.registrar_movimiento",
      )}
      filtros={{
        almacen: filtros.almacen ?? "",
        sucursal: filtros.sucursal ?? "",
        categoria: filtros.categoria ?? "",
        bajo: filtros.bajo === "1",
        q: filtros.q ?? "",
      }}
    />
  );
}
