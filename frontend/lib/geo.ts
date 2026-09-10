/**
 * Cálculos geográficos que corren en el cliente, sin llamar a Google.
 *
 * `distanciaMetros` espeja `src/shared/ubicacion.py::metros_entre` (mismo
 * radio de la Tierra, mismo Haversine): es la única cuenta que backend y
 * frontend hacen las dos, y por eso replica la fórmula en vez de pedirle a
 * la API un número para pintar un mapa.
 *
 * `decodificarPolyline` lee el `encodedPolyline` que devuelve
 * `computeRoutes` (`src/shared/integrations/google/rutas.py::ruta_optima`)
 * para dibujar la ruta en el tablero de despacho. El enlace público de
 * seguimiento no la usa — RN-DLV-008 la excluye del `SeguimientoOut` a
 * propósito, porque revela las demás paradas de la salida.
 */

const RADIO_TIERRA_M = 6_371_000;

export type Punto = { lat: number; lng: number };

function radianes(grados: number): number {
  return (grados * Math.PI) / 180;
}

export function distanciaMetros(a: Punto, b: Punto): number {
  const dLat = radianes(b.lat - a.lat);
  const dLng = radianes(b.lng - a.lng);
  const la1 = radianes(a.lat);
  const la2 = radianes(b.lat);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(la1) * Math.cos(la2) * Math.sin(dLng / 2) ** 2;
  return Math.round(2 * RADIO_TIERRA_M * Math.asin(Math.sqrt(h)));
}

/** Un tramo del algoritmo estándar de Google (variable-length, base64 con
 * offset 63, zigzag) — lee desde `desde` y devuelve el valor y por dónde
 * seguir, para que `decodificarPolyline` no repita el bucle dos veces por
 * punto (uno para latitud, otro para longitud). */
function leerValor(codificada: string, desde: number): { valor: number; siguiente: number } {
  let resultado = 0;
  let desplazamiento = 0;
  let indice = desde;
  let byte: number;
  do {
    byte = codificada.charCodeAt(indice++) - 63;
    resultado |= (byte & 0x1f) << desplazamiento;
    desplazamiento += 5;
  } while (byte >= 0x20);
  const valor = resultado & 1 ? ~(resultado >> 1) : resultado >> 1;
  return { valor, siguiente: indice };
}

/** Precisión estándar de Google Polyline: 1e-5 grados por unidad. */
const FACTOR_PRECISION = 1e5;

export function decodificarPolyline(codificada: string): Punto[] {
  const puntos: Punto[] = [];
  let indice = 0;
  let lat = 0;
  let lng = 0;

  while (indice < codificada.length) {
    const dLat = leerValor(codificada, indice);
    lat += dLat.valor;
    const dLng = leerValor(codificada, dLat.siguiente);
    lng += dLng.valor;
    indice = dLng.siguiente;
    puntos.push({ lat: lat / FACTOR_PRECISION, lng: lng / FACTOR_PRECISION });
  }
  return puntos;
}
