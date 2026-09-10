"use client";

import { useEffect, useRef } from "react";

/**
 * Mantiene la pantalla encendida mientras `activo` es verdadero — sin esto
 * el teléfono se apaga a los pocos segundos en el bolsillo y el repartidor
 * pierde el mapa y el aviso de la próxima parada en cada semáforo.
 *
 * Sin service worker (ADR-013): la Wake Lock API no lo necesita, y
 * degradarse en silencio si el navegador no la soporta —o la niega por
 * batería baja— es el mismo criterio que `lib/camara.ts` con la cámara:
 * nunca bloquea la ruta.
 */
export function useWakeLock(activo: boolean): void {
  const candado = useRef<WakeLockSentinel | null>(null);

  useEffect(() => {
    if (!activo || typeof navigator === "undefined" || !("wakeLock" in navigator)) return;
    let cancelado = false;

    const pedir = async () => {
      try {
        const nuevo = await navigator.wakeLock.request("screen");
        if (cancelado) {
          nuevo.release().catch(() => {});
          return;
        }
        candado.current = nuevo;
      } catch {
        // Batería baja, o el navegador lo niega: la ruta sigue igual.
      }
    };
    pedir();

    // El candado se libera solo al ocultar la pestaña (cambiar de app,
    // apagar la pantalla a mano): hay que volver a pedirlo al regresar.
    const alVolver = () => {
      if (document.visibilityState === "visible" && !candado.current) pedir();
    };
    document.addEventListener("visibilitychange", alVolver);

    return () => {
      cancelado = true;
      document.removeEventListener("visibilitychange", alVolver);
      candado.current?.release().catch(() => {});
      candado.current = null;
    };
  }, [activo]);
}
