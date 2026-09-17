/**
 * Único cliente de la API para todo el sitio (ADR-101). Solo llama a
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
