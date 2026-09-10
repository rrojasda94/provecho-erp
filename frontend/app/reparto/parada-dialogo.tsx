"use client";

import { useEffect, useRef, useState } from "react";

import { capturarFoto, obtenerUbicacion } from "@/lib/camara";
import { ErrorApi } from "@/lib/cliente-api";
import {
  apiDelivery,
  ETIQUETA_MOTIVO,
  MOTIVOS_FALLO,
  type MotivoFallo,
  type ParadaReparto,
} from "@/lib/delivery";

type Props = {
  abierto: boolean;
  parada: ParadaReparto | null;
  modo: "entregar" | "fallar";
  onCerrar: () => void;
  onResuelta: () => void;
};

async function enviarEntrega(
  entregaId: string,
  datos: { observacion: string; foto: string | null },
) {
  const ubicacion = await obtenerUbicacion();
  await apiDelivery.entregar(entregaId, {
    lat: ubicacion?.lat ?? null,
    lng: ubicacion?.lng ?? null,
    foto: datos.foto,
    observacion: datos.observacion.trim() || null,
  });
}

async function enviarFallo(
  entregaId: string,
  datos: { motivo: MotivoFallo; detalle: string; foto: string | null },
) {
  const ubicacion = await obtenerUbicacion();
  await apiDelivery.fallar(entregaId, {
    motivo: datos.motivo,
    detalle: datos.detalle.trim() || null,
    lat: ubicacion?.lat ?? null,
    lng: ubicacion?.lng ?? null,
    foto: datos.foto,
  });
}

function CamposEntregar({
  observacion,
  onObservacion,
}: {
  observacion: string;
  onObservacion: (v: string) => void;
}) {
  return (
    <label className="reparto-campo">
      <span>Observación (opcional)</span>
      <textarea
        value={observacion}
        onChange={(e) => onObservacion(e.target.value)}
        maxLength={255}
        rows={2}
      />
    </label>
  );
}

function CamposFallar({
  motivo,
  onMotivo,
  detalle,
  onDetalle,
}: {
  motivo: MotivoFallo;
  onMotivo: (v: MotivoFallo) => void;
  detalle: string;
  onDetalle: (v: string) => void;
}) {
  return (
    <>
      <label className="reparto-campo">
        <span>Motivo</span>
        <select value={motivo} onChange={(e) => onMotivo(e.target.value as MotivoFallo)}>
          {MOTIVOS_FALLO.map((m) => (
            <option key={m} value={m}>
              {ETIQUETA_MOTIVO[m]}
            </option>
          ))}
        </select>
      </label>
      {motivo === "otro" ? (
        <label className="reparto-campo">
          <span>Detalle</span>
          <textarea
            value={detalle}
            onChange={(e) => onDetalle(e.target.value)}
            maxLength={255}
            rows={3}
          />
        </label>
      ) : null}
    </>
  );
}

function FotoEvidencia({
  foto,
  tomando,
  onTomar,
}: {
  foto: string | null;
  tomando: boolean;
  onTomar: () => void;
}) {
  const etiqueta = foto ? "Cambiar foto" : tomando ? "Abriendo cámara…" : "Tomar foto (opcional)";
  return (
    <>
      <button type="button" onClick={onTomar} disabled={tomando}>
        {etiqueta}
      </button>
      {foto ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={`data:image/jpeg;base64,${foto}`}
          alt="Evidencia de la entrega"
          className="reparto-foto-previa"
        />
      ) : null}
    </>
  );
}

/**
 * Confirmar una entrega o registrar por qué no se pudo (RN-DLV-003), con
 * ubicación y foto de respaldo — las dos opcionales: un GPS flojo o una
 * cámara sin permiso no pueden trabar la entrega (mismo criterio que
 * `rrhh.marcacion`, `lib/camara.ts`).
 *
 * `<dialog>` nativo, igual que `app/pdv/dialogos.tsx`: foco atrapado y
 * cierre con Escape sin una librería aparte.
 */
export default function ParadaDialogo({ abierto, parada, modo, onCerrar, onResuelta }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const [observacion, setObservacion] = useState("");
  const [motivo, setMotivo] = useState<MotivoFallo>("cliente_ausente");
  const [detalle, setDetalle] = useState("");
  const [foto, setFoto] = useState<string | null>(null);
  const [tomandoFoto, setTomandoFoto] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (abierto && !d.open) d.showModal();
    if (!abierto && d.open) d.close();
  }, [abierto]);

  // Limpia el formulario cada vez que se abre para una parada u operación
  // distinta — sin esto, el detalle de un "no se pudo" anterior sobrevive
  // al abrir el diálogo de otra parada.
  useEffect(() => {
    if (!abierto) return;
    setObservacion("");
    setMotivo("cliente_ausente");
    setDetalle("");
    setFoto(null);
    setError(null);
  }, [abierto, parada?.entrega_id, modo]);

  if (!parada) return null;

  const tomarFoto = async () => {
    setTomandoFoto(true);
    try {
      setFoto(await capturarFoto({ camara: "environment" }));
    } finally {
      setTomandoFoto(false);
    }
  };

  const confirmar = async () => {
    if (modo === "fallar" && motivo === "otro" && !detalle.trim()) {
      setError('Cuenta qué pasó: el detalle hace falta cuando el motivo es "otro".');
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      if (modo === "entregar") {
        await enviarEntrega(parada.entrega_id, { observacion, foto });
      } else {
        await enviarFallo(parada.entrega_id, { motivo, detalle, foto });
      }
      onResuelta();
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo registrar. Intenta de nuevo.");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <dialog ref={ref} className="reparto-dialogo" onClose={onCerrar}>
      <header>
        <h3>{modo === "entregar" ? "Confirmar entrega" : "No se pudo entregar"}</h3>
        <button type="button" onClick={onCerrar} aria-label="Cerrar" disabled={enviando}>
          ×
        </button>
      </header>

      <div className="reparto-dialogo-cuerpo">
        <p className="reparto-dialogo-direccion">
          {parada.direccion_entrega ?? "Sin dirección anotada"}
        </p>

        {modo === "fallar" ? (
          <CamposFallar motivo={motivo} onMotivo={setMotivo} detalle={detalle} onDetalle={setDetalle} />
        ) : (
          <CamposEntregar observacion={observacion} onObservacion={setObservacion} />
        )}

        <FotoEvidencia foto={foto} tomando={tomandoFoto} onTomar={tomarFoto} />

        {error ? (
          <p className="reparto-error" role="alert">
            {error}
          </p>
        ) : null}
      </div>

      <footer>
        <button type="button" onClick={onCerrar} disabled={enviando}>
          Cancelar
        </button>
        <button
          type="button"
          className="reparto-boton-primario"
          onClick={confirmar}
          disabled={enviando}
        >
          {enviando ? "Enviando…" : "Confirmar"}
        </button>
      </footer>
    </dialog>
  );
}
