"use client";

import { useActionState, useEffect, useRef, useState, useTransition } from "react";

import {
  cambiarEstadoPosAction,
  entregarCustodiaAction,
  reabrirCierreAction,
  registrarPosAction,
  type EstadoCaja,
} from "./actions";

export type Turno = {
  cierre_id: string;
  apertura_caja_id: string;
  punto_venta_id: string;
  caja: string;
  abierta_desde: string;
  monto_apertura: string;
  descuadre_monto: string;
  descuadre_atribucion: string | null;
  estado: string;
  custodia_destino: string | null;
  custodia_id: string | null;
  custodia_estado: string | null;
  custodia_monto: string | null;
  correcciones: { motivo: string; descuadre_anterior: string }[] | null;
};

export type Pos = {
  id: string;
  serie: string;
  codigo_comercio: string;
  operador: string | null;
  estado: string;
  es_emergencia: boolean;
  sucursal_id: string | null;
};

export type Sucursal = { id: string; nombre: string };

const ESTADO_INICIAL: EstadoCaja = { error: "", ok: false };

/** La cadena de custodia solo avanza (RN-MDP-002): del cajón al encargado,
 * del encargado a contabilidad, y de ahí a depositado/disponible. El paso
 * siguiente no se elige de una lista porque no hay dos caminos — es uno
 * solo, y ofrecer un `<select>` sugeriría que se puede saltear un tramo.
 *
 * El primer escalón es el que **de hecho** se usa desde ADR-049: un turno
 * recién cerrado queda `en_caja`, porque el cajero cierra solo y la plata
 * sigue en el cajón hasta que alguien firme que la recibió. Antes ese estado
 * existía en la tabla de transiciones y no lo escribía nadie. */
const SIGUIENTE: Record<string, { estado: string; boton: string }> = {
  en_caja: { estado: "en_supervisor", boton: "Recibe el encargado" },
  en_supervisor: { estado: "en_contabilidad", boton: "Recibe contabilidad" },
  en_contabilidad: { estado: "disponible", boton: "Marcar disponible" },
};

/** Los enums de la base se leen como los nombra el negocio, no como los
 * escribe la columna. */
const DESTINO: Record<string, string> = {
  local_caja_fuerte: "caja fuerte del local",
  traslado_contabilidad: "traslado a contabilidad",
};

const ESTADO_CIERRE: Record<string, string> = {
  en_proceso: "en recuento",
  conforme: "conforme",
  con_irregularidad: "con irregularidad",
};

const TRAMO: Record<string, string> = {
  // Dice de quién es la responsabilidad, no dónde está el sobre: un turno
  // cerrado sigue siendo del cajero hasta que otro firme haberlo recibido.
  en_caja: "en el cajón, a cargo del cajero",
  en_supervisor: "con el encargado",
  en_contabilidad: "en contabilidad",
  disponible: "disponible",
};

function Monto({ valor }: { valor: string | null }) {
  return <span className="tabular-nums">S/ {valor ?? "0.00"}</span>;
}

/** Diálogo con firma de PIN. Los dos flujos que lo usan —recibir el efectivo
 * y reabrir un cierre— son el mismo formulario más un campo propio, así que
 * comparten envoltorio en vez de repetir el bloque de usuario/PIN. */
