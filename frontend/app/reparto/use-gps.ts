"use client";

import { useEffect, useRef, useState } from "react";

import { distanciaMetros, type Punto } from "@/lib/geo";

/** Mínimo entre dos pings — el límite del servidor es 30 por minuto
 * (`consumir("posicion_gps", ..., 30, 60)`), y `watchPosition` puede
 * disparar varias veces por segundo en algunos teléfonos. */
const INTERVALO_MIN_MS = 10_000;
/** Y solo si de verdad se movió: sin esto, un repartidor parado en el
 * semáforo mandaría un ping cada diez segundos exactos con la misma
 * coordenada, que no le suma nada al trazo. */
const DISTANCIA_MIN_M = 30;

export type PosicionGps = Punto & { precision_m: number | null; registrado_at: string };

/**
 * Reporta la posición del repartidor mientras `activo` es verdadero, con el
 * throttle de arriba. El primer punto se manda siempre, apenas el GPS
 * contesta — es lo que le da al tablero de despacho y al enlace público
 * algo que mostrar antes de que pase el primer minuto de ruta.
 */
export function useGps(activo: boolean, onPosicion: (p: PosicionGps) => void) {
  const [error, setError] = useState<string | null>(null);
  const ultima = useRef<{ lat: number; lng: number; at: number } | null>(null);
  const onPosicionRef = useRef(onPosicion);
  useEffect(() => {
    onPosicionRef.current = onPosicion;
  }, [onPosicion]);

  useEffect(() => {
    if (!activo) {
      ultima.current = null;
      return;
    }
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setError("Este dispositivo no tiene GPS disponible.");
      return;
    }
    setError(null);
    const id = navigator.geolocation.watchPosition(
      (posicion) => {
        const ahora = Date.now();
        const lat = posicion.coords.latitude;
        const lng = posicion.coords.longitude;
        const previa = ultima.current;
        const corresponde =
          !previa ||
          (ahora - previa.at >= INTERVALO_MIN_MS &&
            distanciaMetros(previa, { lat, lng }) >= DISTANCIA_MIN_M);
        if (!corresponde) return;
        ultima.current = { lat, lng, at: ahora };
        onPosicionRef.current({
          lat,
          lng,
          precision_m: posicion.coords.accuracy ? Math.round(posicion.coords.accuracy) : null,
          registrado_at: new Date(posicion.timestamp).toISOString(),
        });
      },
      () => setError("No se pudo leer tu ubicación. Revisa el permiso de GPS."),
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15_000 },
    );
    return () => navigator.geolocation.clearWatch(id);
  }, [activo]);

  return { error };
}
