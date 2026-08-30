"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { Combobox } from "@/components/ui/combobox";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { pedir } from "@/lib/cliente-api";
import { primeroElDe } from "@/lib/destinos";
import { tienePermiso } from "@/lib/permisos";

import { registrarEntradaStockAction } from "./actions";

export type Ajuste = {
  id: string;
  almacen_id: string;
  sku_id: string;
  cantidad: string;
  motivo: string;
  estado: string;
  conteo_id: string | null;
  solicitado_por: string;
  aprobado_por: string | null;
  dentro_margen: boolean;
  lote_id: string | null;
};

export type OpcionAlmacen = { id: string; nombre: string };
export type OpcionSku = { id: string; etiqueta: string; controlaLote: boolean };

/** Los únicos dos motivos con delta positivo (`rules.signo_ajuste_valido`
 * del servidor): `faltante`/`merma` solo aplican a una salida. */
const MOTIVOS_ENTRADA = [
  ["sobrante", "Sobrante"],
  ["error_registro", "Corrección de error de registro"],
] as const;

const CONDICIONES = [
  ["ambiente", "Ambiente"],
  ["refrigerado", "Refrigerado"],
  ["congelado", "Congelado"],
] as const;

const CLASE_ESTADO: Record<string, string> = {
  pendiente: "bg-amber-100 text-amber-900",
  aprobado: "bg-accent/30 text-dark",
  rechazado: "bg-gray/20 text-gray",
};

/**
 * Ajustes de inventario: la pantalla que faltaba.
 *
 * `inventory.ajuste_fuera_margen` reportaba un hecho urgente y no había
 * dónde ir a resolverlo — los ajustes solo se podían crear y aprobar por API
 * (ADR-036). Acá se aprueba o se rechaza, que es la única acción que el
 * reporte pide.
 */
export function AjustesCliente({
  ajustes,
  resaltado,
  estado,
  permisos,
  almacenes,
  skus,
}: {
  ajustes: Ajuste[];
  resaltado: string | null;
  estado: string;
  permisos: string[];
  almacenes: OpcionAlmacen[];
  skus: OpcionSku[];
}) {
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState("");
  const puedeAprobar = tienePermiso(permisos, "inventory.aprobar_ajuste");
  const puedeSolicitar = tienePermiso(permisos, "inventory.solicitar_ajuste");

  async function decidir(id: string, accion: "aprobar" | "rechazar") {
    setEnviando(id);
    setError("");
    try {
      // Las dos rutas escritas enteras y no `${accion}`: el check de contrato
      // (`lib/contrato.test.ts`) coteja cada ruta literal contra el OpenAPI, y
      // un segmento armado en runtime se le escapa.
      await pedir(
        accion === "aprobar"
          ? `/inventory/ajustes/${id}/aprobar`
          : `/inventory/ajustes/${id}/rechazar`,
        { metodo: "POST" },
      );
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo registrar la decisión.");
    } finally {
      setEnviando("");
    }
  }

  function cambiarEstado(nuevo: string) {
    const query = new URLSearchParams(params.toString());
    if (nuevo) query.set("estado", nuevo);
    else query.set("estado", "");
    query.delete("ajuste");
    router.push(`/inventario/ajustes?${query}`);
  }

  const columnas = useMemo<ColumnDef<Ajuste>[]>(
    () => [
      { header: "Motivo", accessorKey: "motivo" },
      { header: "Cantidad", accessorKey: "cantidad" },
      {
        header: "Margen",
        accessorKey: "dentro_margen",
        cell: ({ row }) =>
          row.original.dentro_margen ? (
            <span className="text-sm text-gray">Dentro</span>
          ) : (
            <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-bold text-red-900">
              Fuera de margen
            </span>
          ),
      },
      {
        header: "Estado",
        accessorKey: "estado",
        cell: ({ row }) => (
          <span
            className={`rounded px-2 py-0.5 text-xs font-bold ${
              CLASE_ESTADO[row.original.estado] ?? ""
            }`}
          >
            {row.original.estado}
          </span>
        ),
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) =>
          row.original.estado !== "pendiente" || !puedeAprobar ? null : (
            <div className="flex gap-2">
              <button
                type="button"
                disabled={enviando === row.original.id}
                onClick={() => decidir(row.original.id, "aprobar")}
                className="rounded bg-primary px-3 py-1 text-xs font-bold text-white disabled:opacity-50"
              >
                Aprobar
              </button>
              <button
                type="button"
                disabled={enviando === row.original.id}
                onClick={() => decidir(row.original.id, "rechazar")}
                className="rounded border border-gray px-3 py-1 text-xs font-semibold text-dark disabled:opacity-50"
              >
                Rechazar
              </button>
            </div>
          ),
      },
    ],
    // `decidir` se recrea en cada render y no aporta a la identidad de las
    // columnas: lo que las cambia es quién puede aprobar y qué fila está
    // enviando.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [puedeAprobar, enviando],
  );

  const ordenados = useMemo(
    () => primeroElDe(ajustes, resaltado, (a) => a.id),
    [ajustes, resaltado],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="font-heading text-xl italic uppercase text-dark">
          Ajustes de inventario
        </h1>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm font-semibold">
            Estado
            <select value={estado} onChange={(e) => cambiarEstado(e.target.value)}>
              <option value="pendiente">Pendientes</option>
              <option value="aprobado">Aprobados</option>
              <option value="rechazado">Rechazados</option>
              <option value="">Todos</option>
            </select>
          </label>
          {puedeSolicitar && <FormularioEntradaStock almacenes={almacenes} skus={skus} />}
        </div>
      </div>
      {resaltado && !ajustes.some((a) => a.id === resaltado) && (
        <p className="text-sm text-secondary">
          El ajuste que buscabas no está en este filtro. Probá con «Todos».
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm font-semibold text-secondary">
          {error}
        </p>
      )}
      <TablaDatos
        columnas={columnas}
        datos={ordenados}
        placeholderBusqueda="Buscar por motivo..."
      />
    </div>
  );
}