function DialogoFirmado({
  etiqueta,
  titulo,
  descripcion,
  accion,
  ocultos,
  children,
  destructivo,
}: {
  etiqueta: string;
  titulo: string;
  descripcion: React.ReactNode;
  accion: (previo: EstadoCaja, datos: FormData) => Promise<EstadoCaja>;
  ocultos: Record<string, string>;
  children?: React.ReactNode;
  destructivo?: boolean;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [estado, formAction, pendiente] = useActionState(accion, ESTADO_INICIAL);

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
        className={`text-xs font-bold hover:underline ${
          destructivo ? "text-secondary" : "text-primary"
        }`}
      >
        {etiqueta}
      </button>
      <dialog ref={dialogRef} className="w-full max-w-sm rounded-lg p-0 backdrop:bg-dark/40">
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          {Object.entries(ocultos).map(([nombre, valor]) => (
            <input key={nombre} type="hidden" name={nombre} value={valor} />
          ))}
          <h2 className="font-heading text-lg italic uppercase text-dark">{titulo}</h2>
          <p className="text-sm text-gray">{descripcion}</p>
          {children}
          <div className="grid grid-cols-2 gap-2">
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Usuario
              <input name="username" autoComplete="off" required />
            </label>
            <label className="flex flex-col gap-1 text-sm font-semibold">
              PIN
              <input name="pin" type="password" inputMode="numeric" autoComplete="off" required />
            </label>
          </div>
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
              {pendiente ? "Firmando..." : "Firmar"}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

function AccionesTurno({ turno }: { turno: Turno }) {
  const paso = turno.custodia_estado ? SIGUIENTE[turno.custodia_estado] : undefined;
  return (
    <div className="flex items-center gap-3">
      {turno.custodia_id && paso && (
        <DialogoFirmado
          etiqueta={paso.boton}
          titulo="Recibir el efectivo"
          descripcion={
            <>
              {turno.caja} · <Monto valor={turno.custodia_monto} />. Firma quien{" "}
              <strong>recibe</strong>: es el eslabón que después responde por esa plata.
            </>
          }
          accion={entregarCustodiaAction}
          ocultos={{
            custodia_id: turno.custodia_id,
            estado_siguiente: paso.estado,
          }}
        />
      )}
      {turno.estado !== "en_proceso" && (
        <DialogoFirmado
          etiqueta="Reabrir"
          titulo="Reabrir el cierre"
          descripcion={
            <>
              Devuelve el turno a recuento. Solo mientras el efectivo siga en el local: una
              vez que llegó a contabilidad, corregir es un asiento y no un recuento.
            </>
          }
          accion={reabrirCierreAction}
          ocultos={{ cierre_id: turno.cierre_id }}
          destructivo
        >
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Motivo
            <input
              name="motivo"
              minLength={5}
              maxLength={200}
              required
              placeholder="Por qué se vuelve a contar"
            />
          </label>
        </DialogoFirmado>
      )}
    </div>
  );
}

function CeldaDescuadre({ turno: t }: { turno: Turno }) {
  if (Number(t.descuadre_monto) === 0) {
    return (
      <td className="py-2 pr-4">
        <span className="text-gray">—</span>
      </td>
    );
  }
  return (
    <td className="py-2 pr-4">
      <span className="font-semibold text-secondary">
        <Monto valor={t.descuadre_monto} />
        {t.descuadre_atribucion && (
          <span className="block text-xs font-normal text-gray">
            {t.descuadre_atribucion}
          </span>
        )}
      </span>
    </td>
  );
}

function CeldaCustodia({ turno: t }: { turno: Turno }) {
  return (
    <td className="py-2 pr-4">
      <span className="text-xs text-gray">
        {(t.custodia_estado && TRAMO[t.custodia_estado]) ?? "—"}
      </span>
      {t.custodia_destino && (
        <span className="block text-xs text-gray">
          → {DESTINO[t.custodia_destino] ?? t.custodia_destino}
        </span>
      )}
    </td>
  );
}

/** Una fila de la tabla, en su propio componente: dibujarla dentro del
 * `map` metía descuadre, estado, correcciones y custodia en la misma
 * función y la dejaba sobre el límite de complejidad del proyecto. */
function FilaTurno({ turno: t }: { turno: Turno }) {
  return (
    <tr key={t.cierre_id} className="border-b border-gray/15">
      <td className="py-2 pr-4 font-semibold text-dark">{t.caja}</td>
      <td className="py-2 pr-4">
        <Monto valor={t.monto_apertura} />
      </td>
      <CeldaDescuadre turno={t} />
      <td className="py-2 pr-4">
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
            t.estado === "conforme"
              ? "bg-accent/30 text-dark"
              : "bg-secondary/15 text-secondary"
          }`}
        >
          {ESTADO_CIERRE[t.estado] ?? t.estado}
        </span>
        {/* Un cierre corregido no se ve distinto del que salió bien a
            la primera si no se dice: el rastro es justo el punto. */}
        {t.correcciones && t.correcciones.length > 0 && (
          <span className="block text-xs text-gray">
            {t.correcciones.length} corrección(es)
          </span>
        )}
      </td>
      <CeldaCustodia turno={t} />
      <td className="py-2">
        <AccionesTurno turno={t} />
      </td>
    </tr>
  );
}

function TablaTurnos({ turnos }: { turnos: Turno[] }) {
  if (turnos.length === 0) {
    return (
      <p className="rounded bg-cream px-3 py-2 text-sm text-gray">
        Ningún turno cerrado en el rango.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[52rem] border-collapse text-sm">
        <thead>
          <tr className="border-b border-gray/30 text-left text-xs uppercase text-gray">
            <th className="py-2 pr-4 font-semibold">Caja</th>
            <th className="py-2 pr-4 font-semibold">Apertura</th>
            <th className="py-2 pr-4 font-semibold">Descuadre</th>
            <th className="py-2 pr-4 font-semibold">Cierre</th>
            <th className="py-2 pr-4 font-semibold">Efectivo</th>
            <th className="py-2 font-semibold"></th>
          </tr>
        </thead>
        <tbody>
          {turnos.map((t) => (
            <FilaTurno key={t.cierre_id} turno={t} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AltaPos({ sucursales }: { sucursales: Sucursal[] }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [estado, formAction, pendiente] = useActionState(registrarPosAction, ESTADO_INICIAL);

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
        className="self-start rounded bg-primary px-3 py-1.5 text-sm font-bold text-white hover:bg-secondary"
      >
        Registrar terminal
      </button>
      <dialog ref={dialogRef} className="w-full max-w-sm rounded-lg p-0 backdrop:bg-dark/40">
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg italic uppercase text-dark">
            Registrar terminal
          </h2>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Serie
            <input name="serie" minLength={2} maxLength={50} required />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Código de comercio
            <input name="codigo_comercio" minLength={2} maxLength={50} required />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Operador
            <input name="operador" maxLength={50} placeholder="Izipay, Niubiz..." />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Sucursal
            <select name="sucursal_id" defaultValue="">
              <option value="">Emergencia (pool de contabilidad)</option>
              {sucursales.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.nombre}
                </option>
              ))}
            </select>
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
              {pendiente ? "Guardando..." : "Guardar"}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

function EstadoPos({ pos }: { pos: Pos }) {
  const [pendiente, startTransition] = useTransition();
  const siguiente = pos.estado === "operativo" ? "averiado" : "operativo";
  return (
    <div className="flex items-center gap-3">
      <span
        className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
          pos.estado === "operativo" ? "bg-accent/30 text-dark" : "bg-secondary/15 text-secondary"
        }`}
      >
        {pos.estado}
      </span>
      <button
        type="button"
        disabled={pendiente}
        onClick={() => startTransition(() => void cambiarEstadoPosAction(pos.id, siguiente))}
        className="text-xs font-semibold text-primary hover:underline"
      >
        Marcar {siguiente}
      </button>
    </div>
  );
}

