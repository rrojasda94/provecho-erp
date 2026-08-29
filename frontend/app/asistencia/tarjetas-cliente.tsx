"use client";

/**
 * La grilla de tarjetas y el pinpad. Dos pasos y nada más: se toca el
 * nombre, se teclea el PIN.
 *
 * Qué se marca no lo elige nadie acá — el servidor lo decide con el estado
 * del día. La tarjeta anticipa cuál va a ser para que quien la toca sepa
 * qué está por hacer, pero si el pad y el servidor discreparan, manda el
 * servidor: la respuesta trae el tipo real y es esa la que se muestra.
 */

import { useEffect, useRef, useState } from "react";

import Pinpad from "@/components/pinpad/pinpad";
import { apiAsistencia, type Marcacion, type Tarjeta } from "@/lib/asistencia";
import { capturarFoto, obtenerUbicacion } from "@/lib/camara";
import { ErrorApi } from "@/lib/cliente-api";

/** Cuánto queda el acuse en pantalla antes de volver a la grilla. Lo justo
 * para leerlo de pie y sin tocar nada: la cola del cambio de turno no puede
 * esperar a que alguien confirme. */
const SEGUNDOS_ACUSE = 3;

type Props = { sucursalId: string; inicial: Tarjeta[] };

export default function TarjetasCliente({ sucursalId, inicial }: Props) {
  const [tarjetas, setTarjetas] = useState(inicial);
  const [elegida, setElegida] = useState<Tarjeta | null>(null);
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [acuse, setAcuse] = useState<{ nombre: string; marcacion: Marcacion } | null>(
    null,
  );
  const [enviando, setEnviando] = useState(false);
  const dialogo = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (elegida) dialogo.current?.showModal();
    else dialogo.current?.close();
  }, [elegida]);

  useEffect(() => {
    if (!acuse) return;
    const t = setTimeout(() => setAcuse(null), SEGUNDOS_ACUSE * 1000);
    return () => clearTimeout(t);
  }, [acuse]);

  const cerrar = () => {
    setElegida(null);
    setPin("");
    setError(null);
  };

  const enviar = async (pinCompleto: string) => {
    if (!elegida || enviando) return;
    setEnviando(true);
    setError(null);
    try {
      // Evidencia, no condición (RN-RRHH-024): se intenta en paralelo con
      // la cola de la cámara y el GPS, y si cualquiera de las dos falla o
      // tarda, se marca igual sin ellas.
      const [foto, ubicacion] = await Promise.all([capturarFoto(), obtenerUbicacion()]);
      const marcacion = await apiAsistencia.marcar(
        sucursalId,
        elegida.trabajador_id,
        pinCompleto,
        {
          ...(foto ? { foto } : {}),
          ...(ubicacion ? { lat: ubicacion.lat, lng: ubicacion.lng } : {}),
        },
      );
      setAcuse({ nombre: elegida.nombre, marcacion });
      cerrar();
      setTarjetas(await apiAsistencia.tarjetas(sucursalId));
    } catch (e) {
      // El PIN se borra siempre: dejarlo escrito invita a probar el
      // siguiente dígito en vez de volver a teclearlo entero.
      setPin("");
      setError(
        e instanceof ErrorApi ? e.message : "No se pudo registrar la marcación",
      );
    } finally {
      setEnviando(false);
    }
  };

  if (acuse) {
    const { hora_entrada, hora_salida, tardanza_min } = acuse.marcacion.asistencia;
    const esEntrada = acuse.marcacion.tipo === "entrada";
    return (
      <main className="asistencia-acuse" role="status">
        <h1>{esEntrada ? "Entrada registrada" : "Salida registrada"}</h1>
        <p className="asistencia-acuse-nombre">{acuse.nombre}</p>
        <p className="asistencia-acuse-hora">
          {(esEntrada ? hora_entrada : hora_salida)?.slice(0, 5)}
        </p>
        {esEntrada && tardanza_min > 0 && (
          <p className="asistencia-acuse-tardanza">
            {tardanza_min} min de tardanza
          </p>
        )}
      </main>
    );
  }

  return (
    <main className="asistencia-pad">
      <h1>Marca tu asistencia</h1>
      <p>Toca tu nombre y teclea tu PIN.</p>

      {tarjetas.length === 0 && (
        <p className="asistencia-nota">
          Este local todavía no tiene a nadie con asistencia registrada.
        </p>
      )}

      <div className="asistencia-grilla">
        {tarjetas.map((t) => (
          <button
            key={t.trabajador_id}
            type="button"
            className={`asistencia-tarjeta ${t.marco_salida ? "cerrada" : ""}`}
            disabled={t.marco_salida}
            onClick={() => setElegida(t)}
          >
            <strong>{t.nombre}</strong>
            <em>
              {t.marco_salida
                ? "jornada cerrada"
                : t.marco_entrada
                  ? "marcar salida"
                  : "marcar entrada"}
            </em>
          </button>
        ))}
      </div>

      <dialog ref={dialogo} className="asistencia-dialogo" onCancel={cerrar}>
        <header>
          <h2>{elegida?.nombre}</h2>
          <button type="button" onClick={cerrar} aria-label="Cerrar">
            ✕
          </button>
        </header>
        {error && <p className="asistencia-error">{error}</p>}
        <Pinpad
          value={pin}
          onChange={setPin}
          label="Tu PIN"
          testid="pinpad-asistencia"
          onCompleto={enviar}
        />
      </dialog>
    </main>
  );
}
