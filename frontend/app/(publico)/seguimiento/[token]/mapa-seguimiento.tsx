"use client";

import { useEffect, useRef, useState } from "react";

import { useConfigMapas } from "@/components/direccion/config-mapas";
import { cargarMaps } from "@/lib/google-maps";
import type { Punto } from "@/lib/geo";

const ZOOM_RUTA = 15;

type Marcadores = {
  mapa: google.maps.Map;
  repartidor: google.maps.marker.AdvancedMarkerElement | null;
  destino: google.maps.marker.AdvancedMarkerElement | null;
};

async function crearMapa(
  contenedor: HTMLDivElement,
  apiKey: string,
  mapId: string,
  centro: Punto,
): Promise<Marcadores> {
  const maps = await cargarMaps(apiKey);
  const { Map } = (await maps.importLibrary("maps")) as google.maps.MapsLibrary;
  await maps.importLibrary("marker");
  const mapa = new Map(contenedor, {
    center: centro,
    zoom: ZOOM_RUTA,
    mapId,
    disableDefaultUI: true,
    zoomControl: true,
  });
  return { mapa, repartidor: null, destino: null };
}

/**
 * Mapa del enlace público: dos marcadores fijos —repartidor y destino—, sin
 * la polilínea de la ruta. No es un olvido: `SeguimientoOut` no la trae,
 * porque RN-DLV-008 la excluye a propósito (revelaría las demás paradas de
 * la salida a quien reenvíe el link).
 *
 * Se degrada a nada sin clave de Maps configurada, igual que
 * `CampoDireccion` (ADR-053): el cliente igual ve el estado y el ETA en
 * texto en `SeguimientoCliente`.
 */
export default function MapaSeguimiento({
  repartidor,
  destino,
}: {
  repartidor: Punto | null;
  destino: Punto | null;
}) {
  const { apiKey, mapId } = useConfigMapas();
  const contenedorRef = useRef<HTMLDivElement>(null);
  const marcadores = useRef<Marcadores | null>(null);
  const [listo, setListo] = useState(false);

  useEffect(() => {
    const centro = repartidor ?? destino;
    if (!apiKey || !contenedorRef.current || marcadores.current || !centro) return;
    let cancelado = false;
    crearMapa(contenedorRef.current, apiKey, mapId, centro)
      .then((creado) => {
        if (cancelado) return;
        marcadores.current = creado;
        setListo(true);
      })
      .catch(() => {
        // Sin internet o clave rechazada: se queda sin mapa, con el texto
        // del estado y el ETA — nunca rompe la pantalla por esto.
      });
    return () => {
      cancelado = true;
    };
  }, [apiKey, mapId, repartidor, destino]);

  useEffect(() => {
    const activos = marcadores.current;
    if (!listo || !activos) return;
    const { AdvancedMarkerElement, PinElement } = window.google.maps.marker;
    if (destino && !activos.destino) {
      const pin = new PinElement({ background: "#57534e", borderColor: "#292524" });
      activos.destino = new AdvancedMarkerElement({
        map: activos.mapa,
        position: destino,
        content: pin.element,
      });
    }
    if (repartidor) {
      if (!activos.repartidor) {
        activos.repartidor = new AdvancedMarkerElement({
          map: activos.mapa,
          position: repartidor,
        });
      } else {
        activos.repartidor.position = repartidor;
      }
      activos.mapa.panTo(repartidor);
    }
  }, [listo, repartidor, destino]);

  if (!apiKey) return null;
  return <div ref={contenedorRef} className="seguimiento-mapa" aria-label="Mapa de seguimiento" />;
}
