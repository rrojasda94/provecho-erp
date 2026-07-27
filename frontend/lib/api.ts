/**
 * Base de la API vista desde el SERVIDOR de Next.js (Server Actions,
 * Server Components) — no confundir con NEXT_PUBLIC_API_URL, que es la
 * base vista desde el NAVEGADOR. Dentro de docker-compose, el navegador
 * llega a la API por `localhost:8000` (puerto publicado), pero el proceso
 * de Next.js corre en OTRO contenedor sin ese `localhost` compartido —
 * necesita el nombre del servicio (`http://api:8000`).
 */
export const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function mensajeDeError(respuesta: Response): Promise<string> {
  try {
    const cuerpo = await respuesta.json();
    if (typeof cuerpo.detail === "string") return cuerpo.detail;
    if (Array.isArray(cuerpo.detail)) {
      return cuerpo.detail.map((d: { msg?: string }) => d.msg).join("; ");
    }
  } catch {
    // cuerpo no era JSON — se usa el mensaje genérico de abajo.
  }
  return `Error ${respuesta.status}`;
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
    throw new ApiError(respuesta.status, await mensajeDeError(respuesta));
  }
  return respuesta.json() as Promise<T>;
}