export function CajaCliente({
  turnos,
  pos,
  sucursales,
}: {
  turnos: Turno[];
  pos: Pos[];
  sucursales: Sucursal[];
}) {
  const [verPos, setVerPos] = useState(false);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="font-heading text-lg italic uppercase text-dark">Turnos cerrados hoy</h2>
        <p className="text-sm text-gray">
          El cajero abre y cierra su turno solo; el efectivo queda en el cajón a su nombre
          hasta que alguien firme que lo recibió. De ahí en adelante cada tramo de la cadena
          lo firma quien recibe. Un cierre con faltante se reabre y se recuenta: no se
          reescribe.
        </p>
      </div>
      <TablaTurnos turnos={turnos} />

      <div className="mt-4 border-t border-gray/20 pt-4">
        <button
          type="button"
          onClick={() => setVerPos((v) => !v)}
          className="font-heading text-lg italic uppercase text-dark hover:underline"
        >
          Terminales de tarjeta ({pos.length}) {verPos ? "▾" : "▸"}
        </button>
        {verPos && (
          <div className="mt-3 flex flex-col gap-3">
            <p className="text-sm text-gray">
              Se verifican al abrir cada turno. Los que no cuelgan de ninguna sucursal son
              los de emergencia del pool: viajan al local que se queda sin terminal.
            </p>
            <AltaPos sucursales={sucursales} />
            {pos.length === 0 ? (
              <p className="rounded bg-cream px-3 py-2 text-sm text-gray">
                Sin terminales registrados.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[40rem] border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-gray/30 text-left text-xs uppercase text-gray">
                      <th className="py-2 pr-4 font-semibold">Serie</th>
                      <th className="py-2 pr-4 font-semibold">Comercio</th>
                      <th className="py-2 pr-4 font-semibold">Operador</th>
                      <th className="py-2 pr-4 font-semibold">Ubicación</th>
                      <th className="py-2 font-semibold">Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pos.map((p) => (
                      <tr key={p.id} className="border-b border-gray/15">
                        <td className="py-2 pr-4 font-semibold text-dark">{p.serie}</td>
                        <td className="py-2 pr-4">{p.codigo_comercio}</td>
                        <td className="py-2 pr-4">{p.operador ?? "—"}</td>
                        <td className="py-2 pr-4">
                          {p.sucursal_id
                            ? (sucursales.find((s) => s.id === p.sucursal_id)?.nombre ??
                              "sucursal")
                            : "emergencia"}
                        </td>
                        <td className="py-2">
                          <EstadoPos pos={p} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
