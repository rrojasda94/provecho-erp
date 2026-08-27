"use client";

import { useCallback, useRef } from "react";

const ZOOM_PUERTA = 17;

/**
 * El mapa con el pin arrastrable de `CampoDireccion` (ADR-053). Aparte del
 * componente por el límite de complejidad del linter: sin JSX, `crearMapa` y
 * `moverPin` no le suman nada a la cuenta de `CampoDireccion`.
 */
export function useMapaPin({
  mapId,
  alSoltar,
}: {
  mapId: string;
  /** El pin se soltó en otro punto: hay que preguntar qué dirección hay ahí. */
  alSoltar: (lat: number, lng: number) => void;
}) {
  const mapaRef = useRef<HTMLDivElement>(null);
  const mapa = useRef<google.maps.Map | null>(null);
  const pin = useRef<google.maps.marker.AdvancedMarkerElement | null>(null);

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
        if (p) alSoltar(Number(p.lat), Number(p.lng));
      });
    },
    [mapId, alSoltar],
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

  return { mapaRef, moverPin };
}
