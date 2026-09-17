/**
 * Único cliente de la API para todo el sitio (ADR-103). Solo llama a
 * `/api/v1/storefront/publico/*` — el proceso de Next habla con la API por
 * la red interna de Docker (`API_INTERNAL_URL`), nunca el navegador.
 *
 * Sin token: esta superficie no lleva JWT (`src/modules/storefront/api/
 * publico_routers.py`). No hay proxy genérico como
 * `frontend/app/api/proxy/[...ruta]` a propósito — el navegador no puede
 * pedir nada que este cliente no haya decidido exponer primero.
 */
export const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, mensaje: string) {
    super(mensaje);
    this.status = status;
  }
}

async function leerError(respuesta: Response): Promise<string> {
  try {
    const cuerpo = await respuesta.json();
    if (typeof cuerpo?.detail === "string") return cuerpo.detail;
  } catch {
    // sin cuerpo JSON legible
  }
  return `Error ${respuesta.status}`;
}

/**
 * Para mutaciones de cuenta (registro, login, direcciones, favoritos):
 * **lanza** `ApiError` en vez de degradar a `null` — acá sí hay un usuario
 * esperando una respuesta concreta, a diferencia del contenido público que
 * `apiFetch` sirve mientras el backend puede estar caído.
 */
export async function apiAuth<T>(
  ruta: string,
  opciones: { token?: string; metodo?: string; cuerpo?: unknown } = {},
): Promise<T> {
  const respuesta = await fetch(`${API_INTERNAL_URL}${ruta}`, {
    method: opciones.metodo ?? "GET",
    headers: {
      "Content-Type": "application/json",
      ...(opciones.token ? { Authorization: `Bearer ${opciones.token}` } : {}),
    },
    body: opciones.cuerpo !== undefined ? JSON.stringify(opciones.cuerpo) : undefined,
    cache: "no-store",
  });
  if (!respuesta.ok) {
    throw new ApiError(respuesta.status, await leerError(respuesta));
  }
  if (respuesta.status === 204) return undefined as T;
  return (await respuesta.json()) as T;
}

/**
 * `revalidate` en segundos: el sitio no necesita datos al segundo, y
 * revalidar cada minuto mantiene el catálogo/promos/horarios al día sin
 * golpear la API en cada visita (`Cache-Control` del propio endpoint
 * público ya pide lo mismo, 60 s).
 *
 * Nunca lanza por un fallo de red: el `next build` dentro del Dockerfile no
 * tiene la API arriba, y una página que revienta el build por eso es peor
 * que una que se prerrenderiza vacía y se completa en producción.
 */
export async function apiFetch<T>(
  ruta: string,
  opciones: { revalidate?: number } = {},
): Promise<T | null> {
  try {
    const respuesta = await fetch(`${API_INTERNAL_URL}${ruta}`, {
      next: { revalidate: opciones.revalidate ?? 60 },
    });
    if (!respuesta.ok) {
      if (respuesta.status === 404) return null;
      throw new ApiError(respuesta.status, `Error ${respuesta.status} en ${ruta}`);
    }
    return (await respuesta.json()) as T;
  } catch {
    // Sin API (build, o el servicio está caído): la página se pinta vacía,
    // nunca revienta. Cada `page.tsx` decide qué mostrar con `null`.
    return null;
  }
}
