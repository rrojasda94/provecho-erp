// Extensión explícita: estos dos módulos los carga `node --test`, que
// resuelve ESM por ruta real (mismo motivo que en `lib/carga.test.ts`).
import { type ErrorCampo, leerError } from "./errores.ts";

/**
 * Base de la API vista desde el SERVIDOR de Next.js (Server Actions,
 * Server Components) — no confundir con NEXT_PUBLIC_API_URL, que es la
 * base vista desde el NAVEGADOR. Dentro de docker-compose, el navegador
 * llega a la API por `localhost:8000` (puerto publicado), pero el proceso
 * de Next.js corre en OTRO contenedor sin ese `localhost` compartido —
 * necesita el nombre del servicio (`http://api:8000`).
 */
export const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

/**
 * Sobre de los listados que crecen con la operación (ADR-026). Los
 * catálogos de configuración —roles, divisas, unidades de medida— siguen
 * devolviendo un array plano: paginarlos sería un sobre que desenvolver
 * para nada.
 */
export type Pagina<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

export class ApiError extends Error {
  status: number;
  /** Campos que el servidor rechazó (422). Vacío en todo lo demás. */
  campos: ErrorCampo[];
  /**
   * Segundos del `Retry-After` cuando el servidor lo manda (hoy solo el 429
   * de `core/rate_limit.py`). Es el único dato que dice **cuánto** esperar:
   * sin él una pantalla solo puede escribir "más tarde", que no le sirve a
   * nadie parado frente a una caja.
   */
  reintentarEn?: number;

  constructor(
    status: number,
    message: string,
    reintentarEn?: number,
    campos: ErrorCampo[] = [],
  ) {
    super(message);
    this.status = status;
    this.reintentarEn = reintentarEn;
    this.campos = campos;
  }
}

/** `Retry-After` en segundos. La forma con fecha HTTP existe en el estándar
 * pero ninguna respuesta del ERP la usa, así que se ignora en vez de fingir
 * que se soporta: `undefined` es honesto, una fecha mal parseada no. */
function reintentarEn(respuesta: Response): number | undefined {
  const crudo = respuesta.headers.get("Retry-After");
  const segundos = crudo === null ? NaN : Number(crudo);
  return Number.isFinite(segundos) && segundos > 0 ? segundos : undefined;
}

/** Llama a la API con el token del usuario. Lanza `ApiError` si falla —
 * el llamador decide cómo mostrarlo (nunca se traga el error en silencio). */
export async function apiFetch<T>(
  ruta: string,
  opciones: { token?: string; metodo?: string; cuerpo?: unknown } = {},
): Promise<T> {
  const respuesta = await fetch(`${API_INTERNAL_URL}${ruta}`, {
    method: opciones.metodo ?? "GET",
    headers: {
      "Content-Type": "application/json",
      ...(opciones.token ? { Authorization: `Bearer ${opciones.token}` } : {}),
    },
    body: opciones.cuerpo ? JSON.stringify(opciones.cuerpo) : undefined,
    cache: "no-store",
  });

  if (!respuesta.ok) {
    const { mensaje, campos } = await leerError(respuesta);
    throw new ApiError(respuesta.status, mensaje, reintentarEn(respuesta), campos);
  }
  // 204 no trae cuerpo (asignar/quitar rol, marcar leída): pedirle `.json()`
  // revienta con "Unexpected end of JSON input" sobre una llamada que salió
  // bien.
  if (respuesta.status === 204) return undefined as T;
  return respuesta.json() as Promise<T>;
}

/** El techo de `page_size` del contrato (`PAGE_SIZE_MAXIMO`, ADR-026). */
export const PAGINA_MAXIMA = 200;

/**
 * Junta todas las páginas de un listado, de a una, hasta cubrir `total`.
 *
 * Aparte de `apiFetchTodas` para poder probarla sin red, y para que el cliente
 * (que pide por el proxy, no con `apiFetch`) la use con su propio `pedir`.
 */
export async function recorrerPaginas<T>(
  pedir: (page: number) => Promise<Pagina<T>>,
): Promise<T[]> {
  const items: T[] = [];
  for (let page = 1; ; page++) {
    const pagina = await pedir(page);
    items.push(...pagina.items);
    // Una página corta es la última, diga lo que diga `total`: si alguien
    // borró filas mientras se recorría, seguir pidiendo sería un bucle.
    if (pagina.items.length < pagina.page_size || items.length >= pagina.total) return items;
  }
}

/** `ruta` con `page` y `page_size` al techo, conservando su query. */
export function rutaPagina(ruta: string, page: number): string {
  const [base, query = ""] = ruta.split("?");
  const params = new URLSearchParams(query);
  params.set("page", String(page));
  params.set("page_size", String(PAGINA_MAXIMA));
  return `${base}?${params}`;
}

/**
 * Un listado paginado **completo**.
 *
 * Existe porque pedir `page_size=200` y usar `.items` cortaba en silencio en la
 * fila 200 —o en la 50, donde ni se pasaba el tamaño—: lo que no llegó no
 * aparecía en la tabla ni en los desplegables, y nada lo decía.
 *
 * ponytail: trae todo en serie de a 200. Sirve mientras un listado sean miles,
 * no cientos de miles; el que crezca a eso pasa a paginar en el servidor como
 * Artículos (`TablaDatos` con `servidor`).
 */
export function apiFetchTodas<T>(
  ruta: string,
  opciones: { token?: string } = {},
): Promise<T[]> {
  return recorrerPaginas((page) => apiFetch<Pagina<T>>(rutaPagina(ruta, page), opciones));
}

/** `apiFetchTodas` con el sobre de siempre, para las pantallas que ya leen
 * `.items` y `.total`: cambiar la llamada alcanza, el resto queda igual. */
export async function apiFetchCompleto<T>(
  ruta: string,
  opciones: { token?: string } = {},
): Promise<Pagina<T>> {
  const items = await apiFetchTodas<T>(ruta, opciones);
  return { items, total: items.length, page: 1, page_size: items.length };
}

/** Lo que una tabla paginada en el servidor lleva en la URL. */
export type ParamsPagina = { q?: string; page?: string; page_size?: string };

/**
 * `?q&page&page_size` de la URL, acotados a lo que el contrato acepta —la URL
 * la escribe cualquiera—, y la query lista para la API.
 */
export function leerPagina({ q, page, page_size }: ParamsPagina, porDefecto = 50) {
  const pagina = Math.max(1, Math.trunc(Number(page)) || 1);
  const tamano = Math.min(PAGINA_MAXIMA, Math.max(1, Math.trunc(Number(page_size)) || porDefecto));
  const busqueda = q?.trim() ?? "";
  const query = new URLSearchParams({ page: String(pagina), page_size: String(tamano) });
  if (busqueda) query.set("q", busqueda);
  return { query, pagina, tamano, q: busqueda };
}
