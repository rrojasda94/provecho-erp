"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { primeroElDe } from "@/lib/destinos";

import { anularDevolucionAction, registrarDevolucionAction } from "./actions";

export type Devolucion = {
  id: string;
  almacen_id: string;
  origen: string;
  referencia_id: string | null;
  motivo: string;
  destino: string | null;
  estado: string;
  reporte_dirigido_a: string;
  observacion: string | null;
};

export type OpcionAlmacen = { id: string; nombre: string };
export type OpcionSku = { id: string; etiqueta: string };

/** Los mismos valores que el enum del servidor (`devoluciones.MOTIVOS`). */
const MOTIVOS = [
  ["vencido", "Vencido"],
  ["dañado", "Dañado"],
  ["incumplimiento_plazo", "Llegó fuera de plazo"],
  ["no_requerido", "No se necesitaba"],
  ["error_solicitud", "Error al solicitar"],
  ["duplicidad", "Pedido duplicado"],
] as const;

/** Qué se hace con lo que volvió (RN-INV-019). Solo aplica a cliente. */
const DESTINOS = [
  ["reintegro", "Vuelve al estante"],
  ["desecho", "Se desecha"],
  ["auditoria", "Se aparta para auditar"],
] as const;

/**
 * Devoluciones: registrar, ver y anular (RN-INV-019/020).
 *
 * Hasta 2026-08-13 era una tabla de solo lectura y la API completa quedaba
 * inalcanzable: la devolución existía en el modelo y no había forma de
 * registrar una sin llamar al endpoint a mano.
 */
export function DevolucionesCliente({
  devoluciones,
  resaltado,
  almacenes,
  skus,
}: {
  devoluciones: Devolucion[];
  resaltado: string | null;
  almacenes: OpcionAlmacen[];
  skus: OpcionSku[];
}) {
  const router = useRouter();
  const [error, setError] = useState("");

  const anular = async (id: string) => {
    setError("");
    const r = await anularDevolucionAction(id);
    if (!r.ok) setError(r.error);
    else router.refresh();
  };

  const columnas = useMemo<ColumnDef<Devolucion>[]>(
    () => [
      {
        header: "Origen",
        accessorKey: "origen",
        cell: ({ row }) => (
          <Link
            href={`/inventario/devoluciones/${row.original.id}`}
            className="font-semibold text-primary hover:underline"
          >
            {row.original.origen === "proveedor" ? "A proveedor" : "De cliente"}
          </Link>
        ),
      },
      { header: "Motivo", accessorKey: "motivo" },
      {
        header: "Destino",
        accessorKey: "destino",
        cell: ({ row }) => row.original.destino ?? "—",
      },
      { header: "Dirigida a", accessorKey: "reporte_dirigido_a" },
      { header: "Estado", accessorKey: "estado" },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) =>
          row.original.estado === "registrada" ? (
            <button
              type="button"
              className="text-xs text-secondary underline"
              onClick={() => anular(row.original.id)}
            >
              Anular
            </button>
          ) : null,
      },
    ],
    // `anular` se recrea en cada render y no aporta nada como dependencia:
    // lo que importa es que las columnas no se rearmen por cada tecla.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const ordenadas = useMemo(
    () => primeroElDe(devoluciones, resaltado, (d) => d.id),
    [devoluciones, resaltado],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-xl italic uppercase text-dark">
            Devoluciones
          </h1>
          <p className="text-xs text-gray">
            Lo que se le devuelve al proveedor y lo que devuelve un cliente.
            Mueve stock real y queda auditado.
          </p>
        </div>
        <FormularioDevolucion almacenes={almacenes} skus={skus} />
      </div>

      {error && <p className="text-sm text-secondary">{error}</p>}

      <TablaDatos
        columnas={columnas}
        datos={ordenadas}
        placeholderBusqueda="Buscar por motivo u origen..."
        vacio="Todavía no se registró ninguna devolución."
      />
    </div>
  );
}

function FormularioDevolucion({
  almacenes,
  skus,
}: {
  almacenes: OpcionAlmacen[];
  skus: OpcionSku[];
}) {
  const [origen, setOrigen] = useState("proveedor");

  return (
    <DialogoFormulario
      titulo="Registrar devolución"
      disparador="+ Nueva devolución"
      accion={registrarDevolucionAction}
      etiquetaEnvio="Registrar"
      ayuda="A proveedor la mercadería sale del almacén; de cliente entra, y el destino decide si vuelve al estante o se aparta."
      envioDeshabilitado={almacenes.length === 0 || skus.length === 0}
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Origen
        <select name="origen" value={origen} onChange={(e) => setOrigen(e.target.value)}>
          <option value="proveedor">A proveedor (sale del almacén)</option>
          <option value="cliente">De cliente (entra al almacén)</option>
        </select>
      </label>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Almacén
        <select name="almacen_id" defaultValue="">
          <option value="" disabled>
            Elegir…
          </option>
          {almacenes.map((a) => (
            <option key={a.id} value={a.id}>
              {a.nombre}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Qué se devuelve
        <select name="sku_id" defaultValue="">
          <option value="" disabled>
            Elegir…
          </option>
          {skus.map((s) => (
            <option key={s.id} value={s.id}>
              {s.etiqueta}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Cantidad
        <input name="cantidad" inputMode="decimal" defaultValue="1" />
      </label>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Motivo
        <select name="motivo" defaultValue="dañado">
          {MOTIVOS.map(([valor, etiqueta]) => (
            <option key={valor} value={valor}>
              {etiqueta}
            </option>
          ))}
        </select>
      </label>

      {/* El destino solo existe para una devolución de cliente: a proveedor
          la mercadería se va, así que no hay nada que decidir. */}
      {origen === "cliente" && (
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Qué se hace con lo que volvió
          <select name="destino" defaultValue="reintegro">
            {DESTINOS.map(([valor, etiqueta]) => (
              <option key={valor} value={valor}>
                {etiqueta}
              </option>
            ))}
          </select>
        </label>
      )}

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Observación
        <input name="observacion" maxLength={255} placeholder="Opcional" />
      </label>
    </DialogoFormulario>
  );
}
