"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { cargarMaps } from "@/lib/google-maps";

import { useConfigMapas } from "./config-mapas";

import {
  coordenadasDe,
  desdeGeocode,
  desdeLugar,
  estaAnclada,
  UBICACION_VACIA,
  type Ubicacion,
} from "./ubicacion";

export { UBICACION_VACIA, type Ubicacion };

const ZOOM_PUERTA = 17;

/** Por defecto nadie escucha. Una función vacía y no un `?.`: el opcional
 * suma una rama por cada llamada y el componente ya roza el tope de
 * complejidad del lint. */
const NADIE_ESCUCHA = () => {};

/** El evento del elemento de Google no está en los tipos de la librería. */
type EventoSeleccion = {
  placePrediction: { toPlace: () => google.maps.places.Place };
};

function CamposOcultos({ ancla }: { ancla: Ubicacion }) {
  // Vacío y no `null`: un `FormData` no sabe expresar null, y la Server
  // Action convierte el vacío en null antes de mandarlo a la API.
  return (
    <>
      {(Object.keys(UBICACION_VACIA) as (keyof Ubicacion)[]).map((campo) => (
        <input key={campo} type="hidden" name={campo} value={ancla[campo] ?? ""} />
      ))}
    </>
  );
}

/** El campo de texto y sus valores por defecto.

 * Vive aparte por el límite de complejidad del lint: cada valor por defecto
 * cuenta como una rama, y ocho de ellos en `CampoDireccion` dejaban a la
 * función en 12 sin una sola condición escrita a mano. Acá además quedan
 * juntos los cinco props que son pura presentación.
 */
function CampoTexto({
  campoRef,
  nombre = "direccion",
  etiqueta = "Dirección",
  requerido = false,
  claseCampo = "",
  claseEtiqueta = "flex flex-col gap-1 text-sm font-semibold",
  defaultValue = "",
  onInput,
}: {
  campoRef: React.RefObject<HTMLInputElement | null>;
  nombre?: string;
  etiqueta?: string;
  requerido?: boolean;
  claseCampo?: string;
  claseEtiqueta?: string;
  defaultValue?: string | null;
  onInput: (e: React.FormEvent<HTMLInputElement>) => void;
}) {
  return (
    <label className={claseEtiqueta}>
      {etiqueta}
      <input
        ref={campoRef}
        name={nombre}
        className={claseCampo}
        required={requerido}
        maxLength={255}
        defaultValue={defaultValue ?? ""}
        onInput={onInput}
      />
    </label>
  );
}

/** El `??` vive fuera del componente: adentro cuenta para su complejidad. */
function inicial(u: Ubicacion | null | undefined): Ubicacion {
  return u ?? UBICACION_VACIA;
}

/** El mapa solo existe con SDK cargado, y solo se ve con el pin puesto. */
function Mapa({
  contenedor,
  visible,
}: {
  contenedor: React.RefObject<HTMLDivElement | null>;
  visible: boolean;
}) {
  return (
    <div
      ref={contenedor}
      aria-hidden
      className={`w-full overflow-hidden rounded-lg border border-border ${
        visible ? "h-44" : "hidden"
      }`}
    />
  );
}

function mensaje(aviso: string, anclada: boolean, conMapa: boolean): string {
  if (aviso) return aviso;
  if (anclada) return "Anclada en el mapa. Arrastra el pin si la puerta está a media cuadra.";
  if (conMapa) return "Busca la dirección arriba, o escríbela a mano si Google no la conoce.";
  return "Escribe la dirección. El mapa no está disponible.";
}

/**
 * Campo de dirección anclado a Google Maps (ADR-053).
 *
 * Tres piezas que se leen de arriba abajo:
 *
 * 1. **Buscador de Google** — aparece solo si el SDK cargó. Al elegir una
 *    sugerencia escribe el texto, guarda el ancla y centra el pin.
 * 2. **El campo de verdad** — un `<input>` normal, siempre editable, que es
 *    lo que viaja en el `FormData`. Se puede teclear una dirección que Google
 *    no conoce: en Tarapoto hay varias, y un alta no puede depender de que un
 *    tercero conteste (mismo criterio que ADR-005 y ADR-041).
 * 3. **El mapa** — con el pin arrastrable, para corregir la puerta exacta
 *    cuando Google deja el punto a media cuadra.
 *
 * Dos cajas y no una, igual que `BuscarDocumento` es un botón aparte de los
 * campos que rellena: una busca, la otra guarda y se puede corregir. Meter
 * las dos funciones en un solo control es lo que obliga a elegir entre "solo
 * direcciones que Google conozca" y "sin autocompletado".
 *
 * **Editar el texto a mano suelta el pin.** Si el texto dijera una calle y
 * las coordenadas otra, el reparto iría al lugar equivocado y cobraría la
 * distancia equivocada. El backend aplica la misma regla por su cuenta
 * (`shared/ubicacion.py`): esto es la versión visible, no la que manda.
 *
 * Se monta dentro de los formularios NO controlados del ERP (`defaultValue` +
 * `name`, ver `dialogo-formulario`): el texto y los cinco ocultos son campos
 * del `<form>` que lo contiene y se envían solos.
 */
