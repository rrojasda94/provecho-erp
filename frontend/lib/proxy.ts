/**
 * Cliente de la API visto desde el NAVEGADOR: todo pasa por `/api/proxy`
 * (ver `app/api/proxy/[...ruta]/route.ts`), que adjunta el token desde la
 * cookie httpOnly. El token nunca llega al JavaScript de la página.
 *
 * Lo usan las pantallas intensamente interactivas —PDV, ficha de producto—
 * donde una Server Action por tecla pagaría un round-trip de renderizado.
 * El resto de pantallas sigue usando `lib/api.ts` desde el servidor.
 */

const BASE = "/api/proxy/api/v1";

export class ErrorApi extends Error {
  status: number;

  constructor(status: number, mensaje: string) {
    super(mensaje);
    this.status = status;
  }
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
