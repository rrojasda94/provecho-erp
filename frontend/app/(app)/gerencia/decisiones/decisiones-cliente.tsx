"use client";

import { useActionState, useEffect, useRef, useState } from "react";

import { registrarDecisionAction, type EstadoGerencia } from "../actions";

export type Decision = {
  id: string;
  tipo: string;
  referencia_tipo: string;
  referencia_id: string;
  sustento: string;
  resultado: string;
  condiciones: string | null;
  ejecuta_area: string | null;
  fecha: string;
};

const ESTADO_INICIAL: EstadoGerencia = { error: "", ok: false };

const TIPOS = ["aprobacion", "directiva", "accion_correctiva", "decision_estrategica"];
const RESULTADOS = [
  "aprobado",
  "aprobado_con_condiciones",
  "rechazado",
  "diferido",
  "elevado_a_socios",
];
const AREAS = [
  "accounting",
  "inventory",
  "marketing",
  "production",
  "purchases",
  "rrhh",
  "sales",
  "users",
];

function DialogoNuevaActa() {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [resultado, setResultado] = useState("aprobado");
  const [estado, formAction, pendiente] = useActionState(
    registrarDecisionAction,
    ESTADO_INICIAL,
  );

  useEffect(() => {
    if (estado.ok) {
      formRef.current?.reset();
      dialogRef.current?.close();
    }
  }, [estado.ok]);

  return (
    <>
      <button
        type="button"
        onClick={() => dialogRef.current?.showModal()}
        className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
      >
        + Nueva acta
      </button>
      <dialog ref={dialogRef} className="w-full max-w-lg rounded-lg p-0 backdrop:bg-dark/40">
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg text-dark">
            Acta de decisión
          </h2>
          <div className="flex gap-2">
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              Tipo
              <select name="tipo" defaultValue="aprobacion">
                {TIPOS.map((t) => (
                  <option key={t} value={t}>
                    {t.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex w-40 flex-col gap-1 text-sm font-semibold">
              Fecha
              <input name="fecha" type="date" required />
            </label>
          </div>
          <div className="flex gap-2">
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              Sobre qué
              <input
                name="referencia_tipo"
                required
                maxLength={50}
                placeholder="orden_compra, campana, trabajador..."
              />
            </label>
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              Id de la referencia
              <input name="referencia_id" required placeholder="UUID" />
            </label>
          </div>
          <p className="text-xs text-gray">
            La referencia es polimórfica y sin FK a propósito: el acta aplica a una OC
            escalada, una campaña sobre presupuesto o una sanción, y ningún módulo gana
            una llave hacia Gerencia por eso.
          </p>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Sustento
            <textarea name="sustento" required rows={3} className="rounded border border-gray/40 p-2" />
          </label>
          <div className="flex gap-2">
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              Resultado
              <select
                name="resultado"
                value={resultado}
                onChange={(e) => setResultado(e.target.value)}
              >
                {RESULTADOS.map((r) => (
                  <option key={r} value={r}>
                    {r.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              Área que ejecuta
              <select name="ejecuta_area" defaultValue="">
                <option value="">Ninguna en particular</option>
                {AREAS.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {resultado === "aprobado_con_condiciones" && (
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Condiciones
              <textarea
                name="condiciones"
                rows={2}
                required
                className="rounded border border-gray/40 p-2"
              />
              <span className="text-xs font-normal text-gray">
                Un acta que no dice qué cumplir no sirve: el backend la rechaza.
              </span>
            </label>
          )}
          {estado.error && (
            <p role="alert" className="text-sm font-semibold text-secondary">
              {estado.error}
            </p>
          )}
          <div className="mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => dialogRef.current?.close()}
              className="rounded border border-gray px-4 py-2 text-sm font-semibold text-dark"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={pendiente}
              className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
            >
              {pendiente ? "Firmando..." : "Firmar acta"}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

export function DecisionesCliente({
  decisiones,
  puedeDecidir,
}: {
  decisiones: Decision[];
  puedeDecidir: boolean;
}) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl text-dark">
          Decisiones gerenciales
        </h1>
        {puedeDecidir && <DialogoNuevaActa />}
      </div>
      <p className="text-sm text-gray">
        El acta de lo que Gerencia decidió y por qué (RN-GER-002). Quien ejecuta la lee;
        firmarla es de Gerencia (RN-GER-005).
      </p>
      {decisiones.length === 0 ? (
        <p className="rounded bg-cream px-3 py-2 text-sm text-gray">
          Todavía no hay actas registradas.
        </p>
      ) : (
        <ul className="flex flex-col gap-3">
          {decisiones.map((d) => (
            <li key={d.id} className="rounded border border-gray/20 bg-white p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-dark">{d.tipo.replace(/_/g, " ")}</span>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                    d.resultado === "rechazado"
                      ? "bg-secondary/15 text-secondary"
                      : "bg-accent/30 text-dark"
                  }`}
                >
                  {d.resultado.replace(/_/g, " ")}
                </span>
                <span className="text-xs text-gray">{d.fecha}</span>
                <span className="text-xs text-gray">
                  · sobre {d.referencia_tipo} {d.referencia_id.slice(0, 8)}
                </span>
                {d.ejecuta_area && (
                  <span className="text-xs text-gray">· ejecuta {d.ejecuta_area}</span>
                )}
              </div>
              <p className="mt-2 text-sm text-dark">{d.sustento}</p>
              {d.condiciones && (
                <p className="mt-1 text-sm text-secondary">
                  Condiciones: {d.condiciones}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