function FormularioEntradaStock({
  almacenes,
  skus,
}: {
  almacenes: OpcionAlmacen[];
  skus: OpcionSku[];
}) {
  const [skuId, setSkuId] = useState<string | null>(null);
  const controlaLote = useMemo(
    () => skus.find((s) => s.id === skuId)?.controlaLote ?? false,
    [skus, skuId],
  );

  return (
    <DialogoFormulario
      titulo="Registrar entrada de stock"
      disparador="+ Registrar entrada de stock"
      accion={registrarEntradaStockAction}
      etiquetaEnvio="Registrar"
      ayuda="Queda pendiente hasta que otro usuario la apruebe: quien la pide no puede aprobarla (RN-INV-006)."
      envioDeshabilitado={almacenes.length === 0 || skus.length === 0}
      alCerrar={() => setSkuId(null)}
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Almacén
        <Combobox
          name="almacen_id"
          etiqueta="Almacén"
          requerido
          marcador="Elegir…"
          opciones={almacenes.map((a) => ({ valor: a.id, etiqueta: a.nombre }))}
        />
      </label>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Qué entra
        <Combobox
          name="sku_id"
          etiqueta="Qué entra"
          requerido
          marcador="Elegir…"
          opciones={skus.map((s) => ({ valor: s.id, etiqueta: s.etiqueta }))}
          alCambiar={setSkuId}
        />
      </label>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Cantidad
        <input name="cantidad" inputMode="decimal" defaultValue="1" />
      </label>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Motivo
        <select name="motivo" defaultValue="sobrante">
          {MOTIVOS_ENTRADA.map(([valor, etiqueta]) => (
            <option key={valor} value={valor}>
              {etiqueta}
            </option>
          ))}
        </select>
      </label>

      {/* Solo el artículo con control de lote pide vencimiento: los demás no
          se mueven por `stock_lote`, y pedirlo igual sería un campo que nadie
          sabe para qué sirve. */}
      {controlaLote && (
        <>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Código de lote
            <input name="lote_codigo" maxLength={50} placeholder="Opcional: se genera del vencimiento" />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Fecha de vencimiento
            <input name="fecha_vencimiento" type="date" />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Fecha de elaboración
            <input name="fecha_elaboracion" type="date" />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Condición de almacenamiento
            <select name="condicion_almacenamiento" defaultValue="">
              <option value="">Sin especificar</option>
              {CONDICIONES.map(([valor, etiqueta]) => (
                <option key={valor} value={valor}>
                  {etiqueta}
                </option>
              ))}
            </select>
          </label>
        </>
      )}
    </DialogoFormulario>
  );
}
