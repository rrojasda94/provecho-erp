"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import {
  BOTON_FILA,
  DialogoFormulario,
  valor,
} from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { Combobox } from "@/components/ui/combobox";

import { guardarPuntoVentaAction } from "../actions";

export type Sucursal = { id: string; nombre: string };
export type PuntoVenta = {
  id: string;
  sucursal_id: string;
  canal: string;
  serie_boleta: string;
  serie_factura: string;
  serie_nc_boleta: string | null;
  serie_nc_factura: string | null;
  hardware_id: string | null;
  modalidades_habilitadas: string[] | null;
  politica_pago: string;
};

const MODALIDADES = [
  { valor: "mesa", etiqueta: "Mesa" },
  { valor: "takeout", etiqueta: "Para llevar" },
  { valor: "delivery", etiqueta: "Delivery" },
];

function CamposPuntoVenta({
  sucursales,
  punto,
}: {
  sucursales: Sucursal[];
  punto?: PuntoVenta;
}) {
  const p: Partial<PuntoVenta> = punto ?? {};
  // `null` significa las tres (RN-MDC-001): en el formulario se ven las tres
  // marcadas, que es lo que esa caja efectivamente atiende.
  const marcadas = p.modalidades_habilitadas ?? MODALIDADES.map((m) => m.valor);

  return (
    <>
      {punto ? (
        <p className="text-sm text-gray">
          Caja de <strong>{sucursales.find((s) => s.id === p.sucursal_id)?.nombre}</strong>.
          Una caja no se muda de local: sus comprobantes y cierres cuelgan de ahí.
        </p>
      ) : (
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Sucursal
          <Combobox
            name="sucursal_id"
            etiqueta="Sucursal"
            requerido
            marcador="Elige la sucursal..."
            opciones={sucursales.map((s) => ({ valor: s.id, etiqueta: s.nombre }))}
          />
        </label>
      )}

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Canal
        <select name="canal" defaultValue={valor(p.canal) || "trabajador"}>
          <option value="trabajador">Trabajador (caja física del local)</option>
          <option value="web">Web</option>
          <option value="kiosko">Kiosko de autoatención</option>
        </select>
      </label>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Política de pago
        <select
          name="politica_pago"
          defaultValue={valor(p.politica_pago) || "al_finalizar"}
        >
          <option value="al_finalizar">Al finalizar (se cobra al cerrar la mesa)</option>
          <option value="adelantado">Adelantado (se cobra antes de despachar)</option>
        </select>
        <span className="text-xs font-normal text-gray">
          Web y kiosko cobran siempre por adelantado: no hay cajero que persiga el
          pago al final.
        </span>
      </label>

      <fieldset className="flex flex-col gap-1 text-sm font-semibold">
        <legend>Series SUNAT</legend>
        <span className="text-xs font-normal text-gray">
          Una letra y tres caracteres: <code>B001</code> para boletas,{" "}
          <code>F001</code> para facturas. No se repiten dentro de la empresa — el
          correlativo es único por empresa y serie.
        </span>
        <div className="grid grid-cols-2 gap-2">
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Boleta
            <input
              name="serie_boleta"
              required
              maxLength={10}
              placeholder="B001"
              defaultValue={valor(p.serie_boleta)}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Factura
            <input
              name="serie_factura"
              required
              maxLength={10}
              placeholder="F001"
              defaultValue={valor(p.serie_factura)}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            NC de boleta
            <input
              name="serie_nc_boleta"
              maxLength={10}
              placeholder="BC01"
              defaultValue={valor(p.serie_nc_boleta)}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            NC de factura
            <input
              name="serie_nc_factura"
              maxLength={10}
              placeholder="FC01"
              defaultValue={valor(p.serie_nc_factura)}
            />
          </label>
        </div>
        <span className="text-xs font-normal text-gray">
          Sin serie de nota de crédito, esta caja no puede acreditar lo que emitió:
          la NC numera aparte del documento que corrige.
        </span>
      </fieldset>

      <fieldset className="flex flex-col gap-1 text-sm font-semibold">
        <legend>Modalidades que atiende</legend>
        {MODALIDADES.map((m) => (
          <label key={m.valor} className="flex items-center gap-2 font-normal">
            <input
              type="checkbox"
              name="modalidades_habilitadas"
              value={m.valor}
              defaultChecked={marcadas.includes(m.valor)}
            />
            {m.etiqueta}
          </label>
        ))}
      </fieldset>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Identificador del equipo
        <input
          name="hardware_id"
          maxLength={50}
          placeholder="Opcional — TPV-01"
          defaultValue={valor(p.hardware_id)}
        />
        <span className="text-xs font-normal text-gray">
          Para distinguir dos cajas físicas del mismo local. Un punto de venta web
          no lleva ninguno.
        </span>
      </label>
    </>
  );
}

