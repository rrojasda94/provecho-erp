"use client";

import { useRouter } from "next/navigation";
import { useActionState, useEffect, useMemo, useRef, useState, useTransition } from "react";

import {
  anularVentaAction,
  emitirNotaCreditoAction,
  lineasDeVentaAction,
  reintentarComprobanteAction,
  type EstadoVenta,
  type LineaVenta,
} from "./actions";
import { Combobox } from "@/components/ui/combobox";

export type Venta = {
  id: string;
  fecha_orden: string;
  numero_orden: number;
  canal: string;
  modalidad: string;
  estado: string;
  total: string;
  referencia_atencion: string | null;
};
export type Comprobante = {
  id: string;
  tipo: string;
  serie: string;
  correlativo: number;
  estado_emision: string;
  detalle_emision: string | null;
  intentos_emision: number;
  // Presente = ya fue acreditado por una nota total y no admite otra.
  anulado_por_nc_id: string | null;
};
export type Sucursal = { id: string; nombre: string };

// `cerrada` es el consumo de personal ya entregado (RN-COM-027): no se
// cobra, así que sin este filtro no habría forma de listarlo en la jornada.
const ESTADOS = ["orden", "pagada", "entregada", "cerrada", "anulada"];

function EstadoVenta({ estado }: { estado: string }) {
  const clase =
    estado === "anulada"
      ? "bg-gray/20 text-gray"
      : estado === "orden"
        ? "bg-secondary/15 text-secondary"
        : "bg-accent/30 text-dark";
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${clase}`}>
      {estado}
    </span>
  );
}

function CeldaComprobante({ comprobante }: { comprobante?: Comprobante }) {
  const [pendiente, startTransition] = useTransition();
  const [error, setError] = useState("");

  if (!comprobante) {
    return <span className="text-xs text-gray">sin cuenta cerrada</span>;
  }

  const fallo = comprobante.estado_emision === "rechazado" || comprobante.estado_emision === "error";
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs font-semibold text-dark">
        {comprobante.tipo} {comprobante.serie}-{comprobante.correlativo}
      </span>
      <span className={`text-xs ${fallo ? "text-secondary" : "text-gray"}`}>
        {comprobante.estado_emision}
        {comprobante.intentos_emision > 1 && ` · ${comprobante.intentos_emision} intentos`}
      </span>
      {fallo && (
        <>
          <button
            type="button"
            disabled={pendiente}
            onClick={() =>
              startTransition(async () => {
                const r = await reintentarComprobanteAction(comprobante.id);
                setError(r.error);
              })
            }
            className="self-start text-xs font-bold text-primary hover:underline"
          >
            {pendiente ? "Reintentando..." : "Reintentar emisión"}
          </button>
          {(error || comprobante.detalle_emision) && (
            <span className="text-xs text-secondary">
              {error || comprobante.detalle_emision}
            </span>
          )}
        </>
      )}
    </div>
  );
}

const ESTADO_INICIAL: EstadoVenta = { error: "", ok: false };

// Catálogo 09 de SUNAT, con los cinco motivos que este negocio produce. Los
// dos de corrección no dan de baja la venta: arreglan el papel.
const MOTIVOS_NC = [
  { codigo: "01", texto: "Anulación de la operación", corrige: false },
  { codigo: "06", texto: "Devolución total", corrige: false },
  { codigo: "07", texto: "Devolución por ítem", corrige: false },
  { codigo: "02", texto: "Anulación por error en el RUC", corrige: true },
  { codigo: "03", texto: "Corrección por error en la descripción", corrige: true },
];

function DialogoNotaCredito({
  venta,
  comprobante,
}: {
  venta: Venta;
  comprobante: Comprobante;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [motivo, setMotivo] = useState("01");
  const [alcance, setAlcance] = useState<"total" | "parcial">("total");
  const [lineas, setLineas] = useState<LineaVenta[]>([]);
  const [estado, formAction, pendiente] = useActionState(
    emitirNotaCreditoAction,
    ESTADO_INICIAL,
  );

  useEffect(() => {
    if (estado.ok) dialogRef.current?.close();
  }, [estado.ok]);

  const abrir = async () => {
    dialogRef.current?.showModal();
    if (lineas.length === 0) setLineas(await lineasDeVentaAction(venta.id));
  };

  const deCorreccion = MOTIVOS_NC.find((m) => m.codigo === motivo)?.corrige ?? false;

  return (
    <>
      <button
        type="button"
        onClick={abrir}
        className="text-xs font-bold text-primary hover:underline"
      >
        Nota de crédito
      </button>
      <dialog ref={dialogRef} className="w-full max-w-lg rounded-lg p-0 backdrop:bg-dark/40">
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          <input type="hidden" name="comprobante_id" value={comprobante.id} />
          <h2 className="font-heading text-lg text-dark">
            Nota de crédito · {comprobante.serie}-{comprobante.correlativo}
          </h2>
          <p className="text-xs text-gray">
            Una venta cobrada no se anula, se acredita. La nota sale en serie propia y
            solo puede emitirse una vez por comprobante.
          </p>

          <label className="flex flex-col gap-1 text-sm font-semibold">
            Motivo (catálogo 09 de SUNAT)
            <select name="motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)}>
              {MOTIVOS_NC.map((m) => (
                <option key={m.codigo} value={m.codigo}>
                  {m.codigo} · {m.texto}
                </option>
              ))}
            </select>
            {deCorreccion && (
              <span className="text-xs font-normal text-gray">
                Corrige el documento, no la operación: la venta sigue viva y el
                comprobante queda liberado para reemitir el corregido.
              </span>
            )}
          </label>

          <fieldset className="flex flex-col gap-2 rounded border border-gray/20 p-3">
            <legend className="px-1 text-xs font-semibold uppercase text-gray">
              Qué se acredita
            </legend>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="alcance"
                value="total"
                checked={alcance === "total"}
                onChange={() => setAlcance("total")}
              />
              Todo el comprobante
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="alcance"
                value="parcial"
                checked={alcance === "parcial"}
                onChange={() => setAlcance("parcial")}
              />
              Solo algunas líneas
            </label>
            {alcance === "parcial" && (
              <div className="mt-1 flex flex-col gap-1.5">
                {lineas.length === 0 && (
                  <span className="text-xs text-gray">Cargando las líneas...</span>
                )}
                {lineas.map((linea) => (
                  <div key={linea.id} className="flex items-center gap-2 text-sm">
                    <input type="hidden" name="linea_id" value={linea.id} />
                    <span className="flex-1">
                      {linea.nombre}{" "}
                      <span className="text-xs text-gray">
                        (vendidas {linea.cantidad})
                      </span>
                    </span>
                    <input
                      name="linea_cantidad"
                      type="number"
                      step="0.001"
                      min="0"
                      max={linea.cantidad}
                      defaultValue="0"
                      aria-label={`Cantidad a devolver de ${linea.nombre}`}
                      className="w-24 rounded border border-gray/40 px-2 py-1"
                    />
                  </div>
                ))}
                <span className="text-xs text-gray">
                  Cero = no se devuelve. Cuenta contra lo que quede sin acreditar, no
                  contra lo vendido.
                </span>
              </div>
            )}
          </fieldset>

          <label className="flex items-start gap-2 text-sm font-semibold">
            <input
              type="checkbox"
              name="repone_stock"
              defaultChecked={!deCorreccion}
              className="mt-1"
            />
            <span>
              Devolver el insumo al stock
              <span className="block text-xs font-normal text-gray">
                En cocina el plato devuelto rara vez vuelve al inventario, y corregir un
                dato del comprobante no lo toca en absoluto.
              </span>
            </span>
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
              {pendiente ? "Emitiendo..." : "Emitir"}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

/** Anular o acreditar, nunca las dos: antes de cobrar se anula, después
 * solo queda la nota de crédito (RN-CPP-009). */
function Acciones({ venta, comprobante }: { venta: Venta; comprobante?: Comprobante }) {
  if (venta.estado === "orden") return <BotonAnular venta={venta} />;
  const acreditable =
    comprobante !== undefined &&
    comprobante.tipo !== "nc" &&
    comprobante.estado_emision === "aceptado" &&
    !comprobante.anulado_por_nc_id;
  if (acreditable) return <DialogoNotaCredito venta={venta} comprobante={comprobante} />;
  if (comprobante?.anulado_por_nc_id) {
    return <span className="text-xs text-gray">acreditado</span>;
  }
  return <span className="text-xs text-gray">—</span>;
}


function BotonAnular({ venta }: { venta: Venta }) {
  const [pendiente, startTransition] = useTransition();
  const [error, setError] = useState("");
  // Anular repone el stock y solo aplica antes de cobrar: una venta pagada se
  // corrige con nota de crédito, no borrándola.
  return (
    <div className="flex flex-col gap-0.5">
      <button
        type="button"
        disabled={pendiente}
        onClick={() =>
          startTransition(async () => {
            const r = await anularVentaAction(venta.id);
            setError(r.error);
          })
        }
        className="text-xs font-semibold text-secondary hover:underline"
      >
        {pendiente ? "Anulando..." : "Anular"}
      </button>
      {error && <span className="text-xs text-secondary">{error}</span>}
    </div>
  );
}

export function JornadaCliente({
  ventas,
  comprobantes,
  sucursales,
  sucursalId,
  fecha,
  estado,
}: {
  ventas: Venta[];
  comprobantes: Record<string, Comprobante>;
  sucursales: Sucursal[];
  sucursalId: string;
  fecha: string;
  estado: string;
}) {
  const router = useRouter();

  // Los filtros viven en la URL, no en estado del cliente: la jornada de una
  // sucursal en una fecha es una dirección que se comparte y se recarga.
  const navegar = (cambios: Record<string, string>) => {
    const query = new URLSearchParams({ sucursal: sucursalId, fecha, estado, ...cambios });
    for (const [k, v] of [...query]) if (!v) query.delete(k);
    router.push(`/ventas?${query}`);
  };

  const totales = useMemo(() => {
    const cobradas = ventas.filter((v) => v.estado !== "anulada" && v.estado !== "orden");
    return {
      cantidad: cobradas.length,
      monto: cobradas.reduce((t, v) => t + Number(v.total), 0),
      abiertas: ventas.filter((v) => v.estado === "orden").length,
    };
  }, [ventas]);

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-heading text-xl text-dark">Jornada</h1>
      <p className="text-sm text-gray">
        Lo vendido en una sucursal, día por día: verificar lo cobrado, reintentar el
        comprobante que SUNAT rechazó y anular una orden que nunca se cobró.
      </p>

      <div className="flex flex-wrap items-end gap-3 rounded border border-gray/20 bg-white p-4">
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Sucursal
          <Combobox
            etiqueta="Sucursal"
            requerido
            value={sucursalId}
            alCambiar={(v) => v && navegar({ sucursal: v })}
            opciones={sucursales.map((s) => ({ valor: s.id, etiqueta: s.nombre }))}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Fecha
          <input
            type="date"
            value={fecha}
            onChange={(e) => navegar({ fecha: e.target.value })}
            className="rounded border border-gray/40 px-2 py-1"
          />
          <span className="text-xs font-normal text-gray">Vacío = hoy</span>
        </label>
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Estado
          <select
            value={estado}
            onChange={(e) => navegar({ estado: e.target.value })}
            className="rounded border border-gray/40 px-2 py-1"
          >
            <option value="">Todos</option>
            {ESTADOS.map((e) => (
              <option key={e} value={e}>
                {e}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="flex gap-6 rounded bg-cream px-4 py-3 text-sm">
        <span>
          <strong className="tabular-nums">{totales.cantidad}</strong> ventas cobradas
        </span>
        <span>
          <strong className="tabular-nums">S/ {totales.monto.toFixed(2)}</strong> en total
        </span>
        <span className={totales.abiertas > 0 ? "text-secondary" : "text-gray"}>
          <strong className="tabular-nums">{totales.abiertas}</strong> sin cobrar
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[44rem] border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray/30 text-left text-xs uppercase text-gray">
              <th className="py-2 pr-4 font-semibold">Orden</th>
              <th className="py-2 pr-4 font-semibold">Canal / modalidad</th>
              <th className="py-2 pr-4 font-semibold">Atención</th>
              <th className="py-2 pr-4 font-semibold">Total</th>
              <th className="py-2 pr-4 font-semibold">Estado</th>
              <th className="py-2 pr-4 font-semibold">Comprobante</th>
              <th className="py-2 font-semibold"></th>
            </tr>
          </thead>
          <tbody>
            {ventas.length === 0 && (
              <tr>
                <td colSpan={7} className="py-3 text-gray">
                  No hay ventas en esa jornada.
                </td>
              </tr>
            )}
            {ventas.map((v) => (
              <tr key={v.id} className="border-b border-gray/15 align-top">
                <td className="py-2 pr-4 font-semibold text-dark tabular-nums">
                  #{v.numero_orden}
                </td>
                <td className="py-2 pr-4">
                  {v.canal} · {v.modalidad}
                </td>
                <td className="py-2 pr-4">{v.referencia_atencion ?? "—"}</td>
                <td className="py-2 pr-4 tabular-nums">S/ {v.total}</td>
                <td className="py-2 pr-4">
                  <EstadoVenta estado={v.estado} />
                </td>
                <td className="py-2 pr-4">
                  <CeldaComprobante comprobante={comprobantes[v.id]} />
                </td>
                <td className="py-2">
                  <Acciones venta={v} comprobante={comprobantes[v.id]} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
