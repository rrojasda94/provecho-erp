"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { ErrorApi } from "@/lib/cliente-api";
import { apiDelivery, type Tablero } from "@/lib/delivery";

/** Mismo criterio que `app/kds/use-cola.ts`: el estado real vive en el
 * backend (otro despachador o el repartidor mismo pueden tocar la ruta) y
 * el sondeo se pausa con la pestaña oculta. 10 s, como el KDS — acá
 * también se mira de pie, decidiendo a quién asignar lo que acaba de
 * salir de cocina. */
const REFRESCO_MS = 10_000;

export function useTablero(sucursalId: string, inicial: Tablero) {
  const [tablero, setTablero] = useState(inicial);

  // El servidor ya trae la primera foto; si cambia de sucursal (mismo
  // componente, otra navegación) hay que arrancar de la suya y no seguir
  // mostrando la anterior hasta el próximo sondeo.
  useEffect(() => {
    setTablero(inicial);
  }, [inicial]);

  const refrescar = useCallback(async () => {
    try {
      setTablero(await apiDelivery.tablero(sucursalId));
    } catch (e) {
      toast(e instanceof ErrorApi ? e.message : "Sin conexión con la API");
    }
  }, [sucursalId]);

  useEffect(() => {
    const id = setInterval(() => {
      if (!document.hidden) refrescar();
    }, REFRESCO_MS);
    const alVolver = () => {
      if (!document.hidden) refrescar();
    };
    document.addEventListener("visibilitychange", alVolver);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", alVolver);
    };
  }, [refrescar]);

  return { tablero, refrescar };
}
