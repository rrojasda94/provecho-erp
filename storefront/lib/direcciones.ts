/// <reference types="google.maps" />

/**
 * Reglas puras del campo de dirección unificado (ADR-072): cuándo un geocode
 * alcanza para anclar solo, y cómo se mueve el resaltado del desplegable de
 * sugerencias. Sin SDK ni React acá, para que se puedan probar sin Google.
 */

/** Un geocode con alguna de estas precisiones sí describe una puerta. */
const PRECISOS: readonly string[] = ["ROOFTOP", "RANGE_INTERPOLATED"];

/** Un resultado con alguno de estos tipos es un área, no una puerta: anclar
 * ahí fijaría el pin en el centro de un distrito entero. */
const TIPOS_VAGOS = [
  "locality",
  "sublocality",
  "postal_code",
  "country",
  "administrative_area_level_1",
  "administrative_area_level_2",
  "administrative_area_level_3",
];

/**
 * Si un geocode directo del texto ya guardado —sin que nadie haya elegido
 * nada en el mapa— alcanza para anclar solo. Hay plata atada a este punto
 * (ADR-054, el delivery se cobra por kilómetro), así que ante la duda no se
 * ancla:
 *
 * - `partial_match`: Google avisa que casó solo parte del texto.
 * - `location_type` fuera de ROOFTOP/RANGE_INTERPOLATED: se rechaza el
 *   centro geométrico de una calle o el centroide de una zona, que
 *   *parecen* anclados y son justo el caso que más plata haría perder.
 * - `types` vago: por si algo pasó las dos reglas anteriores y aun así es
 *   un distrito, una provincia o un país a secas.
 *
 * Nada de exigir un único resultado: Google devuelve más de uno para una
 * calle homónima en dos distritos, y ahí `partial_match` ya suele avisar.
 */
export function esConfiable(resultado: google.maps.GeocoderResult): boolean {
  if (resultado.partial_match) return false;
  if (!PRECISOS.includes(resultado.geometry.location_type)) return false;
  return !resultado.types.some((tipo) => TIPOS_VAGOS.includes(tipo));
}

/** A dónde se mueve el resaltado del listbox con una tecla. `-1` = ninguna
 * fila resaltada; envuelve en las dos puntas. */
export function siguienteActivo(activo: number, total: number, tecla: string): number {
  if (total <= 0) return -1;
  if (tecla === "ArrowDown") return (activo + 1) % total;
  if (tecla === "ArrowUp") return activo <= 0 ? total - 1 : activo - 1;
  return activo;
}
