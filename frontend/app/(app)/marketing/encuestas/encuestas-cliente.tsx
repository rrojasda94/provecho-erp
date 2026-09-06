"use client";

import { useState, useTransition } from "react";

import { Insignia } from "@/components/estado/insignia";
import { fechaHora } from "@/lib/fechas";
import { tienePermiso } from "@/lib/permisos";

import { expirarEncuestaAction } from "./actions";

export type Encuesta = {
  id: string;
  canal: string;
  fecha_envio: string;
  fecha_respuesta: string | null;
  puntaje: number | null;
  comentario: string | null;
  estado: string;
  error_envio: string | null;
};

const GESTIONAR = "marketing.encuesta_gestionar";

const TONO: Record<string, "exito" | "alerta" | "neutro" | "peligro"> = {
  respondida: "exito",
  enviada: "alerta",
  expirada: "neutro",
  fallida: "peligro",
};

function BotonExpirar({ id }: { id: string }) {
  const [pendiente, startTransition] = useTransition();
  const [error, setError] = useState("");
  return (
    <span className="flex flex-col">
      <button
        type="button"
        disabled={pendiente}
        onClick={() =>
          startTransition(async () => setError((await expirarEncuestaAction(id)).error))
        }
        className="text-xs font-semibold text-secondary hover:underline"
      >
        {pendiente ? "Cerrando..." : "Cerrar"}
      </button>
      {error && <span className="text-xs text-secondary">{error}</span>}
    </span>
  );
}

export function EncuestasCliente({
  encuestas,
  total,
  permisos,
}: {
  encuestas: Encuesta[];
  total: number;
  permisos: string[];
}) {
  const puedeGestionar = tienePermiso(permisos, GESTIONAR);
  const respondidas = encuestas.filter((e) => e.puntaje !== null);
  const promedio = respondidas.length
    ? respondidas.reduce((t, e) => t + (e.puntaje ?? 0), 0) / respondidas.length
    : null;

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-heading text-xl text-dark">Encuestas</h1>
      <p className="text-sm text-gray">
        Qué contestaron los clientes. La encuesta es selectiva y nunca automática
        para toda venta (RN-COM-007): se manda después de la entrega y a quien
        tiene con qué contestarla.
      </p>

      {promedio !== null && (
        <p className="rounded bg-cream px-3 py-2 text-sm">
          <strong className="cifra">{promedio.toFixed(1)}</strong> de puntaje
          promedio sobre <strong>{respondidas.length}</strong> respondidas.
        </p>
      )}

      {encuestas.length === 0 ? (
        <p className="rounded bg-cream px-3 py-2 text-sm text-gray">
          No hay encuestas con esos filtros.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[46rem] border-collapse text-sm">
            <thead>
              <tr className="border-b border-gray/30 text-left text-xs uppercase text-gray">
                <th className="py-2 pr-4 font-semibold">Enviada</th>
                <th className="py-2 pr-4 font-semibold">Canal</th>
                <th className="py-2 pr-4 font-semibold">Puntaje</th>
                <th className="py-2 pr-4 font-semibold">Comentario</th>
                <th className="py-2 font-semibold">Estado</th>
              </tr>
            </thead>
            <tbody>
              {encuestas.map((e) => (
                <tr key={e.id} className="border-b border-gray/15 align-top">
                  <td className="py-2 pr-4 cifra whitespace-nowrap">
                    {fechaHora(e.fecha_envio)}
                  </td>
                  <td className="py-2 pr-4">{e.canal}</td>
                  <td className="py-2 pr-4 cifra font-semibold">{e.puntaje ?? "—"}</td>
                  <td className="py-2 pr-4">
                    {e.comentario ?? <span className="text-gray">—</span>}
                    {/* Un envío fallido no es una encuesta sin contestar: es
                        una que el cliente nunca recibió, y se arregla en otro
                        lado. */}
                    {e.error_envio && (
                      <span className="block text-xs text-secondary">{e.error_envio}</span>
                    )}
                  </td>
                  <td className="py-2">
                    <span className="flex items-center gap-2">
                      <Insignia tono={TONO[e.estado] ?? "neutro"}>{e.estado}</Insignia>
                      {puedeGestionar && e.estado === "enviada" && <BotonExpirar id={e.id} />}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-xs text-gray">{total} encuestas en total.</p>
    </div>
  );
}
