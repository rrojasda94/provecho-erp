/// <reference types="google.maps" />

/** Lo que se guarda además del texto: el ancla de la dirección en el mapa. */
export type Ubicacion = {
  ubicacion_place_id: string | null;
  ubicacion_lat: string | number | null;
  ubicacion_lng: string | number | null;
  ubicacion_plus_code: string | null;
  ubicacion_distrito: string | null;
};

export const UBICACION_VACIA: Ubicacion = {
  ubicacion_place_id: null,
  ubicacion_lat: null,
  ubicacion_lng: null,
  ubicacion_plus_code: null,
  ubicacion_distrito: null,
};

/** En Perú el distrito llega como `locality`; en zona rural, no siempre. */
const TIPOS_DISTRITO = [
  "locality",
  "administrative_area_level_3",
  "administrative_area_level_2",
];

const LARGO_DISTRITO = 100;
const LARGO_PLUS_CODE = 20;

/** Google devuelve los componentes en camelCase (Places) o snake (Geocoder). */
type ComponenteDireccion = {
  longText?: string | null;
  long_name?: string;
  types: string[];
};

export function distritoDe(
  componentes: readonly ComponenteDireccion[] | undefined | null,
): string | null {
  if (!componentes) return null;
  for (const tipo of TIPOS_DISTRITO) {
    const encontrado = componentes.find((c) => c.types?.includes(tipo));
    const nombre = encontrado?.longText ?? encontrado?.long_name;
    if (nombre) return nombre.slice(0, LARGO_DISTRITO);
  }
  return null;
}

/** Ubicación a partir de un lugar elegido en el autocompletado (Places). */
export function desdeLugar(lugar: google.maps.places.Place): Ubicacion {
  return {
    ubicacion_place_id: lugar.id ?? null,
    ubicacion_lat: lugar.location?.lat() ?? null,
    ubicacion_lng: lugar.location?.lng() ?? null,
    ubicacion_plus_code: lugar.plusCode?.globalCode?.slice(0, LARGO_PLUS_CODE) ?? null,
    ubicacion_distrito: distritoDe(
      lugar.addressComponents as unknown as ComponenteDireccion[],
    ),
  };
}

/** Ubicación a partir del punto donde quedó el pin (Geocoder inverso). */
export function desdeGeocode(
  resultado: google.maps.GeocoderResult,
  lat: number,
  lng: number,
): Ubicacion {
  return {
    ubicacion_place_id: resultado.place_id ?? null,
    ubicacion_lat: lat,
    ubicacion_lng: lng,
    ubicacion_plus_code:
      resultado.plus_code?.global_code?.slice(0, LARGO_PLUS_CODE) ?? null,
    ubicacion_distrito: distritoDe(
      resultado.address_components as unknown as ComponenteDireccion[],
    ),
  };
}

/** Recorta al ancla y nada más. Un objeto más gordo —un `ClienteBuscado`,
 * que es `... & Ubicacion`— pasa como `Ubicacion` sin que el tipo se queje,
 * y esparcirlo entero metía sus campos de más (`id`, `tipo`, `nombre`) en el
 * cuerpo de la venta. */
export function soloUbicacion(u: Ubicacion): Ubicacion {
  return {
    ubicacion_place_id: u.ubicacion_place_id,
    ubicacion_lat: u.ubicacion_lat,
    ubicacion_lng: u.ubicacion_lng,
    ubicacion_plus_code: u.ubicacion_plus_code,
    ubicacion_distrito: u.ubicacion_distrito,
  };
}

export function estaAnclada(u: Ubicacion): boolean {
  return u.ubicacion_lat !== null && u.ubicacion_lat !== undefined;
}

/** El par de coordenadas, si las dos son números usables. */
export function coordenadasDe(u: Ubicacion): { lat: number; lng: number } | null {
  const lat = Number(u.ubicacion_lat);
  const lng = Number(u.ubicacion_lng);
  if (!estaAnclada(u) || !Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  return { lat, lng };
}
