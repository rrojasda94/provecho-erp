"use client";

import Link from "next/link";
import { useActionState, useEffect, useRef } from "react";

import { Insignia, type Tono } from "@/components/estado/insignia";
import { Rastro } from "@/components/shell/rastro";
import { tienePermiso } from "@/lib/permisos";

import {
  anularOrdenCompraAction,
  emitirOrdenCompraAction,
  recibirOrdenCompraAction,
  registrarFacturaAction,
  type EstadoOrdenCompra,
} from "../actions";
import type { Articulo, OrdenCompra, Proveedor } from "../ordenes-compra-cliente";

export type RecepcionItem = {
  id: string;
  orden_compra_item_id: string;
  articulo_id: string;
  cantidad_recibida: string;
  costo_unitario: string;
  lote_codigo: string | null;
  fecha_vencimiento: string | null;
};

export type Recepcion = {
  id: string;
  fecha: string;
  comprobante_id: string | null;
  items: RecepcionItem[];
};

export type Comprobante = {
  id: string;
  tipo: string;
  serie: string;
  correlativo: number;
  emisor_num_doc: string | null;
  fecha_emision: string | null;
  total: string | null;
  sustento: string;
};

const ESTADO_INICIAL: EstadoOrdenCompra = { error: "", ok: false };

/** El estado de la OC, con el mismo criterio de tono que el resto del ERP:
 * el acento es «conforme», el rojo es «no pasó». */
const TONO_ESTADO: Record<string, Tono> = {
  borrador: "neutro",
  emitida: "info",
  recibida_parcial: "alerta",
  recibida: "exito",
  anulada: "peligro",
};

const ETIQUETA_TIPO: Record<string, string> = {
  factura: "Factura",
  boleta: "Boleta",
  rhe: "Recibo por honorarios",
  ticket_compra: "Ticket",
};

const SUSTENTOS = [
  ["contrato_credito", "Crédito del proveedor"],
  ["efectivo", "Efectivo"],
  ["voucher_medio_pago", "Voucher de medio de pago"],
  ["movimiento_bancario", "Movimiento bancario"],
] as const;

function soles(valor: string | null): string {
  if (valor === null) return "—";
  return `S/ ${Number(valor).toFixed(2)}`;
}

/** Un botón que dispara una acción sin formulario que llenar (emitir,
 * anular). `useActionState` y no `fetch`: es el mismo camino que el resto de
 * las mutaciones del ERP, con su error en pantalla. */
function BotonAccion({
  ordenId,
  accion,
  etiqueta,
  confirmacion,
  destructivo,
}: {
  ordenId: string;
  accion: typeof emitirOrdenCompraAction;
  etiqueta: string;
  confirmacion: string;
  destructivo?: boolean;
}) {
  const [estado, formAction, pendiente] = useActionState(accion, ESTADO_INICIAL);
  return (
    <form
      action={formAction}
      onSubmit={(e) => {
        if (!confirm(confirmacion)) e.preventDefault();
      }}
      className="flex flex-col gap-1"
    >
      <input type="hidden" name="orden_id" value={ordenId} />
      <button
        type="submit"
        disabled={pendiente}
        className={`rounded px-4 py-2 text-sm font-bold disabled:opacity-50 ${
          destructivo
            ? "border border-secondary text-secondary hover:bg-secondary/10"
            : "bg-primary text-white hover:bg-secondary"
        }`}
      >
        {pendiente ? "…" : etiqueta}
      </button>
      {estado.error && (
        <p role="alert" className="text-xs font-semibold text-secondary">
          {estado.error}
        </p>
      )}
    </form>
  );
}

/** Cuánto falta por recibir de cada línea. Es lo que precarga el formulario:
 * teclear de nuevo lo que el sistema ya sabe es el paso donde se equivoca
 * quien está apurado en el almacén. */
function pendienteDe(orden: OrdenCompra) {
  return (orden.items ?? [])
    .map((it) => ({
      ...it,
      pendiente: Number(it.cantidad) - Number(it.cantidad_recibida),
    }))
    .filter((it) => it.pendiente > 0);
}

