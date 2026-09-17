"use client";

import { useEffect, useRef, useState } from "react";

import { cargarMaps } from "@/lib/google-maps";
import { filasDeHorario } from "@/lib/horario";

export type Sucursal = {
  id: string;
  nombre: string;
  direccion: string | null;
  telefono: string | null;
  horario_atencion: Record<string, [string, string][]> | null;
  lat: string | number | null;
  lng: string | number | null;
  abierto_ahora: boolean | null;
};

const CENTRO_TARAPOTO = { lat: -6.4886, lng: -76.3679 };

function MapaGoogle({ sucursales, apiKey, mapId }: { sucursales: Sucursal[]; apiKey: string; mapId: string }) {
  const contenedor = useRef<HTMLDivElement>(null);
  // Sin clave, el estado inicial ya es el de error: no hace falta que el
  // efecto llame a `setState` de forma síncrona en su primer render.
  const [error, setError] = useState<string | null>(apiKey ? null : "sin-clave");

  useEffect(() => {
    if (!apiKey) return;
    let cancelado = false;
    cargarMaps(apiKey)
      .then(async (maps) => {
        if (cancelado || !contenedor.current) return;
        const { Map } = (await maps.importLibrary("maps")) as google.maps.MapsLibrary;
        const { AdvancedMarkerElement } = (await maps.importLibrary(
          "marker",
        )) as google.maps.MarkerLibrary;

        const conCoordenadas = sucursales.filter((s) => s.lat != null && s.lng != null);
        const centro = conCoordenadas[0]
          ? { lat: Number(conCoordenadas[0].lat), lng: Number(conCoordenadas[0].lng) }
          : CENTRO_TARAPOTO;

        const mapa = new Map(contenedor.current, {
          center: centro,
          zoom: 14,
          mapId,
        });

        for (const s of conCoordenadas) {
          new AdvancedMarkerElement({
            map: mapa,
            position: { lat: Number(s.lat), lng: Number(s.lng) },
            title: s.nombre,
          });
        }
      })
      .catch(() => {
        if (!cancelado) setError("no-cargo");
      });
    return () => {
      cancelado = true;
    };
  }, [apiKey, mapId, sucursales]);

  if (error) {
    return (
      <div className="flex h-80 items-center justify-center rounded-lg border-2 border-negro bg-crema-2 text-sm text-humo">
        El mapa no está disponible ahora — mira la dirección de cada local abajo.
      </div>
    );
  }

  return <div ref={contenedor} className="h-80 w-full rounded-lg border-2 border-negro" />;
}

export function MapaLocales({
  sucursales,
  apiKey,
  mapId,
}: {
  sucursales: Sucursal[];
  apiKey: string;
  mapId: string;
}) {
  return (
    <div className="flex flex-col gap-6">
      <MapaGoogle sucursales={sucursales} apiKey={apiKey} mapId={mapId} />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {sucursales.map((s) => (
          <div key={s.id} className="sombra-dura rounded-lg border-2 border-negro bg-white p-4">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-negro">{s.nombre}</h2>
              {s.abierto_ahora !== null && (
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-bold ${
                    s.abierto_ahora ? "bg-verde text-negro" : "bg-negro text-crema"
                  }`}
                >
                  {s.abierto_ahora ? "Abierto" : "Cerrado"}
                </span>
              )}
            </div>
            {s.direccion && <p className="text-sm text-humo">{s.direccion}</p>}
            {s.telefono && <p className="text-sm text-humo">Tel. {s.telefono}</p>}
            <ul className="mt-2 text-xs text-humo">
              {filasDeHorario(s.horario_atencion).map((fila) => (
                <li key={fila.etiqueta} className="flex justify-between gap-2">
                  <span>{fila.etiqueta}</span>
                  <span>{fila.texto}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
        {sucursales.length === 0 && (
          <p className="col-span-full text-sm text-humo">No hay locales publicados todavía.</p>
        )}
      </div>
    </div>
  );
}
