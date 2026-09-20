/// <reference types="google.maps" />

import { esConfiable } from "@/lib/direcciones";

import { desdeGeocode, desdeLugar, type Ubicacion } from "./ubicacion";

const CAMPOS_LUGAR: (
  | "formattedAddress"
  | "location"
  | "plusCode"
  | "addressComponents"
)[] = ["formattedAddress", "location", "plusCode", "addressComponents"];

const LARGO_MAXIMO = 5;

export type Sugerencia = {
  id: string;
  principal: string;
  secundario: string;
  texto: string;
  prediccion: google.maps.places.PlacePrediction;
};

export type Buscador = {
  buscar(texto: string): Promise<Sugerencia[]>;
  detalle(s: Sugerencia): Promise<{ texto: string; ancla: Ubicacion }>;
};

function aSugerencia(s: google.maps.places.AutocompleteSuggestion): Sugerencia | null {
  const prediccion = s.placePrediction;
  // Las sugerencias de tipo "query" (una búsqueda, no un lugar) no traen
  // predicción: no hay dirección detrás que se pueda anclar.
  if (!prediccion) return null;
  return {
    id: prediccion.placeId,
    principal: prediccion.mainText?.text ?? prediccion.text.text,
    secundario: prediccion.secondaryText?.text ?? "",
    texto: prediccion.text.text,
    prediccion,
  };
}

/**
 * Abre un buscador de lugares atado a una sola sesión de Places (ADR-072): el
 * token se crea con la primera tecla y se cierra al pedir el detalle de un
 * resultado, que es lo que hace que una búsqueda entera se cobre como una
 * sola y no como varias.
 *
 * Devuelve `null` si el canal de Google servido no trae `AutocompleteSuggestion`
 * — el `v=weekly` de `lib/google-maps.ts` puede ir por delante de los tipos
 * instalados. Sin este chequeo, un canal viejo revienta dentro del `.then` de
 * quien llama y el `.catch` silencioso de ADR-053 deja el mapa encendido sin
 * buscador ni explicación: el feature-detect es lo que mantiene la
 * degradación silenciosa que esa decisión pide.
 */
export async function abrirBuscador(
  maps: typeof google.maps,
  pais: string,
): Promise<Buscador | null> {
  const places = (await maps.importLibrary("places")) as google.maps.PlacesLibrary;
  if (!places.AutocompleteSuggestion || !places.AutocompleteSessionToken) return null;

  let sesion: google.maps.places.AutocompleteSessionToken | null = null;

  return {
    async buscar(texto) {
      sesion ??= new places.AutocompleteSessionToken();
      try {
        const { suggestions } =
          await places.AutocompleteSuggestion.fetchAutocompleteSuggestions({
            input: texto,
            includedRegionCodes: [pais],
            region: pais,
            language: "es",
            sessionToken: sesion,
          });
        return suggestions
          .map(aSugerencia)
          .filter((s): s is Sugerencia => s !== null)
          .slice(0, LARGO_MAXIMO);
      } catch {
        // Sin cuota, clave mal restringida o cualquier otro tropiezo de
        // Google: no puede romperle el tecleo al cajero (ADR-053).
        return [];
      }
    },

    async detalle(s) {
      const lugar = s.prediccion.toPlace();
      await lugar.fetchFields({ fields: CAMPOS_LUGAR });
      // La sesión termina acá: la próxima tecla abre una nueva.
      sesion = null;
      return { texto: lugar.formattedAddress ?? s.texto, ancla: desdeLugar(lugar) };
    },
  };
}

/** Geocode inverso del pin soltado a mano sobre el mapa. */
export async function direccionDePunto(
  maps: typeof google.maps,
  lat: number,
  lng: number,
): Promise<{ texto: string; ancla: Ubicacion } | null> {
  const { Geocoder } = (await maps.importLibrary(
    "geocoding",
  )) as google.maps.GeocodingLibrary;
  try {
    const { results } = await new Geocoder().geocode({ location: { lat, lng } });
    if (!results[0]) return null;
    return { texto: results[0].formatted_address, ancla: desdeGeocode(results[0], lat, lng) };
  } catch {
    return null;
  }
}

// El diálogo de delivery del PDV remonta el campo por pedido
// (`key={borrador?.id}`, `app/pdv/dialogos.tsx`): sin este cache, reabrir el
// mismo pedido repetiría el geocode del texto guardado cada vez.
const CACHE_TEXTO = new Map<string, Ubicacion | null>();
const TOPE_CACHE = 50;

/**
 * Geocode directo de un texto ya guardado, para colgarle un pin sin que
 * nadie lo haya elegido en el mapa (ADR-072). `null` si no hay resultado o si
 * `esConfiable` lo rechaza — anclar en silencio un punto dudoso sería peor
 * que no anclar, porque hay plata atada a él (ADR-054).
 */
export async function anclaDeTexto(
  maps: typeof google.maps,
  texto: string,
  pais: string,
): Promise<Ubicacion | null> {
  const clave = `${pais}|${texto}`;
  if (CACHE_TEXTO.has(clave)) return CACHE_TEXTO.get(clave) ?? null;

  const { Geocoder } = (await maps.importLibrary(
    "geocoding",
  )) as google.maps.GeocodingLibrary;
  let ancla: Ubicacion | null = null;
  try {
    const { results } = await new Geocoder().geocode({
      address: texto,
      region: pais,
      componentRestrictions: { country: pais },
    });
    const primero = results[0];
    if (primero && esConfiable(primero)) {
      const punto = primero.geometry.location;
      ancla = desdeGeocode(primero, punto.lat(), punto.lng());
    }
  } catch {
    ancla = null;
  }

  if (CACHE_TEXTO.size >= TOPE_CACHE) {
    const primeraClave = CACHE_TEXTO.keys().next().value;
    if (primeraClave !== undefined) CACHE_TEXTO.delete(primeraClave);
  }
  CACHE_TEXTO.set(clave, ancla);
  return ancla;
}
