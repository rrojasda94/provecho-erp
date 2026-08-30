/**
 * Lectura del error de la API: un texto que el usuario pueda leer y, cuando
 * el servidor los manda, los campos que rechazó.
 *
 * El parseo estaba duplicado byte por byte en `lib/api.ts` (servidor) y
 * `lib/cliente-api.ts` (navegador). Son dos clientes distintos a propósito
 * —el token vive en una cookie httpOnly y solo el de servidor lo tiene—,
 * pero **cómo se lee un error** no tiene por qué diferir entre los dos: la
 * copia que se quedara atrás iba a mostrar otra cosa para el mismo fallo.
 *
 * Sin imports, como `lib/carga.ts` y por lo mismo: lo usan los dos clientes
 * y se prueba con `node --test` sin arrastrar nada de Next.
 */

/** Un campo rechazado por el servidor (`errores[]` del 422). `campo` es el
 * nombre del dato en la API, que es también el `name` del input en el
 * formulario; `etiqueta` es cómo se llama en pantalla. */
export type ErrorCampo = { campo: string; etiqueta: string; mensaje: string };

/** Lo que devuelve toda Server Action de formulario del ERP. */
export type EstadoFormulario = { error: string; ok: boolean; campos?: ErrorCampo[] };

export const ESTADO_INICIAL: EstadoFormulario = { error: "", ok: false };

/**
 * Saca de una respuesta fallida el mensaje y los campos.
 *
 * El sobre del ERP es `{detail: string, errores?: ErrorCampo[]}` (ver
 * `src/core/validacion.py`). La rama de `detail` como **lista** es el
 * formato crudo de FastAPI y se conserva de respaldo: el hub de sucursal y
 * cualquier API vieja pueden seguir contestando así, y quedarse sin mensaje
 * es peor que un mensaje en inglés. Los `msg` ausentes se filtran — sin eso
 * el usuario leía "undefined; undefined".
 */
export async function leerError(
  respuesta: Response,
): Promise<{ mensaje: string; campos: ErrorCampo[] }> {
  try {
    const cuerpo = await respuesta.json();
    const campos: ErrorCampo[] = Array.isArray(cuerpo?.errores) ? cuerpo.errores : [];
    if (typeof cuerpo?.detail === "string") return { mensaje: cuerpo.detail, campos };
    if (Array.isArray(cuerpo?.detail)) {
      const mensajes = cuerpo.detail
        .map((d: { msg?: string }) => d?.msg)
        .filter((m: unknown): m is string => typeof m === "string");
      if (mensajes.length > 0) return { mensaje: mensajes.join("; "), campos };
    }
  } catch {
    // Cuerpo no-JSON: cae al mensaje genérico.
  }
  return { mensaje: `Error ${respuesta.status}`, campos: [] };
}

/** `ApiError` (servidor) y `ErrorApi` (navegador) son clases distintas en
 * módulos distintos. Se lee la forma —un `status` numérico— y no
 * `instanceof`, igual que en `lib/carga.ts`. */
function esDeLaApi(e: unknown): e is Error & { campos?: ErrorCampo[] } {
  return (
    e instanceof Error &&
    "status" in e &&
    typeof (e as { status: unknown }).status === "number"
  );
}

/**
 * Traduce lo que se haya lanzado al estado que devuelve una Server Action.
 *
 * `porDefecto` lo pone el llamador porque solo él sabe qué se estaba
 * intentando: un `TypeError: fetch failed` no le dice nada a un cajero.
 * Reemplaza el `function mensajeDe(e, porDefecto)` que estaba copiado en
 * quince `actions.ts` y que además tiraba a la basura los campos.
 */
export function estadoDeError(e: unknown, porDefecto: string): EstadoFormulario {
  if (!esDeLaApi(e)) return { error: porDefecto, ok: false };
  return { error: e.message || porDefecto, ok: false, campos: e.campos ?? [] };
}
