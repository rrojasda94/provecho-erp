"use client";

import { useActionState, useEffect, useMemo, useRef, useState } from "react";

import {
  aprobarParametroAction,
  proponerParametroAction,
  rechazarParametroAction,
  type EstadoGerencia,
} from "../actions";
import { Combobox } from "@/components/ui/combobox";

export type Parametro = {
  id: string;
  modulo: string;
  codigo: string;
  valor: Record<string, unknown>;
  valor_display: string | null;
  estado: string;
  motivo: string | null;
  motivo_rechazo: string | null;
  resuelto_en: string | null;
};
export type Divisa = { id: string; codigo: string; nombre: string; simbolo: string };

const ESTADO_INICIAL: EstadoGerencia = { error: "", ok: false };

const MODULOS = [
  "accounting",
  "inventory",
  "marketing",
  "production",
  "purchases",
  "rrhh",
  "sales",
  "users",
];

/** Monto (lleva divisa), cantidad (lleva unidad de medida) o adimensional
 * (RN-GER-010). El backend responde 422 si la magnitud llega sin su unidad;
 * el selector existe para que eso no pase por descuido. */
function CamposValor({ divisas, prefijo = "" }: { divisas: Divisa[]; prefijo?: string }) {
  const [tipo, setTipo] = useState("monto");
  return (
    <>
      <div className="flex gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Tipo de valor
          <select
            name="tipo_valor"
            value={tipo}
            onChange={(e) => setTipo(e.target.value)}
            aria-label={`${prefijo}tipo de valor`}
          >
            <option value="monto">Monto (con divisa)</option>
            <option value="cantidad">Cantidad (con unidad de medida)</option>
            <option value="libre">Adimensional (días, porcentaje...)</option>
          </select>
        </label>
        <label className="flex w-32 flex-col gap-1 text-sm font-semibold">
          Valor
          <input name="valor_numero" type="number" step="0.0001" required />
        </label>
      </div>
      {tipo === "monto" && (
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Divisa
          <Combobox
            name="divisa"
            etiqueta="Divisa"
            requerido
            defaultValue="PEN"
            opciones={divisas.map((d) => ({
              valor: d.codigo,
              etiqueta: `${d.codigo} · ${d.nombre}`,
            }))}
          />
        </label>
      )}
      {tipo === "cantidad" && (
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Unidad de medida (id)
          <input name="unidad_medida_id" placeholder="UUID de la unidad" />
          <span className="text-xs font-normal text-gray">
            Las unidades se administran en Inventario; acá va su identificador.
          </span>
        </label>
      )}
      {tipo === "libre" && (
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Nombre del valor
          <input name="clave_libre" placeholder="dias, porcentaje, unidades..." />
        </label>
      )}
    </>
  );
}

