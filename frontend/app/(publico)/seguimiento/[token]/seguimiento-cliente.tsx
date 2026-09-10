"use client";

import { useCallback, useEffect, useState } from "react";

import type { Punto } from "@/lib/geo";

import { consultarSeguimiento, type EstadoPublico, type Seguimiento } from "./actions";
import MapaSeguimiento from "./mapa-seguimiento";

/**
 * El estado del pedido y su mapa, sondeando el enlace público (RN-DLV-008).
 *
 * Mismo patrón que `app/kds/use-cola.ts`: intervalo + pausa en
 * `document.hidden`, para no gastar requests en una pestaña que nadie está
 * mirando. La diferencia es que acá el sondeo **se apaga solo** una vez que
 * el pedido llega a un estado final — entregado o no entregado no vuelven a
 * cambiar, y seguir preguntando cada 10 s no le sirve a nadie.
 */
const REFRESCO_MS = 10_000;

const TITULO_ESTADO: Record<EstadoPublico, string> = {
  preparando: "Estamos preparando tu pedido",
  en_camino: "Tu pedido está en camino",
  entregado: "¡Pedido entregado!",
  no_entregado: "No pudimos entregar tu pedido",
};

const LABEL_HITO: Record<string, string> = {
  en_camino: "Salió del local",
  entregado: "Entregado",
  no_entregado: "No se pudo entregar",
};

function hora(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit" });
}

function aPunto(
  lat: string | number | null | undefined,
  lng: string | number | null | undefined,
): Punto | null {
  const la = lat === null || lat === undefined ? NaN : Number(lat);
  const ln = lng === null || lng === undefined ? NaN : Number(lng);
  return Number.isFinite(la) && Number.isFinite(ln) ? { lat: la, lng: ln } : null;
}

function terminado(estado: EstadoPublico): boolean {
  return estado === "entregado" || estado === "no_entregado";
}

export default function SeguimientoCliente({
  token,
  inicial,
}: {
  token: string;
  inicial: Seguimiento;
}) {
  const [estado, setEstado] = useState(inicial);
  const [aviso, setAviso] = useState<string | null>(null);

  const refrescar = useCallback(async () => {
    try {
      const siguiente = await consultarSeguimiento(token);
      if (siguiente) {
        setEstado(siguiente);
        setAviso(null);
      } else {
        setAviso("Este enlace ya no está disponible.");
      }
    } catch {
      setAviso("No pudimos actualizar el estado. Seguimos intentando...");
    }
  }, [token]);

  useEffect(() => {
    if (terminado(estado.estado_publico)) return;
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
  }, [estado.estado_publico, refrescar]);

  const repartidorPunto = estado.posicion
    ? aPunto(estado.posicion.lat, estado.posicion.lng)
    : null;
  const destinoPunto = aPunto(estado.destino.lat, estado.destino.lng);

  return (
    <section className="seguimiento" aria-live="polite">
      <p className="seguimiento-estado">{TITULO_ESTADO[estado.estado_publico]}</p>

      {estado.repartidor ? (
        <p className="seguimiento-repartidor">Te lo lleva {estado.repartidor.nombre}.</p>
      ) : null}

      {estado.estado_publico === "en_camino" && estado.eta_at ? (
        <p className="seguimiento-eta">Llega aprox. a las {hora(estado.eta_at)}.</p>
      ) : null}

      <MapaSeguimiento repartidor={repartidorPunto} destino={destinoPunto} />

      {estado.linea_tiempo.length > 0 ? (
        <ol className="seguimiento-linea-tiempo">
          {estado.linea_tiempo.map((h) => (
            <li key={h.hito}>
              <span>{LABEL_HITO[h.hito] ?? h.hito}</span>
              {h.at ? <time>{hora(h.at)}</time> : null}
            </li>
          ))}
        </ol>
      ) : null}

      {aviso ? (
        <p className="publico-error" role="status">
          {aviso}
        </p>
      ) : null}
    </section>
  );
}
