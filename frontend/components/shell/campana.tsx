"use client";

import { useCallback, useEffect, useState } from "react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { pedir } from "@/lib/cliente-api";

/** Espeja `NotificacionOut` de la API. */
export type Notificacion = {
  id: string;
  tipo: string;
  nivel: string;
  titulo: string;
  cuerpo: string | null;
  sucursal_id: string | null;
  leida_at: string | null;
  created_at: string;
};

/** Cada cuánto se vuelve a preguntar por la bandeja. Un minuto: la alerta de
 * pedido demorado nace de un barrido de Celery cada 5 min, así que refrescar
 * más seguido solo agrega peticiones sin adelantar ninguna noticia. El día
 * que exista push (ver ROADMAP) esto deja de ser el camino principal. */
const INTERVALO_MS = 60_000;

const COLOR_NIVEL: Record<string, string> = {
  critico: "text-secondary",
  alerta: "text-secondary",
  info: "text-gray",
};

function haceCuanto(iso: string): string {
  const minutos = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 60_000));
  if (minutos < 60) return `hace ${minutos} min`;
  const horas = Math.round(minutos / 60);
  if (horas < 24) return `hace ${horas} h`;
  return `hace ${Math.round(horas / 24)} d`;
}

/**
 * Bandeja de notificaciones en la barra superior.
 *
 * Solo muestra las **no leídas**: la campana responde "¿hay algo que
 * atender?", y una lista que mezcla lo ya visto obliga a releerla entera
 * para contestar eso. El histórico completo, si alguna vez hace falta, es
 * una pantalla aparte con su propio filtro.
 *
 * Marca leída al hacer click en la fila y no al abrir el panel: abrir para
 * mirar de reojo no es haberse enterado, y con lo segundo un aviso se pierde
 * por pasar el mouse.
 */
export function Campana() {
  const [items, setItems] = useState<Notificacion[]>([]);
  const [error, setError] = useState(false);

  const recargar = useCallback(async () => {
    try {
      const pagina = await pedir<{ items: Notificacion[] }>(
        "/notificaciones?solo_no_leidas=true&page_size=20",
      );
      setItems(pagina.items);
      setError(false);
    } catch {
      // Una campana que grita en rojo porque se cayó la red es peor que una
      // campana callada: se marca el estado y la próxima vuelta lo corrige.
      setError(true);
    }
  }, []);

  useEffect(() => {
    recargar();
    const id = setInterval(recargar, INTERVALO_MS);
    return () => clearInterval(id);
  }, [recargar]);

  async function marcarLeida(notificacionId: string) {
    setItems((previas) => previas.filter((n) => n.id !== notificacionId));
    try {
      await pedir(`/notificaciones/${notificacionId}/leer`, { metodo: "POST" });
    } catch {
      recargar();
    }
  }

  async function marcarTodas() {
    setItems([]);
    try {
      await pedir("/notificaciones/leer-todas", { metodo: "POST" });
    } catch {
      recargar();
    }
  }

  return (
    <Popover>
      <PopoverTrigger
        className="relative rounded p-1.5 text-dark hover:bg-cream"
        aria-label={
          items.length ? `Notificaciones: ${items.length} sin leer` : "Notificaciones"
        }
      >
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          className="h-5 w-5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.7 21a2 2 0 0 1-3.4 0" />
        </svg>
        {items.length > 0 && (
          <span className="absolute -right-0.5 -top-0.5 min-w-4 rounded-full bg-secondary px-1 text-center text-[10px] font-bold leading-4 text-white">
            {items.length > 9 ? "9+" : items.length}
          </span>
        )}
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 gap-0 p-0">
        <div className="flex items-center justify-between border-b border-gray/20 px-3 py-2">
          <span className="text-xs font-bold uppercase text-gray">Notificaciones</span>
          {items.length > 0 && (
            <button
              type="button"
              onClick={marcarTodas}
              className="text-xs font-semibold text-primary hover:underline"
            >
              Marcar todas
            </button>
          )}
        </div>
        {error && items.length === 0 ? (
          <p className="px-3 py-4 text-sm text-gray">No se pudo cargar la bandeja.</p>
        ) : items.length === 0 ? (
          <p className="px-3 py-4 text-sm text-gray">Sin novedades.</p>
        ) : (
          <ul className="max-h-80 overflow-y-auto">
            {items.map((n) => (
              <li key={n.id}>
                <button
                  type="button"
                  onClick={() => marcarLeida(n.id)}
                  className="flex w-full flex-col items-start gap-0.5 border-b border-gray/10 px-3 py-2 text-left hover:bg-cream"
                >
                  <span
                    className={`text-sm font-semibold ${COLOR_NIVEL[n.nivel] ?? "text-dark"}`}
                  >
                    {n.titulo}
                  </span>
                  {n.cuerpo && <span className="text-xs text-gray">{n.cuerpo}</span>}
                  <span className="text-[11px] text-gray">{haceCuanto(n.created_at)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </PopoverContent>
    </Popover>
  );
}