function DialogoProponer({
  divisas,
  empresaId,
}: {
  divisas: Divisa[];
  empresaId: string;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [estado, formAction, pendiente] = useActionState(
    proponerParametroAction,
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
        + Proponer parámetro
      </button>
      <dialog ref={dialogRef} className="w-full max-w-md rounded-lg p-0 backdrop:bg-dark/40">
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          <input type="hidden" name="empresa_id" value={empresaId} />
          <h2 className="font-heading text-lg text-dark">
            Proponer parámetro
          </h2>
          <p className="text-xs text-gray">
            Cada área propone los suyos desde su módulo; el valor no llega al módulo
            hasta que Gerencia lo aprueba (ADR-014).
          </p>
          <div className="flex gap-2">
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              Módulo
              <select name="modulo" defaultValue="purchases">
                {MODULOS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-[2] flex-col gap-1 text-sm font-semibold">
              Código
              <input name="codigo" required maxLength={50} placeholder="oc_umbral" />
            </label>
          </div>
          <CamposValor divisas={divisas} />
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Motivo
            <input name="motivo" placeholder="Por qué se propone este valor" />
          </label>
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
              {pendiente ? "Enviando..." : "Proponer"}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

function DialogoResolver({
  parametro,
  divisas,
}: {
  parametro: Parametro;
  divisas: Divisa[];
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [modificar, setModificar] = useState(false);
  const [aprobacion, aprobarAction, aprobando] = useActionState(
    aprobarParametroAction,
    ESTADO_INICIAL,
  );
  const [rechazo, rechazarAction, rechazando] = useActionState(
    rechazarParametroAction,
    ESTADO_INICIAL,
  );

  useEffect(() => {
    if (aprobacion.ok || rechazo.ok) dialogRef.current?.close();
  }, [aprobacion.ok, rechazo.ok]);

  return (
    <>
      <button
        type="button"
        onClick={() => dialogRef.current?.showModal()}
        className="text-xs font-bold text-primary hover:underline"
      >
        Resolver
      </button>
      <dialog ref={dialogRef} className="w-full max-w-md rounded-lg p-0 backdrop:bg-dark/40">
        <div className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg text-dark">
            {parametro.modulo} · {parametro.codigo}
          </h2>
          <p className="text-sm text-dark">
            Valor propuesto: <strong>{parametro.valor_display ?? JSON.stringify(parametro.valor)}</strong>
          </p>
          {parametro.motivo && (
            <p className="text-sm text-gray">Motivo: {parametro.motivo}</p>
          )}

          <form action={aprobarAction} className="flex flex-col gap-3 border-t border-gray/20 pt-4">
            <input type="hidden" name="parametro_id" value={parametro.id} />
            <label className="flex items-center gap-2 text-sm font-semibold">
              <input
                type="checkbox"
                name="modificar"
                checked={modificar}
                onChange={(e) => setModificar(e.target.checked)}
              />
              Modificar el valor antes de aprobar
            </label>
            {modificar && <CamposValor divisas={divisas} prefijo="nuevo " />}
            {aprobacion.error && (
              <p role="alert" className="text-sm font-semibold text-secondary">
                {aprobacion.error}
              </p>
            )}
            <button
              type="submit"
              disabled={aprobando}
              className="self-start rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
            >
              {aprobando ? "Aprobando..." : "Aprobar"}
            </button>
          </form>

          <form action={rechazarAction} className="flex flex-col gap-3 border-t border-gray/20 pt-4">
            <input type="hidden" name="parametro_id" value={parametro.id} />
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Motivo del rechazo
              <input name="motivo_rechazo" required maxLength={500} />
            </label>
            {rechazo.error && (
              <p role="alert" className="text-sm font-semibold text-secondary">
                {rechazo.error}
              </p>
            )}
            <button
              type="submit"
              disabled={rechazando}
              className="self-start rounded border border-secondary px-4 py-2 text-sm font-semibold text-secondary"
            >
              {rechazando ? "Rechazando..." : "Rechazar"}
            </button>
          </form>

          <button
            type="button"
            onClick={() => dialogRef.current?.close()}
            className="self-end text-sm font-semibold text-gray hover:text-dark"
          >
            Cerrar
          </button>
        </div>
      </dialog>
    </>
  );
}

export function ParametrosCliente({
  parametros,
  divisas,
  empresaId,
}: {
  parametros: Parametro[];
  divisas: Divisa[];
  empresaId: string;
}) {
  const [soloPropuestos, setSoloPropuestos] = useState(true);
  const visibles = useMemo(
    () => (soloPropuestos ? parametros.filter((p) => p.estado === "propuesto") : parametros),
    [parametros, soloPropuestos],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl text-dark">
          Parámetros operativos
        </h1>
        <DialogoProponer divisas={divisas} empresaId={empresaId} />
      </div>
      <p className="text-sm text-gray">
        Los valores que el negocio configura (umbral de OC, margen mínimo, caja chica,
        rangos salariales). El área propone desde su módulo y Gerencia acepta, rechaza o
        modifica: hasta entonces el valor no llega al módulo (ADR-014, RN-GER-009).
      </p>
      <label className="flex items-center gap-2 text-sm font-semibold">
        <input
          type="checkbox"
          checked={soloPropuestos}
          onChange={(e) => setSoloPropuestos(e.target.checked)}
        />
        Solo pendientes de resolver
      </label>

      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-gray/30 text-left text-xs uppercase text-gray">
            <th className="py-2 pr-4 font-semibold">Módulo</th>
            <th className="py-2 pr-4 font-semibold">Código</th>
            <th className="py-2 pr-4 font-semibold">Valor</th>
            <th className="py-2 pr-4 font-semibold">Estado</th>
            <th className="py-2 font-semibold"></th>
          </tr>
        </thead>
        <tbody>
          {visibles.length === 0 && (
            <tr>
              <td colSpan={5} className="py-3 text-gray">
                {soloPropuestos
                  ? "Nada pendiente de resolver."
                  : "Todavía no hay parámetros propuestos."}
              </td>
            </tr>
          )}
          {visibles.map((p) => (
            <tr key={p.id} className="border-b border-gray/15 align-top">
              <td className="py-2 pr-4">{p.modulo}</td>
              <td className="py-2 pr-4 font-semibold text-dark">{p.codigo}</td>
              <td className="py-2 pr-4">
                {p.valor_display ?? JSON.stringify(p.valor)}
                {p.motivo_rechazo && (
                  <span className="block text-xs text-secondary">
                    Rechazado: {p.motivo_rechazo}
                  </span>
                )}
              </td>
              <td className="py-2 pr-4">
                {/* `vigente` es el aprobado que manda hoy; `reemplazado` es
                    el que quedó atrás cuando se aprobó uno nuevo. */}
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                    p.estado === "vigente"
                      ? "bg-accent/30 text-dark"
                      : p.estado === "propuesto"
                        ? "bg-secondary/15 text-secondary"
                        : "bg-gray/20 text-gray"
                  }`}
                >
                  {p.estado}
                </span>
              </td>
              <td className="py-2">
                {p.estado === "propuesto" && (
                  <DialogoResolver parametro={p} divisas={divisas} />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
