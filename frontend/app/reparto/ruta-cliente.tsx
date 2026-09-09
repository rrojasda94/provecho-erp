"use client";

import { useCallback, useState } from "react";

import { ErrorApi } from "@/lib/cliente-api";
import { apiDelivery, type MiParada, type MiRuta } from "@/lib/delivery";

import ParadaDialogo from "./parada-dialogo";
import { useGps } from "./use-gps";
import { useWakeLock } from "./use-wake-lock";

const ETIQUETA_ESTADO_PARADA: Record<string, string> = {
  pendiente: "Pendiente",
  asignada: "Por salir",
  en_ruta: "En camino",
  entregada: "Entregada",
  fallida: "No se pudo entregar",
  cancelada: "Cancelada",
};

/** Resuelta = ya no hay nada más que hacer con esta parada — es lo que
 * habilita "Finalizar ruta" (RN-DLV, el servidor exige lo mismo: 409 si
 * queda una parada `en_ruta`). */
function resuelta(estado: string): boolean {
  return estado === "entregada" || estado === "fallida" || estado === "cancelada";
}

function urlNavegar(lat: string | number | null, lng: string | number | null): string | null {
  if (lat === null || lng === null) return null;
  return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`;
}

/** Iniciar y finalizar comparten la misma forma —pedir, refrescar al
 * padre si sale bien, avisar si no— así que comparten un solo `ejecutar`
 * en vez de repetir el mismo try/catch/finally dos veces. */
function useAccionesRuta(rutaId: string, onCambio: () => void) {
  const [aviso, setAviso] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  const ejecutar = useCallback(
    async (accion: () => Promise<unknown>, mensajeError: string) => {
      setOcupado(true);
      try {
        await accion();
        onCambio();
      } catch (e) {
        setAviso(e instanceof ErrorApi ? e.message : mensajeError);
      } finally {
        setOcupado(false);
      }
    },
    [onCambio],
  );

  return {
    aviso,
    ocupado,
    iniciar: () => ejecutar(() => apiDelivery.iniciarRuta(rutaId), "No se pudo iniciar la ruta"),
    finalizar: () =>
      ejecutar(
        () => apiDelivery.finalizarRuta(rutaId),
        "Todavía queda una parada sin resolver",
      ),
  };
}

function ResumenRuta({ ruta, errorGps }: { ruta: MiRuta; errorGps: string | null }) {
  return (
    <div className="reparto-ruta-resumen">
      <span className={`reparto-chip reparto-chip-${ruta.estado}`}>
        {ruta.estado === "planificada" ? "Por salir" : "En ruta"}
      </span>
      {ruta.distancia_m ? <span>{(ruta.distancia_m / 1000).toFixed(1)} km</span> : null}
      {errorGps ? <span className="reparto-error-gps">{errorGps}</span> : null}
    </div>
  );
}

/** El único botón de acción de la pantalla, según en qué momento está la
 * ruta — planificada pide iniciarla, en curso (con todo resuelto) pide
 * cerrarla, cualquier otro estado no tiene nada que ofrecer acá. */
function BotonRuta({
  ruta,
  enCurso,
  ocupado,
  todasResueltas,
  iniciar,
  finalizar,
}: {
  ruta: MiRuta;
  enCurso: boolean;
  ocupado: boolean;
  todasResueltas: boolean;
  iniciar: () => void;
  finalizar: () => void;
}) {
  if (ruta.estado === "planificada") {
    return (
      <button
        type="button"
        className="reparto-boton-primario"
        disabled={ocupado}
        onClick={iniciar}
      >
        {ocupado ? "Iniciando…" : "Iniciar ruta"}
      </button>
    );
  }
  if (!enCurso) return null;
  return (
    <button
      type="button"
      className="reparto-boton-primario"
      disabled={ocupado || !todasResueltas}
      onClick={finalizar}
    >
      {ocupado ? "Finalizando…" : "Finalizar ruta"}
    </button>
  );
}

function Parada({
  parada,
  onAccion,
}: {
  parada: MiParada;
  onAccion: (modo: "entregar" | "fallar") => void;
}) {
  const enlace = urlNavegar(parada.destino_lat, parada.destino_lng);
  return (
    <li className="reparto-parada">
      <header>
        <strong>Pedido #{parada.numero_orden ?? "—"}</strong>
        <span className={`reparto-estado-parada reparto-estado-${parada.estado}`}>
          {ETIQUETA_ESTADO_PARADA[parada.estado] ?? parada.estado}
        </span>
      </header>
      <p>{parada.direccion_entrega ?? "Sin dirección anotada"}</p>
      {parada.cliente_nombre ? <p>{parada.cliente_nombre}</p> : null}
      {parada.monto_a_cobrar !== null ? (
        <p className="reparto-monto">Cobrar S/ {Number(parada.monto_a_cobrar).toFixed(2)}</p>
      ) : null}

      <div className="reparto-parada-acciones">
        {parada.cliente_telefono ? (
          <a href={`tel:${parada.cliente_telefono}`}>Llamar</a>
        ) : null}
        {enlace ? (
          <a href={enlace} target="_blank" rel="noreferrer">
            Navegar
          </a>
        ) : null}
        {parada.estado === "en_ruta" ? (
          <>
            <button type="button" onClick={() => onAccion("entregar")}>
              Entregado
            </button>
            <button type="button" onClick={() => onAccion("fallar")}>
              No se pudo
            </button>
          </>
        ) : null}
      </div>
    </li>
  );
}

export default function RutaCliente({
  ruta,
  onCambio,
}: {
  ruta: MiRuta;
  onCambio: () => void;
}) {
  const [dialogo, setDialogo] = useState<{
    parada: MiParada;
    modo: "entregar" | "fallar";
  } | null>(null);

  const enCurso = ruta.estado === "en_curso";

  const enviarPosicion = useCallback(
    (p: { lat: number; lng: number; precision_m: number | null; registrado_at: string }) => {
      apiDelivery.registrarPosicion(ruta.id, p).catch(() => {
        // Un ping perdido no interrumpe la ruta: el siguiente lo compensa.
      });
    },
    [ruta.id],
  );
  const { error: errorGps } = useGps(enCurso, enviarPosicion);
  useWakeLock(enCurso);

  const { aviso, ocupado, iniciar, finalizar } = useAccionesRuta(ruta.id, onCambio);
  const todasResueltas = ruta.paradas.every((p) => resuelta(p.estado));

  return (
    <section className="reparto-ruta">
      <ResumenRuta ruta={ruta} errorGps={errorGps} />

      <ol className="reparto-paradas">
        {ruta.paradas.map((parada) => (
          <Parada
            key={parada.entrega_id}
            parada={parada}
            onAccion={(modo) => setDialogo({ parada, modo })}
          />
        ))}
      </ol>

      <BotonRuta
        ruta={ruta}
        enCurso={enCurso}
        ocupado={ocupado}
        todasResueltas={todasResueltas}
        iniciar={iniciar}
        finalizar={finalizar}
      />

      {aviso ? (
        <p className="reparto-error" role="alert">
          {aviso}
        </p>
      ) : null}

      <ParadaDialogo
        abierto={dialogo !== null}
        parada={dialogo?.parada ?? null}
        modo={dialogo?.modo ?? "entregar"}
        onCerrar={() => setDialogo(null)}
        onResuelta={() => {
          setDialogo(null);
          onCambio();
        }}
      />
    </section>
  );
}
