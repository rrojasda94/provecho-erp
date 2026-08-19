/**
 * Los cuatro filtros que comparten Requerimientos y Conteos: marca, sucursal,
 * almacén y estado (ADR-051).
 *
 * Viajan en la URL para que el enlace se pueda compartir y el corte lo haga
 * el servidor. Vive en `lib/` y no en cada pantalla porque las dos arman
 * exactamente la misma query contra endpoints que solo difieren en cómo se
 * llama el parámetro del almacén, y dos copias de esto se desincronizan en el
 * primer filtro que alguien agregue.
 */

export type FiltrosInventario = {
  almacen: string;
  estado: string;
  sucursal: string;
  marca: string;
};

export type ParamsFiltros = {
  almacen?: string;
  estado?: string;
  sucursal?: string;
  marca?: string;
};

/** Lo que la pantalla vuelve a dibujar en sus selectores. */
export function filtrosDe(params: ParamsFiltros): FiltrosInventario {
  return {
    almacen: params.almacen ?? "",
    estado: params.estado ?? "",
    sucursal: params.sucursal ?? "",
    marca: params.marca ?? "",
  };
}

/**
 * La query para la API. `claveAlmacen` cambia entre endpoints —la solicitud
 * distingue el almacén *solicitante*— y es la única diferencia entre los dos
 * llamados.
 */
export function queryDeFiltros(
  params: ParamsFiltros,
  claveAlmacen = "almacen_id",
): URLSearchParams {
  const query = new URLSearchParams();
  const pares: [string, string | undefined][] = [
    [claveAlmacen, params.almacen],
    ["estado", params.estado],
    ["sucursal_id", params.sucursal],
    ["marca_id", params.marca],
  ];
  for (const [clave, valor] of pares) if (valor) query.set(clave, valor);
  return query;
}