export function CampoDireccion({
  ubicacion,
  onCambio = NADIE_ESCUCHA,
  ...presentacion
}: {
  /** `name` del campo de texto. El de los ocultos es fijo. */
  nombre?: string;
  etiqueta?: string;
  requerido?: boolean;
  defaultValue?: string | null;
  ubicacion?: Ubicacion | null;
  /** Para los formularios que NO son `<form>` — el PDV lleva el pedido en
   * estado de React, no en campos del DOM. */
  onCambio?: (texto: string, ubicacion: Ubicacion) => void;
  /** El PDV tiene su propia paleta y sus propias clases (`pdv-campo`). */
  claseCampo?: string;
  claseEtiqueta?: string;
}) {
  // Del contexto y no de props: la clave la lee el servidor y el layout la
  // baja una sola vez (`components/direccion/config-mapas`).
  const { apiKey, mapId, pais } = useConfigMapas();
  const paisBuscado = pais || "pe";
  const [ancla, setAncla] = useState<Ubicacion>(inicial(ubicacion));
  const [conMapa, setConMapa] = useState(false);
  const [aviso, setAviso] = useState("");

  const inputRef = useRef<HTMLInputElement>(null);
  const buscadorRef = useRef<HTMLDivElement>(null);
  const mapaRef = useRef<HTMLDivElement>(null);
  const mapa = useRef<google.maps.Map | null>(null);
  const pin = useRef<google.maps.marker.AdvancedMarkerElement | null>(null);

  /** Escribe en el DOM y no en estado: el campo es no controlado. */
  const escribirTexto = useCallback((texto: string) => {
    if (inputRef.current) inputRef.current.value = texto;
  }, []);

  /** Pin soltado en otro punto: se pregunta qué dirección hay ahí. */
  const reubicar = useCallback(
    async (lat: number, lng: number) => {
      const maps = window.google?.maps;
      if (!maps) return;
      const { Geocoder } = (await maps.importLibrary(
        "geocoding",
      )) as google.maps.GeocodingLibrary;
      try {
        const { results } = await new Geocoder().geocode({ location: { lat, lng } });
        if (!results[0]) return;
        escribirTexto(results[0].formatted_address);
        const movida = desdeGeocode(results[0], lat, lng);
        setAncla(movida);
        onCambio(results[0].formatted_address, movida);
        setAviso("Pin movido: revisa la dirección antes de guardar.");
      } catch {
        // Mover el pin sin poder nombrar la dirección es peor que no
        // haberlo movido: el texto quedaría contando otra historia.
        setAviso("No se pudo leer la dirección de ese punto.");
      }
    },
    [escribirTexto, onCambio],
  );

  const crearMapa = useCallback(
    async (posicion: google.maps.LatLngLiteral) => {
      const maps = window.google.maps;
      const { Map } = (await maps.importLibrary("maps")) as google.maps.MapsLibrary;
      const { AdvancedMarkerElement } = (await maps.importLibrary(
        "marker",
      )) as google.maps.MarkerLibrary;
      mapa.current = new Map(mapaRef.current as HTMLElement, {
        center: posicion,
        zoom: ZOOM_PUERTA,
        mapId,
        disableDefaultUI: true,
        zoomControl: true,
      });
      pin.current = new AdvancedMarkerElement({
        map: mapa.current,
        position: posicion,
        gmpDraggable: true,
      });
      // Solo al soltar: el geocode inverso se cobra por llamada y arrastrar
      // dispara cientos de eventos.
      pin.current.addListener("dragend", () => {
        const p = pin.current?.position;
        if (p) void reubicar(Number(p.lat), Number(p.lng));
      });
    },
    [mapId, reubicar],
  );

  const moverPin = useCallback(
    async (lat: number, lng: number) => {
      if (!window.google?.maps || !mapaRef.current) return;
      const posicion = { lat, lng };
      if (!mapa.current) await crearMapa(posicion);
      mapa.current?.setCenter(posicion);
      if (pin.current) pin.current.position = posicion;
    },
    [crearMapa],
  );

  const elegir = useCallback(
    async (evento: Event) => {
      const { placePrediction } = evento as unknown as EventoSeleccion;
      const lugar = placePrediction.toPlace();
      await lugar.fetchFields({
        fields: ["formattedAddress", "location", "plusCode", "addressComponents"],
      });
      const texto = lugar.formattedAddress ?? "";
      escribirTexto(texto);
      const nueva = desdeLugar(lugar);
      setAncla(nueva);
      onCambio(texto, nueva);
      setAviso("");
      const punto = coordenadasDe(nueva);
      if (punto) void moverPin(punto.lat, punto.lng);
    },
    [escribirTexto, moverPin, onCambio],
  );

  // Monta el buscador de Google. Si el SDK no carga —sin clave, sin internet,
  // clave restringida a otro dominio— no pasa nada: queda el campo de texto,
  // que es todo lo que había antes de esta integración.
  useEffect(() => {
    let vivo = true;
    cargarMaps(apiKey)
      .then(async (maps) => {
        if (!vivo || !buscadorRef.current) return;
        const { PlaceAutocompleteElement } = (await maps.importLibrary(
          "places",
        )) as google.maps.PlacesLibrary;
        const buscador = new PlaceAutocompleteElement({
          includedRegionCodes: [paisBuscado],
        });
        buscador.placeholder = "Buscar dirección en Google Maps...";
        buscador.style.width = "100%";
        buscadorRef.current.replaceChildren(buscador);
        buscador.addEventListener("gmp-select", elegir as EventListener);
        setConMapa(true);
      })
      .catch((error) => {
        // Al usuario no se le dice nada —no hay nada que pueda hacer y el
        // formulario funciona igual—, pero a la consola sí: el `catch` mudo
        // hacía que "sin clave", "clave restringida a otro dominio" y "el SDK
        // cargó pero el buscador reventó" se vieran los tres iguales, y esa
        // ceguera costó tres intentos de arreglar lo mismo (ADR-072).
        //
        // `warn` y no `error`: quedarse sin mapa es un estado previsto —el hub
        // de una sucursal sin internet corre así siempre (ADR-053)—, y un
        // `error` por diseño es el que se aprende a ignorar.
        console.warn("[direccion] el buscador de Google no se montó:", error);
      });
    return () => {
      vivo = false;
    };
  }, [apiKey, paisBuscado, elegir]);

  // Pin inicial de una ficha que ya venía anclada.
  const puntoInicial = coordenadasDe(ancla);
  useEffect(() => {
    if (conMapa && puntoInicial) void moverPin(puntoInicial.lat, puntoInicial.lng);
    // Solo al aparecer el mapa: después el pin lo mueven la búsqueda y el
    // arrastre, que ya llaman a `moverPin` por su cuenta.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conMapa]);

  const anclada = estaAnclada(ancla);

  return (
    <div className="flex flex-col gap-1.5">
      {/* Sin condicionar a `conMapa`: el efecto que activa `conMapa` necesita
          que este `<div>` ya exista para engancharle el buscador
          (`buscadorRef.current`). Condicionarlo era un huevo-y-gallina que
          dejaba el mapa sin encenderse nunca, con clave o sin ella — el
          contenedor solo aparecía cuando `conMapa` era `true`, y `conMapa`
          solo se volvía `true` si el contenedor ya existía. Vacío no ocupa
          espacio visible, así que no hay nada que mostrar de más mientras el
          SDK no cargó. */}
      <div ref={buscadorRef} className="w-full" />

      <CampoTexto
        {...presentacion}
        campoRef={inputRef}
        onInput={(e) => {
          // Texto tecleado a mano: el pin viejo ya no es de esta dirección.
          onCambio(e.currentTarget.value, UBICACION_VACIA);
          if (!anclada) return;
          setAncla(UBICACION_VACIA);
          setAviso("Dirección escrita a mano: queda sin punto en el mapa.");
        }}
      />

      <CamposOcultos ancla={ancla} />

      {conMapa && <Mapa contenedor={mapaRef} visible={anclada} />}

      <p className="text-xs text-muted-foreground" role="status">
        {mensaje(aviso, anclada, conMapa)}
      </p>
    </div>
  );
}
