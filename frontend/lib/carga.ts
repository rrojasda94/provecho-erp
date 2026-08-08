/**
 * Distinguir "no hay datos" de "no se pudieron traer".
 *
 * Hasta 2026-08-07 varias cargas hacían `.catch(() => setLista([]))`: un 500
 * o una red caída se dibujaban exactamente igual que un día sin ventas. Eso
 * convirtió un fallo real del PDV —una venta con pago dividido que no salía
 * en la pestaña "Cobrados"— en algo indiagnosticable desde la pantalla: la
 * venta estaba en la base, el fetch fallaba y la lista salía vacía.
 *
 * Sin imports a propósito: lo usan los dos clientes HTTP del proyecto
 * (`lib/api.ts` en el servidor, `lib/cliente-api.ts` en el navegador) y se
 * prueba con `node --test` sin arrastrar nada de Next.
 */

/** Motivo por el que una carga no se pudo completar.
 *
 * `mensaje` es lo que lee el usuario; `detalle` es lo que dijo el servidor
 * (o la excepción) y se muestra en letra chica — el bug que motivó esto era
 * indiagnosticable justo por no tener eso a la vista. `status` es `null`
 * cuando ni siquiera hubo respuesta (red caída, DNS, proxy): ese caso es el
 * que no hay que confundir con un "no te toca". */
export type Falla = { mensaje: string; detalle: string | null; status: number | null };

/** Una lista traída del servidor: sus filas, el motivo si no se pudieron
 * traer, y cómo volver a intentarlo. Se pasa entera a los componentes para
 * que ninguno pueda renderizar las filas sin haber mirado la falla. */
export type Lista<T> = { datos: T[]; falla: Falla | null; recargar: () => void };

/** `ApiError` (servidor) y `ErrorApi` (navegador) son clases distintas en
 * módulos distintos. Se lee la forma —un `status` numérico— en vez de
 * `instanceof` para no atar este archivo a ninguna de las dos. */
function statusDe(e: unknown): number | null {
  if (typeof e === "object" && e !== null && "status" in e) {
    const status = (e as { status: unknown }).status;
    if (typeof status === "number") return status;
  }
  return null;
}

/** Traduce lo que sea que se haya lanzado a algo que el usuario pueda leer.
 * `mensaje` lo pone el llamador porque solo él sabe qué se estaba trayendo:
 * un `TypeError: fetch failed` no le dice nada a un cajero. */
export function fallaDe(e: unknown, mensaje: string): Falla {
  return {
    mensaje,
    detalle: e instanceof Error && e.message ? e.message : null,
    status: statusDe(e),
  };
}

/** 403 es el servidor contestando "no te toca": el bloque se oculta y ya.
 * Cualquier otra cosa —red, 5xx, 401— es "no se pudo preguntar", y eso sí
 * hay que decirlo: tragárselo es lo que hace que un tablero en blanco
 * parezca un permiso faltante. */
export function esSinPermiso(falla: Falla | null): boolean {
  return falla?.status === 403;
}
