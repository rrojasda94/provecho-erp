"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ETIQUETA_ESTADO_ENTREGA, type RutaConParadas } from "@/lib/delivery";

import AvisoParada from "./aviso-parada";
import MapaRutas from "./mapa-rutas";

const ETIQUETA_ESTADO_RUTA: Record<string, string> = {
  planificada: "Por salir",
  en_curso: "En ruta",
  finalizada: "Finalizada",
  cancelada: "Cancelada",
};

function resuelta(estado: string): boolean {
  return estado === "entregada" || estado === "fallida" || estado === "cancelada";
}

export default function TarjetaRuta({
  ruta,
  puedeDespachar,
  onCancelar,
  whatsappHabilitado,
}: {
  ruta: RutaConParadas;
  puedeDespachar: boolean;
  onCancelar: (rutaId: string) => void;
  whatsappHabilitado: boolean;
}) {
  const [verMapa, setVerMapa] = useState(false);
  const resueltas = ruta.paradas.filter((p) => resuelta(p.estado)).length;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-2">
          <span>{ruta.repartidor_nombre ?? "Repartidor"}</span>
          <Badge variant="outline">{ETIQUETA_ESTADO_RUTA[ruta.estado] ?? ruta.estado}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        <div className="flex flex-wrap gap-3 text-gray">
          {ruta.distancia_m ? <span>{(ruta.distancia_m / 1000).toFixed(1)} km</span> : null}
          <span>
            {resueltas} de {ruta.paradas.length} paradas resueltas
          </span>
        </div>

        <ol className="flex flex-col gap-1.5">
          {ruta.paradas.map((p) => (
            <li key={p.entrega_id} className="flex flex-col gap-1">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate">
                  #{p.numero_orden ?? "—"} · {p.direccion_entrega ?? "Sin dirección"}
                </span>
                <span className="shrink-0 text-xs text-gray">
                  {ETIQUETA_ESTADO_ENTREGA[p.estado] ?? p.estado}
                </span>
              </div>
              {p.estado === "en_ruta" ? (
                <AvisoParada parada={p} whatsappHabilitado={whatsappHabilitado} />
              ) : null}
            </li>
          ))}
        </ol>

        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => setVerMapa((v) => !v)}>
            {verMapa ? "Ocultar mapa" : "Ver mapa"}
          </Button>
          {puedeDespachar && ruta.estado === "planificada" ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onCancelar(ruta.id)}
            >
              Cancelar ruta
            </Button>
          ) : null}
        </div>

        {verMapa ? <MapaRutas ruta={ruta} /> : null}
      </CardContent>
    </Card>
  );
}
