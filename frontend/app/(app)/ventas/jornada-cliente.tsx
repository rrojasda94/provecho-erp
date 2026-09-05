"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";

import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";

import {
  anularVentaAction,
  emitirNotaCreditoAction,
  lineasDeVentaAction,
  reintentarComprobanteAction,
  type EstadoVenta,
  type LineaVenta,
} from "./actions";
import { Combobox } from "@/components/ui/combobox";
import { tienePermiso } from "@/lib/permisos";

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

// Los cinco valores de `estado_venta`, en el orden en que una venta los
// recorre. Salen de `sales.domain.rules.ESTADOS_VENTA` y un test de
// coherencia impide que vuelvan a separarse: `entregada` no existe acá —es
// estado de ítem, del KDS— y sin `facturada` no había forma de listar lo
// cobrado, que es donde termina casi todo. `cerrada` es el consumo de
// personal ya entregado (RN-COM-027): no se cobra, y sin este filtro no
// habría forma de listarlo en la jornada.
const ESTADOS = ["orden", "pagada", "facturada", "cerrada", "anulada"];

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

/** Lo que se ofrece cuando la emisión falló. Reintentar exige el permiso de
 * emitir; el motivo del rechazo se muestra igual sin él, que es la mitad útil
 * de la celda para quien solo mira la jornada. */
function AvisoEmision({
  comprobante,
  permisos,
}: {
  comprobante: Comprobante;
  permisos: string[];
}) {
  const [pendiente, startTransition] = useTransition();
  const [error, setError] = useState("");
  const detalle = error || comprobante.detalle_emision;

  return (
    <>
      {tienePermiso(permisos, "sales.emitir_comprobante") && (
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
      )}
      {detalle && <span className="text-xs text-secondary">{detalle}</span>}
    </>
  );
}

function CeldaComprobante({
  comprobante,
  permisos,
}: {
  comprobante?: Comprobante;
  permisos: string[];
}) {
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
      {fallo && <AvisoEmision comprobante={comprobante} permisos={permisos} />}
    </div>
  );
}

// Catálogo 09 de SUNAT, con los cinco motivos que este negocio produce. Los
// dos de corrección no dan de baja la venta: arreglan el papel.
const MOTIVOS_NC = [
  { codigo: "01", texto: "Anulación de la operación", corrige: false },
  { codigo: "06", texto: "Devolución total", corrige: false },
  { codigo: "07", texto: "Devolución por ítem", corrige: false },
  { codigo: "02", texto: "Anulación por error en el RUC", corrige: true },
  { codigo: "03", texto: "Corrección por error en la descripción", corrige: true },
];

/** Qué se devuelve de cada línea. Los tres estados de la carga se dibujan
 * distinto a propósito: "todavía no llegó", "falló" y "esta venta no tiene
 * líneas" llevaban al mismo cartel, y el fallo se leía como una venta vacía
 * — justo antes de acreditarla. */