function DialogoRecepcion({
  orden,
  articulos,
}: {
  orden: OrdenCompra;
  articulos: Articulo[];
}) {
  const dialogo = useRef<HTMLDialogElement>(null);
  const [estado, formAction, pendiente] = useActionState(
    recibirOrdenCompraAction,
    ESTADO_INICIAL,
  );
  const lineas = pendienteDe(orden);
  const porId = new Map(articulos.map((a) => [a.id, a]));

  useEffect(() => {
    if (estado.ok) dialogo.current?.close();
  }, [estado.ok]);

  return (
    <>
      <button
        type="button"
        onClick={() => dialogo.current?.showModal()}
        className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
      >
        Registrar recepción
      </button>
      <dialog ref={dialogo} className="w-full max-w-3xl rounded-lg p-0 backdrop:bg-dark/40">
        <form action={formAction} className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg text-dark">Qué llegó</h2>
          <p className="text-xs text-gray">
            Viene precargado con lo que falta. Corrige la cantidad si el
            proveedor entregó menos: la OC queda en <em>recibida parcial</em> y
            admite otra entrega después.
          </p>
          <input type="hidden" name="orden_id" value={orden.id} />

          <div className="flex flex-col gap-3">
            {lineas.map((it) => {
              const articulo = porId.get(it.articulo_id);
              return (
                <div key={it.id} className="rounded border border-gray/20 p-3">
                  <p className="text-sm font-semibold">
                    {articulo?.nombre ?? it.articulo_id}
                    <span className="ml-2 font-normal text-gray">
                      pendiente {it.pendiente}
                    </span>
                  </p>
                  <input type="hidden" name="orden_compra_item_id[]" value={it.id} />
                  <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
                    <label className="flex flex-col gap-1 text-xs font-semibold">
                      Cantidad
                      <input
                        name="cantidad_recibida[]"
                        type="number"
                        min="0"
                        step="0.01"
                        defaultValue={it.pendiente}
                      />
                    </label>
                    <label className="flex flex-col gap-1 text-xs font-semibold">
                      Costo unitario
                      <input
                        name="costo_recibido[]"
                        type="number"
                        min="0"
                        step="0.01"
                        defaultValue={it.costo_unitario}
                      />
                    </label>
                    {/* Lote y vencimiento solo donde significan algo: un
                        artículo que no controla lote los ignora (RN-VNC-002),
                        y pedirlos igual serían dos campos que nadie llena. */}
                    {articulo?.controla_lote ? (
                      <>
                        <label className="flex flex-col gap-1 text-xs font-semibold">
                          Lote
                          <input name="lote_codigo[]" type="text" maxLength={50} />
                        </label>
                        <label className="flex flex-col gap-1 text-xs font-semibold">
                          Vence
                          <input name="fecha_vencimiento[]" type="date" />
                        </label>
                      </>
                    ) : (
                      <>
                        <input type="hidden" name="lote_codigo[]" value="" />
                        <input type="hidden" name="fecha_vencimiento[]" value="" />
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {estado.error && (
            <p role="alert" className="text-sm font-semibold text-secondary">
              {estado.error}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => dialogo.current?.close()}
              className="rounded border border-gray px-4 py-2 text-sm font-semibold text-dark"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={pendiente}
              className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
            >
              {pendiente ? "Registrando…" : "Registrar"}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

/** Los campos del papel del proveedor. Se comparte con la compra directa,
 * que registra exactamente la misma factura en el mismo paso que la compra. */
export function CamposDeFactura({ rucSugerido }: { rucSugerido?: string | null }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Tipo
        <select name="tipo" defaultValue="factura">
          {Object.entries(ETIQUETA_TIPO).map(([valor, etiqueta]) => (
            <option key={valor} value={valor}>
              {etiqueta}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Serie
        <input name="serie" type="text" maxLength={10} placeholder="F001" required />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Número
        <input name="correlativo" type="number" min="1" step="1" required />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Fecha de emisión
        <input name="fecha_emision" type="date" />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Total del documento
        <input name="total" type="number" min="0.01" step="0.01" placeholder="Con IGV" />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        RUC del emisor
        <input
          name="emisor_num_doc"
          type="text"
          inputMode="numeric"
          maxLength={11}
          placeholder={rucSugerido ?? "El del proveedor"}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Sustento
        <select name="sustento" defaultValue="contrato_credito">
          {SUSTENTOS.map(([valor, etiqueta]) => (
            <option key={valor} value={valor}>
              {etiqueta}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        ¿Lleva IGV?
        {/* Tres estados: sin elegir manda el régimen de la empresa, que no es
            lo mismo que decir que no lleva (ADR-081). */}
        <select name="gravado_igv" defaultValue="">
          <option value="">Según el régimen de la empresa</option>
          <option value="si">Sí, con IGV</option>
          <option value="no">No, exonerada</option>
        </select>
      </label>
    </div>
  );
}

function DialogoFactura({ orden, ruc }: { orden: OrdenCompra; ruc: string | null }) {
  const dialogo = useRef<HTMLDialogElement>(null);
  const [estado, formAction, pendiente] = useActionState(
    registrarFacturaAction,
    ESTADO_INICIAL,
  );

  useEffect(() => {
    if (estado.ok) dialogo.current?.close();
  }, [estado.ok]);

  return (
    <>
      <button
        type="button"
        onClick={() => dialogo.current?.showModal()}
        className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
      >
        Registrar factura
      </button>
      <dialog ref={dialogo} className="w-full max-w-2xl rounded-lg p-0 backdrop:bg-dark/40">
        <form action={formAction} className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg text-dark">La factura del proveedor</h2>
          <p className="text-xs text-gray">
            Dar conformidad es lo que encola el pago en Contabilidad y lo que
            registra el crédito fiscal. Compras sustenta; nunca paga.
          </p>
          <input type="hidden" name="orden_id" value={orden.id} />
          <CamposDeFactura rucSugerido={ruc} />
          {estado.error && (
            <p role="alert" className="text-sm font-semibold text-secondary">
              {estado.error}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => dialogo.current?.close()}
              className="rounded border border-gray px-4 py-2 text-sm font-semibold text-dark"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={pendiente}
              className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
            >
              {pendiente ? "Registrando…" : "Dar conformidad"}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

function Acciones({
  orden,
  articulos,
  ruc,
  permisos,
  yaFacturada,
}: {
  orden: OrdenCompra;
  articulos: Articulo[];
  ruc: string | null;
  permisos: string[];
  yaFacturada: boolean;
}) {
  // Los estados salen de `purchases/domain/rules.py`. Acá deciden qué se
  // ofrece; quien manda sigue siendo la API — mostrar de más solo produce un
  // error legible, y mostrar de menos deja a alguien sin poder trabajar.
  const puedeEmitir = orden.estado === "borrador" && tienePermiso(permisos, "purchases.crear");
  const puedeRecibir =
    ["emitida", "recibida_parcial"].includes(orden.estado) &&
    tienePermiso(permisos, "purchases.recepcionar");
  const puedeAnular =
    ["borrador", "emitida"].includes(orden.estado) &&
    tienePermiso(permisos, "purchases.anular");
  const puedeFacturar =
    ["recibida", "recibida_parcial"].includes(orden.estado) &&
    !yaFacturada &&
    tienePermiso(permisos, "purchases.dar_conformidad");

  return (
    <div className="flex flex-wrap items-start gap-2">
      {puedeEmitir && (
        <BotonAccion
          ordenId={orden.id}
          accion={emitirOrdenCompraAction}
          etiqueta="Emitir"
          confirmacion="Emitir la orden la vuelve inmutable y la manda al proveedor. ¿Seguro?"
        />
      )}
      {puedeRecibir && <DialogoRecepcion orden={orden} articulos={articulos} />}
      {puedeFacturar && <DialogoFactura orden={orden} ruc={ruc} />}
      {puedeAnular && (
        <BotonAccion
          ordenId={orden.id}
          accion={anularOrdenCompraAction}
          etiqueta="Anular"
          confirmacion="Anular la orden no se deshace. ¿Seguro?"
          destructivo
        />
      )}
    </div>
  );
}

function ItemsDeLaOrden({
  orden,
  nombreDe,
}: {
  orden: OrdenCompra;
  nombreDe: (id: string) => string;
}) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-bold uppercase text-gray">Ítems</h2>
      <div className="overflow-x-auto rounded border border-gray/20">
        <table className="w-full text-sm">
          <thead className="bg-cream text-left text-xs uppercase text-gray">
            <tr>
              <th className="px-3 py-2">Artículo</th>
              <th className="px-3 py-2">Ordenado</th>
              <th className="px-3 py-2">Recibido</th>
              <th className="px-3 py-2">Pendiente</th>
              <th className="px-3 py-2">Costo</th>
              <th className="px-3 py-2">Subtotal</th>
            </tr>
          </thead>
          <tbody>
            {(orden.items ?? []).map((it) => {
              const falta = Number(it.cantidad) - Number(it.cantidad_recibida);
              return (
                <tr key={it.id} className="border-t border-gray/10">
                  <td className="px-3 py-2">{nombreDe(it.articulo_id)}</td>
                  <td className="px-3 py-2">{it.cantidad}</td>
                  <td className="px-3 py-2">{it.cantidad_recibida}</td>
                  <td className={`px-3 py-2 ${falta > 0 ? "font-semibold" : "text-gray"}`}>
                    {falta}
                  </td>
                  <td className="px-3 py-2">{soles(it.costo_unitario)}</td>
                  <td className="px-3 py-2">
                    {soles(String(Number(it.cantidad) * Number(it.costo_unitario)))}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Recepciones({
  recepciones,
  nombreDe,
}: {
  recepciones: Recepcion[];
  nombreDe: (id: string) => string;
}) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-bold uppercase text-gray">Recepciones</h2>
      {recepciones.length === 0 ? (
        <p className="text-sm text-gray">Todavía no llegó nada de esta orden.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {recepciones.map((r) => (
            <li key={r.id} className="rounded border border-gray/20 p-3 text-sm">
              <p className="font-semibold">{new Date(r.fecha).toLocaleString("es-PE")}</p>
              <ul className="mt-1 flex flex-col gap-0.5 text-gray">
                {r.items.map((it) => (
                  <li key={it.id}>
                    {nombreDe(it.articulo_id)} · {it.cantidad_recibida}
                    {it.lote_codigo ? ` · lote ${it.lote_codigo}` : ""}
                    {it.fecha_vencimiento ? ` · vence ${it.fecha_vencimiento}` : ""}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Facturas({ comprobantes }: { comprobantes: Comprobante[] }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-bold uppercase text-gray">Factura del proveedor</h2>
      {comprobantes.length === 0 ? (
        <p className="text-sm text-gray">
          Sin conformidad todavía. Registrarla es lo que encola el pago en
          Contabilidad y lo que registra el crédito fiscal.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {comprobantes.map((c) => (
            <li key={c.id} className="rounded border border-gray/20 p-3 text-sm">
              <p className="font-semibold">
                {ETIQUETA_TIPO[c.tipo] ?? c.tipo} {c.serie}-{c.correlativo}
              </p>
              <p className="text-gray">
                {c.fecha_emision ?? "sin fecha"}
                {c.emisor_num_doc ? ` · RUC ${c.emisor_num_doc}` : ""} · {soles(c.total)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function OrdenCompraCliente({
  orden,
  recepciones,
  comprobantes,
  proveedor,
  almacen,
  articulos,
  permisos,
}: {
  orden: OrdenCompra;
  recepciones: Recepcion[];
  comprobantes: Comprobante[];
  proveedor: Proveedor | null;
  almacen: string | null;
  articulos: Articulo[];
  permisos: string[];
}) {
  const nombreDeArticulo = (id: string) =>
    articulos.find((a) => a.id === id)?.nombre ?? id;
  const nombreProveedor = proveedor?.razon_social ?? proveedor?.ruc ?? "—";

  return (
    <section className="flex flex-col gap-6">
      <Rastro hoja={`${nombreProveedor} · S/ ${Number(orden.total).toFixed(2)}`} />

      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="font-heading text-xl italic uppercase text-dark">
            {nombreProveedor}
          </h1>
          <p className="flex flex-wrap items-center gap-2 text-sm text-gray">
            <Insignia tono={TONO_ESTADO[orden.estado] ?? "neutro"}>
              {orden.estado.replace("_", " ")}
            </Insignia>
            {/* ADR-082 prometió distinguirlas donde importa: una compra
                directa nace recibida y sustentada solo con su comprobante. */}
            <Insignia tono="info">
              {orden.origen === "directa" ? "Compra directa" : "Orden de compra"}
            </Insignia>
            <span>Destino: {almacen ?? "—"}</span>
            <span className="cifra font-semibold">S/ {Number(orden.total).toFixed(2)}</span>
          </p>
        </div>
        <Acciones
          orden={orden}
          articulos={articulos}
          ruc={proveedor?.ruc ?? null}
          permisos={permisos}
          yaFacturada={comprobantes.length > 0}
        />
      </header>

      <ItemsDeLaOrden orden={orden} nombreDe={nombreDeArticulo} />

      <Recepciones recepciones={recepciones} nombreDe={nombreDeArticulo} />
      <Facturas comprobantes={comprobantes} />

      <Link href="/compras/ordenes-compra" className="text-sm underline">
        Volver a Órdenes de compra
      </Link>
    </section>
  );
}
