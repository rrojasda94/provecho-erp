"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Insignia } from "@/components/estado/insignia";
import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { Combobox } from "@/components/ui/combobox";
import { tienePermiso } from "@/lib/permisos";

import { registrarMermaAction, resolverMermaAction } from "./actions";

export type Merma = {
  id: string;
  almacen_id: string;
  sku_id: string;
  lote_id: string | null;
  cantidad: string;
  motivo: string | null;
  estado: string;
};
export type OpcionAlmacen = { id: string; nombre: string };
export type OpcionSku = { id: string; etiqueta: string };

/** Qué originó la merma (RN-INV-012). El backend acepta exactamente estos
 * tres: no es un texto libre porque de acá sale el análisis de por qué se
 * pierde mercadería. */
const MOTIVOS: [string, string][] = [
  ["devolucion", "Volvió en una devolución"],
  ["rechazo_sucursal", "La sucursal lo rechazó"],
  ["auditoria", "Lo encontró una auditoría o un conteo"],
];

const ETIQUETA_MOTIVO = Object.fromEntries(MOTIVOS);

/**
 * Mermas: lo que está en el almacén pero ya no se puede vender.
 *
 * Tres endpoints con ADR propio (ADR-028), pruebas y permisos sembrados, y
 * cero pantalla que los llamara: apartar mercadería inservible solo se podía
 * hacer llamando la API a mano. Es la mitad del bloque
 * `feat/inventario-transferencias-mermas` de la auditoría del 2026-08-30.
 *
 * Dos pasos y no uno, porque la segregación es la regla: quien declara que
 * algo no sirve (`inventory.solicitar_ajuste`) no firma su baja
 * (`inventory.aprobar_ajuste`). Mismo criterio que los ajustes de
 * inventario, y por eso esta pantalla se parece a la de al lado.
 */
export function MermasCliente({
  mermas,
  almacenes,
  skus,
  permisos,
}: {
  mermas: Merma[];
  almacenes: OpcionAlmacen[];
  skus: OpcionSku[];
  permisos: string[];
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState("");
  const puedeRegistrar = tienePermiso(permisos, "inventory.solicitar_ajuste");
  const puedeResolver = tienePermiso(permisos, "inventory.aprobar_ajuste");

  const nombreAlmacen = useMemo(
    () => new Map(almacenes.map((a) => [a.id, a.nombre])),
    [almacenes],
  );
  const nombreSku = useMemo(() => new Map(skus.map((s) => [s.id, s.etiqueta])), [skus]);

  async function resolver(id: string, destino: "desecho" | "reintegro") {
    setEnviando(id);
    setError("");
    const r = await resolverMermaAction(id, destino);
    if (!r.ok) setError(r.error);
    else router.refresh();
    setEnviando("");
  }

  const columnas = useMemo<ColumnDef<Merma>[]>(
    () => [
      {
        header: "Almacén",
        accessorFn: (m) => nombreAlmacen.get(m.almacen_id) ?? "—",
      },
      {
        header: "Qué",
        accessorFn: (m) => nombreSku.get(m.sku_id) ?? m.sku_id,
      },
      { header: "Cantidad", accessorKey: "cantidad", meta: { numero: true } },
      {
        header: "Por qué",
        accessorFn: (m) => (m.motivo ? (ETIQUETA_MOTIVO[m.motivo] ?? m.motivo) : "—"),
      },
      {
        header: "Estado",
        accessorKey: "estado",
        cell: ({ row }) => (
          <Insignia tono={row.original.estado === "activa" ? "alerta" : "neutro"}>
            {row.original.estado === "activa" ? "apartada" : row.original.estado}
          </Insignia>
        ),
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) =>
          row.original.estado !== "activa" || !puedeResolver ? null : (
            <div className="flex items-center gap-3">
              {/* Desechar primero: es el destino de la enorme mayoría, y
                  ofrecer el reintegro con el mismo peso invita a devolver al
                  estante algo que ya se declaró inservible. */}
              <button
                type="button"
                disabled={enviando === row.original.id}
                onClick={() => resolver(row.original.id, "desecho")}
                title="Sale del stock y se asienta como pérdida"
                className="text-xs font-semibold text-status-danger hover:underline disabled:opacity-50"
              >
                Desechar
              </button>
              <button
                type="button"
                disabled={enviando === row.original.id}
                onClick={() => resolver(row.original.id, "reintegro")}
                title="Vuelve a disponible: era recuperable"
                className="text-xs font-semibold text-primary hover:underline disabled:opacity-50"
              >
                Reintegrar
              </button>
            </div>
          ),
      },
    ],
    // `resolver` se recrea en cada render; lo que cambia las columnas es
    // quién puede resolver, qué fila está enviando y los catálogos.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [puedeResolver, enviando, nombreAlmacen, nombreSku],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-heading text-xl italic uppercase text-dark">Mermas</h1>
          <p className="text-xs text-gray">
            Lo que está en el almacén y ya no se puede vender. Apartarlo no lo saca
            del almacén: lo saca de la venta. Qué se hace con ello —tirarlo o
            devolverlo al estante— lo firma otra persona.
          </p>
        </div>
        {puedeRegistrar && <FormularioMerma almacenes={almacenes} skus={skus} />}
      </div>

      {error && (
        <p role="alert" className="text-sm font-semibold text-secondary">
          {error}
        </p>
      )}

      <TablaDatos
        columnas={columnas}
        datos={mermas}
        placeholderBusqueda="Buscar por almacén o motivo..."
        vacio="No hay mermas apartadas."
      />
    </div>
  );
}

function FormularioMerma({
  almacenes,
  skus,
}: {
  almacenes: OpcionAlmacen[];
  skus: OpcionSku[];
}) {
  return (
    <DialogoFormulario
      titulo="Apartar por merma"
      disparador="+ Registrar merma"
      accion={registrarMermaAction}
      etiquetaEnvio="Apartar"
      ayuda="Aparta la cantidad para que deje de figurar como disponible. El stock sigue en el almacén hasta que alguien resuelva si se desecha o se reintegra."
      envioDeshabilitado={almacenes.length === 0 || skus.length === 0}
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
        Qué se aparta
        <Combobox
          name="sku_id"
          etiqueta="Qué se aparta"
          requerido
          marcador="Elegir…"
          opciones={skus.map((s) => ({ valor: s.id, etiqueta: s.etiqueta }))}
        />
      </label>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Cantidad
        <input name="cantidad" inputMode="decimal" defaultValue="1" />
      </label>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Por qué
        <select name="motivo" defaultValue="auditoria">
          {MOTIVOS.map(([valor, etiqueta]) => (
            <option key={valor} value={valor}>
              {etiqueta}
            </option>
          ))}
        </select>
      </label>
    </DialogoFormulario>
  );
}
