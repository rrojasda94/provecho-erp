"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ETIQUETA_ESTADO_ENTREGA,
  type Repartidor,
  type RutaConParadas,
  type VentaLista,
} from "@/lib/delivery";

import AvisoParada from "./aviso-parada";
import MapaRutas from "./mapa-rutas";
import RutaDialogo from "./ruta-dialogo";

const ETIQUETA_ESTADO_RUTA: Record<string, string> = {
  planificada: "Por salir",
  en_curso: "En ruta",
  finalizada: "Finalizada",
  cancelada: "Cancelada",
};

function resuelta(estado: string): boolean {
  return estado === "entregada" || estado === "fallida" || estado === "cancelada";
}

function ListaParadas({
  paradas,
  puedeDespachar,
  whatsappHabilitado,
  onEntregar,
}: {
  paradas: RutaConParadas["paradas"];
  puedeDespachar: boolean;
  whatsappHabilitado: boolean;
  onEntregar: (entregaId: string) => void;
}) {
  return (
    <ol className="flex flex-col gap-1.5">
      {paradas.map((p) => (
        <li key={p.entrega_id} className="flex flex-col gap-1">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate">
              #{p.numero_orden ?? "—"} · {p.direccion_entrega ?? "Sin dirección"}
            </span>
            <span className="flex shrink-0 items-center gap-1.5 text-xs text-gray">
              {!resuelta(p.estado) && !p.lista ? (
                <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-800">
                  En cocina
                </span>
              ) : null}
              {ETIQUETA_ESTADO_ENTREGA[p.estado] ?? p.estado}
            </span>
          </div>
          {p.estado === "en_ruta" ? (
            <div className="flex items-center gap-2">
              <AvisoParada parada={p} whatsappHabilitado={whatsappHabilitado} />
              {puedeDespachar ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => onEntregar(p.entrega_id)}
                >
                  Marcar entregada
                </Button>
              ) : null}
            </div>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

function AccionesRuta({
  ruta,
  puedeDespachar,
  noListas,
  resueltas,
  onCancelar,
  onIniciar,
  onFinalizar,
  editarTrigger,
}: {
  ruta: RutaConParadas;
  puedeDespachar: boolean;
  noListas: number;
  resueltas: number;
  onCancelar: (rutaId: string) => void;
  onIniciar: (rutaId: string) => void;
  onFinalizar: (rutaId: string) => void;
  editarTrigger: React.ReactNode;
}) {
  if (!puedeDespachar) return null;
  return (
    <>
      {ruta.estado === "planificada" || ruta.estado === "en_curso" ? editarTrigger : null}
      {ruta.estado === "planificada" ? (
        <>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={noListas > 0}
            title={noListas > 0 ? "Hay pedidos que siguen en cocina" : undefined}
            onClick={() => onIniciar(ruta.id)}
          >
            Iniciar
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={() => onCancelar(ruta.id)}>
            Cancelar ruta
          </Button>
        </>
      ) : null}
      {ruta.estado === "en_curso" && resueltas === ruta.paradas.length ? (
        <Button type="button" variant="outline" size="sm" onClick={() => onFinalizar(ruta.id)}>
          Finalizar
        </Button>
      ) : null}
    </>
  );
}

export default function TarjetaRuta({
  ruta,
  puedeDespachar,
  onCancelar,
  onIniciar,
  onFinalizar,
  onEntregar,
  whatsappHabilitado,
  sucursalId,
  sinAsignar,
  repartidores,
  onEditada,
}: {
  ruta: RutaConParadas;
  puedeDespachar: boolean;
  onCancelar: (rutaId: string) => void;
  onIniciar: (rutaId: string) => void;
  onFinalizar: (rutaId: string) => void;
  onEntregar: (entregaId: string) => void;
  whatsappHabilitado: boolean;
  sucursalId: string;
  sinAsignar: VentaLista[];
  repartidores: Repartidor[];
  onEditada: () => void;
}) {
  const [verMapa, setVerMapa] = useState(false);
  const resueltas = ruta.paradas.filter((p) => resuelta(p.estado)).length;
  const noListas = ruta.paradas.filter((p) => !resuelta(p.estado) && !p.lista).length;

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

        <ListaParadas
          paradas={ruta.paradas}
          puedeDespachar={puedeDespachar}
          whatsappHabilitado={whatsappHabilitado}
          onEntregar={onEntregar}
        />

        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => setVerMapa((v) => !v)}>
            {verMapa ? "Ocultar mapa" : "Ver mapa"}
          </Button>
          <AccionesRuta
            ruta={ruta}
            puedeDespachar={puedeDespachar}
            noListas={noListas}
            resueltas={resueltas}
            onCancelar={onCancelar}
            onIniciar={onIniciar}
            onFinalizar={onFinalizar}
            editarTrigger={
              <RutaDialogo
                sucursalId={sucursalId}
                sinAsignar={sinAsignar}
                repartidores={repartidores}
                ruta={ruta}
                onListo={onEditada}
                trigger={{ label: "Editar", variant: "outline", size: "sm" }}
              />
            }
          />
        </div>

        {verMapa ? <MapaRutas ruta={ruta} /> : null}
      </CardContent>
    </Card>
  );
}
