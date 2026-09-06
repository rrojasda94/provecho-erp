/**
 * La fecha en hora del **negocio**, no la del proceso que la dibuja.
 *
 * Espejo de `src/shared/fechas.py`: la base guarda instantes en UTC, el
 * contenedor corre en UTC y el navegador corre en la zona del equipo. Solo
 * una de las tres es la del local. `toLocaleString("es-PE")` fija el
 * **idioma** y no la zona, así que una pantalla renderizada en el servidor
 * mostraba un movimiento de las 20:00 como la 01:00 del día siguiente.
 *
 * Por eso la zona viaja explícita y no se deja al reloj de quien formatea:
 * así vale igual en el servidor, en `npm run dev` y en una tablet mal
 * configurada.
 */

export const ZONA_NEGOCIO = "America/Lima";

/** Instante ISO (UTC o con offset) → fecha y hora del negocio. */
export function fechaHora(iso: string): string {
  return new Date(iso).toLocaleString("es-PE", { timeZone: ZONA_NEGOCIO });
}

/** Instante ISO → solo el día de calendario del negocio. */
export function fecha(iso: string): string {
  return new Date(iso).toLocaleDateString("es-PE", { timeZone: ZONA_NEGOCIO });
}

/** Hoy en la zona del negocio, como `YYYY-MM-DD`.
 *
 * Para el `defaultValue` de un `<input type="date">`, que exige ese formato.
 * `toISOString().slice(0, 10)` da el día **en UTC**: a las 19:00 de Lima ya es
 * el día siguiente, así que un formulario abierto de noche proponía mañana.
 */
export function hoyEnZonaDelNegocio(ahora: Date = new Date()): string {
  // `en-CA` porque su formato corto ya es `YYYY-MM-DD`; la zona es la que
  // importa, el idioma solo elige el orden de los números.
  return ahora.toLocaleDateString("en-CA", { timeZone: ZONA_NEGOCIO });
}

