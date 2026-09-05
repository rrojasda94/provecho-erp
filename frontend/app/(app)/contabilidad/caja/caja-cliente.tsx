"use client";

import { useState, useTransition } from "react";

import { Insignia } from "@/components/estado/insignia";
import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";

import {
  cambiarEstadoPosAction,
  entregarCustodiaAction,
  reabrirCierreAction,
  registrarArqueoAction,
  registrarPosAction,
  type EstadoCaja,
} from "./actions";
import { Combobox } from "@/components/ui/combobox";

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

/** Una caja abierta ahora mismo: es la única sobre la que se puede arquear,
 * porque el esperado sale del turno vivo. */
export type CajaAbierta = { punto_venta_id: string; caja: string };

export type Arqueo = {
  id: string;
  punto_venta_id: string;
  tipo: string;
  monto_esperado: string;
  monto_contado: string;
  diferencia: string;
  created_at: string;
};

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
  return (
    <DialogoFormulario
      titulo={titulo}
      disparador={etiqueta}
      claseDisparador={`text-xs font-bold hover:underline ${
        destructivo ? "text-status-danger" : "text-primary"
      }`}
      etiquetaEnvio="Firmar"
      etiquetaPendiente="Firmando..."
      accion={accion}
      ayuda={descripcion}
    >
      {Object.entries(ocultos).map(([nombre, valor]) => (
        <input key={nombre} type="hidden" name={nombre} value={valor} />
      ))}
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
    </DialogoFormulario>
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
  return (
    <DialogoFormulario
      titulo="Registrar terminal"
      disparador="Registrar terminal"
      claseDisparador="self-start inline-flex items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/85"
      accion={registrarPosAction}
    >
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
        <Combobox
          name="sucursal_id"
          etiqueta="Sucursal"
          marcador="Emergencia (pool de contabilidad)"
          opciones={sucursales.map((s) => ({ valor: s.id, etiqueta: s.nombre }))}
        />
      </label>
    </DialogoFormulario>
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

/** Contar el efectivo del cajón y compararlo contra lo que el sistema espera
 * (PROC-CTB-005).
 *
 * El monto esperado **no se teclea**: lo calcula el servidor con la apertura,
 * lo cobrado en efectivo y los movimientos del turno. Si lo mandara la
 * pantalla, el arqueo no probaría nada — sería contar y escribir el número
 * que uno quiere que dé.
 *
 * Solo se ofrecen las cajas abiertas: sobre un turno cerrado no hay cajón que
 * contar, hay un cierre que recontar, y eso es otra cosa (RN-MDP-005). */
function DialogoArqueo({ cajas }: { cajas: CajaAbierta[] }) {
  const [puntoVenta, setPuntoVenta] = useState("");
  return (
    <DialogoFormulario
      titulo="Arquear una caja"
      disparador="+ Arquear"
      etiquetaEnvio="Registrar"
      etiquetaPendiente="Registrando..."
      accion={registrarArqueoAction}
      envioDeshabilitado={cajas.length === 0}
      ayuda="Contá el efectivo del cajón y anotá el total. El esperado lo calcula el sistema: la diferencia es el hallazgo."
      alAbrir={() => setPuntoVenta("")}
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Caja
        <Combobox
          name="punto_venta_id"
          etiqueta="Caja"
          requerido
          marcador="Elegir caja abierta..."
          value={puntoVenta}
          alCambiar={(v) => setPuntoVenta(v ?? "")}
          opciones={cajas.map((c) => ({ valor: c.punto_venta_id, etiqueta: c.caja }))}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Tipo
        <select name="tipo" defaultValue="sorpresa">
          <option value="sorpresa">Sorpresa</option>
          <option value="programado">Programado</option>
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Efectivo contado
        <input name="monto_contado" type="number" step="0.01" min="0" required />
      </label>
    </DialogoFormulario>
  );
}

function TablaArqueos({ arqueos, cajas }: { arqueos: Arqueo[]; cajas: CajaAbierta[] }) {
  if (arqueos.length === 0) {
    return (
      <p className="rounded bg-cream px-3 py-2 text-sm text-gray">
        Todavía no se arqueó ninguna caja abierta.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[38rem] border-collapse text-sm">
        <thead>
          <tr className="border-b border-gray/30 text-left text-xs uppercase text-gray">
            <th className="py-2 pr-4 font-semibold">Caja</th>
            <th className="py-2 pr-4 font-semibold">Tipo</th>
            <th className="py-2 pr-4 font-semibold">Esperado</th>
            <th className="py-2 pr-4 font-semibold">Contado</th>
            <th className="py-2 font-semibold">Diferencia</th>
          </tr>
        </thead>
        <tbody>
          {arqueos.map((a) => {
            const dif = Number(a.diferencia);
            return (
              <tr key={a.id} className="border-b border-gray/15">
                <td className="py-2 pr-4 font-semibold text-dark">
                  {cajas.find((c) => c.punto_venta_id === a.punto_venta_id)?.caja ?? "caja"}
                </td>
                <td className="py-2 pr-4">{a.tipo}</td>
                <td className="py-2 pr-4 cifra">S/ {a.monto_esperado}</td>
                <td className="py-2 pr-4 cifra">S/ {a.monto_contado}</td>
                <td className="py-2">
                  {/* Cero es el resultado bueno y se lee como tal; cualquier
                      otra cosa es un hallazgo, sobre o falte. */}
                  <Insignia tono={dif === 0 ? "exito" : "alerta"}>
                    S/ {a.diferencia}
                  </Insignia>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function CajaCliente({
  turnos,
  pos,
  sucursales,
  cajasAbiertas,
  arqueos,
  puedeArquear,
}: {
  turnos: Turno[];
  pos: Pos[];
  sucursales: Sucursal[];
  cajasAbiertas: CajaAbierta[];
  arqueos: Arqueo[];
  puedeArquear: boolean;
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

      <div className="mt-4 flex flex-col gap-3 border-t border-gray/20 pt-4">
        <div className="flex items-center justify-between gap-4">
          <h2 className="font-heading text-lg italic uppercase text-dark">Arqueos</h2>
          {puedeArquear && <DialogoArqueo cajas={cajasAbiertas} />}
        </div>
        <p className="text-sm text-gray">
          El conteo sorpresa del cajón contra lo que el sistema espera
          (PROC-CTB-005). Se arquea una caja abierta: sobre un turno cerrado ya
          no hay cajón que contar.
        </p>
        <TablaArqueos arqueos={arqueos} cajas={cajasAbiertas} />
      </div>

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
