"use client";

import { useEffect, useRef, useState } from "react";

import { useConfigMapas } from "@/components/direccion/config-mapas";
import type { RutaConParadas } from "@/lib/delivery";
import { decodificarPolyline, type Punto } from "@/lib/geo";
import { cargarMaps } from "@/lib/google-maps";

const ZOOM_RUTA = 13;

function aPunto(lat: string | number | null, lng: string | number | null): Punto | null {
  if (lat === null || lng === null) return null;
  const la = Number(lat);
  const ln = Number(lng);
  return Number.isFinite(la) && Number.isFinite(ln) ? { lat: la, lng: ln } : null;
}

type Instancia = {
  mapa: google.maps.Map;
  repartidor: google.maps.marker.AdvancedMarkerElement | null;
};

/**
 * Arma el mapa una sola vez: origen, cada parada numerada y la polilínea
 * real cuando la ruta se optimizó con Google (`ruteo.py` — la heurística
 * ordena las paradas pero no calcula calles, así que ahí solo hay pines).
 * El marcador del repartidor se crea acá pero se mueve aparte, en cada
 * sondeo del tablero —ésto no se vuelve a llamar solo porque cambió su
 * posición.
 */
async function crearMapa(
  contenedor: HTMLDivElement,
  apiKey: string,
  mapId: string,
  ruta: RutaConParadas,
): Promise<Instancia | null> {
  const origen = aPunto(ruta.origen_lat, ruta.origen_lng);
  if (!origen) return null;
  const maps = await cargarMaps(apiKey);
  const { Map } = (await maps.importLibrary("maps")) as google.maps.MapsLibrary;
  const { AdvancedMarkerElement, PinElement } = (await maps.importLibrary(
    "marker",
  )) as google.maps.MarkerLibrary;

  const mapa = new Map(contenedor, {
    center: origen,
    zoom: ZOOM_RUTA,
    mapId,
    disableDefaultUI: true,
    zoomControl: true,
  });

  new AdvancedMarkerElement({
    map: mapa,
    position: origen,
    content: new PinElement({ background: "#57534e", borderColor: "#292524" }).element,
  });

  for (const parada of ruta.paradas) {
    const destino = aPunto(parada.destino_lat, parada.destino_lng);
    if (!destino) continue;
    new AdvancedMarkerElement({
      map: mapa,
      position: destino,
      content: new PinElement({ glyph: String(parada.orden_parada ?? "?") }).element,
    });
  }

  if (ruta.polyline) {
    new google.maps.Polyline({
      path: decodificarPolyline(ruta.polyline),
      map: mapa,
      strokeColor: "#f4511e",
      strokeOpacity: 0.85,
      strokeWeight: 3,
    });
  }

  const repartidorInicial = aPunto(ruta.ultima_lat, ruta.ultima_lng);
  const repartidor = repartidorInicial
    ? new AdvancedMarkerElement({ map: mapa, position: repartidorInicial })
    : null;

  return { mapa, repartidor };
}

/**
 * El mapa de una ruta para el tablero de despacho. Se degrada a nada sin
 * clave de Maps configurada, igual que `CampoDireccion` (ADR-053) y el
 * mapa del enlace público: la tarjeta sigue funcionando con la lista de
 * paradas.
 */
export default function MapaRutas({ ruta }: { ruta: RutaConParadas }) {
  const { apiKey, mapId } = useConfigMapas();
  const contenedorRef = useRef<HTMLDivElement>(null);
  const instancia = useRef<Instancia | null>(null);
  const [listo, setListo] = useState(false);

  useEffect(() => {
    if (!apiKey || !contenedorRef.current) return;
    let cancelado = false;
    crearMapa(contenedorRef.current, apiKey, mapId, ruta)
      .then((creada) => {
        if (cancelado || !creada) return;
        instancia.current = creada;
        setListo(true);
      })
      .catch(() => {
        // Sin internet o clave rechazada: la tarjeta sigue con su lista
        // de paradas, sin mapa.
      });
    return () => {
      cancelado = true;
    };
    // Solo arma el mapa una vez por ruta: reordenar paradas o mover al
    // repartidor no lo reconstruye, ver el efecto de abajo.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiKey, mapId, ruta.id]);

  useEffect(() => {
    const activa = instancia.current;
    const repartidor = aPunto(ruta.ultima_lat, ruta.ultima_lng);
    if (!listo || !activa || !repartidor) return;
    if (activa.repartidor) {
      activa.repartidor.position = repartidor;
    } else {
      // La ruta no tenía posición cuando se armó el mapa (recién salió):
      // el primer ping del repartidor crea el marcador acá en vez de
      // esperar a que la tarjeta se cierre y se vuelva a abrir.
      activa.repartidor = new google.maps.marker.AdvancedMarkerElement({
        map: activa.mapa,
        position: repartidor,
      });
    }
  }, [listo, ruta.ultima_lat, ruta.ultima_lng]);

  if (!apiKey) return null;
  return (
    <div
      ref={contenedorRef}
      className="h-64 w-full rounded-lg border border-border"
      aria-label="Mapa de la ruta"
    />
  );
}