function DialogoNuevoPuntoVenta({ sucursales }: { sucursales: Sucursal[] }) {
  return (
    <DialogoFormulario
      titulo="Nuevo punto de venta"
      disparador="+ Nuevo punto de venta"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={guardarPuntoVentaAction}
      envioDeshabilitado={sucursales.length === 0}
      ayuda={
        sucursales.length === 0
          ? "Primero da de alta una sucursal: una caja siempre pertenece a un local."
          : undefined
      }
    >
      <CamposPuntoVenta sucursales={sucursales} />
    </DialogoFormulario>
  );
}

function DialogoEditarPuntoVenta({
  punto,
  sucursales,
}: {
  punto: PuntoVenta;
  sucursales: Sucursal[];
}) {
  return (
    <DialogoFormulario
      titulo="Editar punto de venta"
      disparador="Editar"
      claseDisparador={BOTON_FILA}
      accion={guardarPuntoVentaAction}
      ayuda="Cambiar una serie no reescribe lo ya emitido: cada comprobante guarda la suya al emitirse. Los nuevos salen con la serie corregida."
    >
      <input type="hidden" name="id" value={punto.id} />
      <CamposPuntoVenta sucursales={sucursales} punto={punto} />
    </DialogoFormulario>
  );
}

export function PuntosVentaCliente({
  puntos,
  sucursales,
}: {
  puntos: PuntoVenta[];
  sucursales: Sucursal[];
}) {
  const nombreSucursal = useMemo(
    () => new Map(sucursales.map((s) => [s.id, s.nombre])),
    [sucursales],
  );

  const columnas: ColumnDef<PuntoVenta>[] = useMemo(
    () => [
      {
        id: "sucursal",
        header: "Sucursal",
        accessorFn: (p) => nombreSucursal.get(p.sucursal_id) ?? "—",
      },
      { accessorKey: "canal", header: "Canal" },
      { accessorKey: "serie_boleta", header: "Boleta" },
      { accessorKey: "serie_factura", header: "Factura" },
      {
        id: "notas_credito",
        header: "Notas de crédito",
        accessorFn: (p) =>
          [p.serie_nc_boleta, p.serie_nc_factura].filter(Boolean).join(" / ") ||
          "No emite",
      },
      {
        id: "modalidades",
        header: "Atiende",
        accessorFn: (p) => (p.modalidades_habilitadas ?? ["todas"]).join(", "),
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => (
          <DialogoEditarPuntoVenta punto={row.original} sucursales={sucursales} />
        ),
      },
    ],
    [nombreSucursal, sucursales],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl italic uppercase text-dark">
          Puntos de venta
        </h1>
        <DialogoNuevoPuntoVenta sucursales={sucursales} />
      </div>
      <p className="text-sm text-gray">
        La caja de cada local: es lo que el PDV pide al arrancar y de donde salen las
        series con las que se emite. Sin al menos una, la sucursal no puede vender.
      </p>
      <TablaDatos
        columnas={columnas}
        datos={puntos}
        placeholderBusqueda="Buscar por sucursal o serie..."
      />
    </div>
  );
}
