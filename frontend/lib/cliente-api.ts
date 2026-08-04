/**
 * Cliente HTTP del NAVEGADOR hacia la API. Todo pasa por `/api/proxy` (ver
 * `app/api/proxy/[...ruta]/route.ts`): el token vive en una cookie httpOnly
 * y nunca llega al JavaScript de la página.
 *
 * Vive aparte de `lib/pdv.ts` porque ya hay dos pantallas táctiles fuera del
 * shell (PDV y KDS) hablando con la API desde el cliente; duplicar el fetch
 * y el parseo de error en cada una era la vía rápida a dos manejos de error
 * distintos para la misma API.
 */

const BASE = "/api/proxy/api/v1";

export class ErrorApi extends Error {
  status: number;

  constructor(status: number, mensaje: string) {
    super(mensaje);
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
    // Cuerpo no-JSON: cae al mensaje genérico.
  }
  return `Error ${respuesta.status}`;
}

export async function pedir<T>(
  ruta: string,
  opciones: { metodo?: string; cuerpo?: unknown } = {},
): Promise<T> {
  const respuesta = await fetch(`${BASE}${ruta}`, {
    method: opciones.metodo ?? "GET",
    headers: { "Content-Type": "application/json" },
    body: opciones.cuerpo ? JSON.stringify(opciones.cuerpo) : undefined,
  });
  if (!respuesta.ok) {
    throw new ErrorApi(respuesta.status, await mensajeDeError(respuesta));
  }
  // 204 (los DELETE) no traen cuerpo: pedirle `.json()` a una respuesta
  // vacía revienta con un error de sintaxis que no dice nada.
  if (respuesta.status === 204) return undefined as T;
  return (await respuesta.json()) as T;
}

/** Cada operación crítica necesita su clave (RN-COM-002): un reintento por
 * red inestable no puede convertirse en un segundo cobro. */
export function claveIdempotencia(prefijo: string): string {
  return `${prefijo}-${crypto.randomUUID()}`;
}