function LineasAcreditables({
  lineas,
  cargando,
  error,
}: {
  lineas: LineaVenta[];
  cargando: boolean;
  error: string;
}) {
  return (
    <div className="mt-1 flex flex-col gap-1.5">
      {cargando && <span className="text-xs text-gray">Cargando las líneas...</span>}
      {error && (
        <span role="alert" className="text-xs font-semibold text-secondary">
          {error} No se puede acreditar por línea sin saber qué se vendió; vuelve a
          abrir el diálogo para reintentar.
        </span>
      )}
      {!cargando && !error && lineas.length === 0 && (
        <span className="text-xs text-gray">Esta venta no tiene líneas que acreditar.</span>
      )}
      {lineas.map((linea) => (
        <div key={linea.id} className="flex items-center gap-2 text-sm">
          <input type="hidden" name="linea_id" value={linea.id} />
          <span className="flex-1">
            {linea.nombre}{" "}
            <span className="text-xs text-gray">(vendidas {linea.cantidad})</span>
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
        Cero = no se devuelve. Cuenta contra lo que quede sin acreditar, no contra lo
        vendido.
      </span>
    </div>
  );
}

function DialogoNotaCredito({
  venta,
  comprobante,
}: {
  venta: Venta;
  comprobante: Comprobante;
}) {
  const [motivo, setMotivo] = useState("01");
  const [alcance, setAlcance] = useState<"total" | "parcial">("total");
  const [lineas, setLineas] = useState<LineaVenta[]>([]);
  const [errorLineas, setErrorLineas] = useState("");
  const [cargandoLineas, setCargandoLineas] = useState(false);

  // Las líneas acreditables se piden **antes** de abrir: el diálogo aparecía
  // vacío y se llenaba solo un instante después, justo debajo del cursor.
  const cargar = async () => {
    setMotivo("01");
    setAlcance("total");
    if (lineas.length > 0) return;
    setCargandoLineas(true);
    const r = await lineasDeVentaAction(venta.id);
    setLineas(r.lineas);
    setErrorLineas(r.error);
    setCargandoLineas(false);
  };

  const deCorreccion = MOTIVOS_NC.find((m) => m.codigo === motivo)?.corrige ?? false;

  return (
    <DialogoFormulario
      titulo={`Nota de crédito · ${comprobante.serie}-${comprobante.correlativo}`}
      disparador="Nota de crédito"
      claseDisparador="text-xs font-bold text-primary hover:underline"
      etiquetaEnvio="Emitir"
      etiquetaPendiente="Emitiendo..."
      accion={emitirNotaCreditoAction}
      ancho="max-w-lg"
      ayuda="Una venta cobrada no se anula, se acredita. La nota sale en serie propia y solo puede emitirse una vez por comprobante."
      alAbrir={cargar}
    >
      <input type="hidden" name="comprobante_id" value={comprobante.id} />

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
        <LineasAcreditables lineas={lineas} cargando={cargandoLineas} error={errorLineas} />
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

    </DialogoFormulario>
  );
}

/** Anular o acreditar, nunca las dos: antes de cobrar se anula, después
 * solo queda la nota de crédito (RN-CPP-009).
 *
 * El permiso decide si la acción se ofrece, no solo el estado: la API es
 * quien autoriza de verdad, pero un botón que siempre termina en 403 es peor
 * que no tenerlo. Anular admite `sales.cobrar` **o** `sales.anular` porque el
 * endpoint concede con cualquiera de los dos (`check_permission`): el cajero
 * cobra y no anula, el supervisor anula y no cobra. */
function puedeAnular(permisos: string[]): boolean {
  return tienePermiso(permisos, "sales.cobrar") || tienePermiso(permisos, "sales.anular");
}

function admiteNotaCredito(comprobante: Comprobante, permisos: string[]): boolean {
  return (
    comprobante.tipo !== "nc" &&
    comprobante.estado_emision === "aceptado" &&
    !comprobante.anulado_por_nc_id &&
    tienePermiso(permisos, "sales.emitir_nota_credito")
  );
}

function Acciones({
  venta,
  comprobante,
  permisos,
}: {
  venta: Venta;
  comprobante?: Comprobante;
  permisos: string[];
}) {
  const guion = <span className="text-xs text-gray">—</span>;
  if (venta.estado === "orden") {
    return puedeAnular(permisos) ? <BotonAnular venta={venta} /> : guion;
  }
  if (comprobante !== undefined && admiteNotaCredito(comprobante, permisos)) {
    return <DialogoNotaCredito venta={venta} comprobante={comprobante} />;
  }
  if (comprobante?.anulado_por_nc_id) {
    return <span className="text-xs text-gray">acreditado</span>;
  }
  return guion;
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
  permisos,
}: {
  ventas: Venta[];
  comprobantes: Record<string, Comprobante>;
  sucursales: Sucursal[];
  sucursalId: string;
  fecha: string;
  estado: string;
  permisos: string[];
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
                  <CeldaComprobante comprobante={comprobantes[v.id]} permisos={permisos} />
                </td>
                <td className="py-2">
                  <Acciones venta={v} comprobante={comprobantes[v.id]} permisos={permisos} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
