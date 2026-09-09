"use client";

import { useCallback, useEffect, useState } from "react";

import { RegionDeAviso } from "@/components/estado/region-de-aviso";
import { ErrorApi } from "@/lib/cliente-api";
import { apiDelivery, type RutaConParadas } from "@/lib/delivery";

import RutaCliente from "./ruta-cliente";

/** Mismo criterio que `app/kds/use-cola.ts`: se sondea porque el estado
 * real vive en el backend (otro repartidor no, pero un despachador puede
 * tocar la ruta desde el tablero) y se pausa con la pestaña oculta. 15 s y
 * no 3 como el KDS: acá no hay una cocina completa mirando la pantalla, es
 * un repartidor que la revisa cada tanto. */
const REFRESCO_MS = 15_000;

/** La ruta que importa mostrar ahora: la que está en curso o, si no hay
 * ninguna, la próxima planificada. Un repartidor casi siempre tiene una
 * sola ruta viva a la vez — si alguna vez tuviera dos, esto elige cuál se
 * ve primero sin obligarlo a un selector que en la práctica no usaría. */
function rutaActiva(rutas: RutaConParadas[]): RutaConParadas | null {
  return rutas.find((r) => r.estado === "en_curso") ?? rutas[0] ?? null;
}

export default function RepartoCliente({ inicial }: { inicial: RutaConParadas[] }) {
  const [rutas, setRutas] = useState(inicial);
  const [aviso, setAviso] = useState<string | null>(null);

  const refrescar = useCallback(async () => {
    try {
      setRutas(await apiDelivery.misRutas());
    } catch (e) {
      setAviso(e instanceof ErrorApi ? e.message : "Sin conexión con la API");
    }
  }, []);

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

  useEffect(() => {
    if (!aviso) return;
    const id = setTimeout(() => setAviso(null), 4000);
    return () => clearTimeout(id);
  }, [aviso]);

  const activa = rutaActiva(rutas);

  return (
    <main className="reparto">
      <header className="reparto-top">
        <strong>Mi reparto</strong>
      </header>

      {activa ? (
        <RutaCliente ruta={activa} onCambio={refrescar} />
      ) : (
        <p className="reparto-nada">No tienes rutas asignadas por ahora.</p>
      )}

      <RegionDeAviso texto={aviso} clase="reparto-aviso" />
    </main>
  );
}
