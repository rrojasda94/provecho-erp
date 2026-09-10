"use client";

import Link from "next/link";
import { useMemo } from "react";

import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";

import { crearOrdenHijaAction } from "./actions";

import type { Articulo } from "../../ordenes-cliente";

export type ConsumoRealOut = {
  id: string;
  articulo_id: string;
  cantidad: string;
  costo_unitario: string;
  peso_desperdicio_real: string;
  desviacion_desperdicio: string | null;
};

export type OrdenHijaResumen = {
  id: string;
  articulo_id: string;
  estado: string;
  cantidad_planeada: string;
  cantidad_producida: string | null;
};

export type OrdenDetalle = {
  id: string;
  articulo_id: string;
  almacen_id: string;
  plan_produccion_id: string | null;
  orden_padre_id: string | null;
  origen: string;
  cantidad_planeada: string;
  cantidad_producida: string | null;
  estado: string;
  costo_insumos: string | null;
  costo_mano_obra: string | null;
  costo_real_unitario: string | null;
  consumos: ConsumoRealOut[];
  trabajadores: { trabajador_id: string; horas: string }[];
  hijas: OrdenHijaResumen[];
};

export type ConsumoSugeridoLinea = {
  articulo_id: string;
  articulo_nombre: string;
  cantidad_sugerida: string;
  costo_linea: string;
  requiere_orden_hija: boolean;
};

export type ConsumoSugerido = {
  items: ConsumoSugeridoLinea[];
  costo_total: string;
};

const ETIQUETA_ESTADO: Record<string, string> = {
  borrador: "Borrador",
  en_proceso: "En proceso",
  conforme: "Conforme",
  no_conforme_reprocesado: "No conforme · reprocesado",
  no_conforme_desechado: "No conforme · desechado",
};

function BadgeEstado({ estado }: { estado: string }) {
  const clase = estado.startsWith("no_conforme")
    ? "bg-secondary/15 text-secondary"
    : estado === "conforme"
      ? "bg-accent/30 text-dark"
      : "bg-gray/20 text-gray";
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${clase}`}>
      {ETIQUETA_ESTADO[estado] ?? estado}
    </span>
  );
}

function DialogoOrdenHija({
  ordenId,
  linea,
}: {
  ordenId: string;
  linea: ConsumoSugeridoLinea;
}) {
  return (
    <DialogoFormulario
      titulo={`Fabricar ${linea.articulo_nombre}`}
      disparador="+ Orden hija"
      claseDisparador="text-xs font-bold text-primary hover:underline"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearOrdenHijaAction}
      ayuda="No hay disponible suficiente para consumirlo directo — se fabrica primero con su propia orden, en el mismo almacén (RN-PRD-020)."
    >
      <input type="hidden" name="orden_id" value={ordenId} />
      <input type="hidden" name="articulo_id" value={linea.articulo_id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Cantidad planeada
        <input
          name="cantidad_planeada"
          type="number"
          step="0.0001"
          min="0.0001"
          defaultValue={linea.cantidad_sugerida}
          required
        />
      </label>
    </DialogoFormulario>
  );
}

export function FichaOrdenCliente({
  orden,
  consumoSugerido,
  articulos,
}: {
  orden: OrdenDetalle;
  consumoSugerido: ConsumoSugerido | null;
  articulos: Articulo[];
}) {
  const nombreArticulo = useMemo(
    () => new Map(articulos.map((a) => [a.id, a.nombre])),
    [articulos],
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link href="/produccion" className="text-xs text-primary hover:underline">
          ← Volver a órdenes
        </Link>
        <div className="flex items-center gap-3">
          <h1 className="font-heading text-xl text-dark">
            {nombreArticulo.get(orden.articulo_id) ?? orden.articulo_id}
          </h1>
          <BadgeEstado estado={orden.estado} />
        </div>
        {orden.orden_padre_id && (
          <p className="text-xs text-gray">
            Orden hija de{" "}
            <Link
              href={`/produccion/ordenes/${orden.orden_padre_id}`}
              className="text-primary hover:underline"
            >
              otra orden
            </Link>
            {" "}(origen: {orden.origen}).
          </p>
        )}
        <p className="text-sm text-gray">
          Planeado {orden.cantidad_planeada}
          {orden.cantidad_producida ? ` · producido ${orden.cantidad_producida}` : ""}
          {orden.costo_real_unitario ? ` · costo unitario ${orden.costo_real_unitario}` : ""}
        </p>
      </div>

      {orden.hijas.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="font-heading text-sm text-dark">Órdenes hijas</h2>
          <p className="text-xs text-gray">
            Esta orden no admite registrar consumo mientras alguna siga sin llegar a
            &quot;conforme&quot; (RN-PRD-020).
          </p>
          <ul className="flex flex-col gap-1">
            {orden.hijas.map((h) => (
              <li key={h.id} className="flex items-center gap-2 text-sm">
                <Link
                  href={`/produccion/ordenes/${h.id}`}
                  className="text-primary hover:underline"
                >
                  {nombreArticulo.get(h.articulo_id) ?? h.articulo_id}
                </Link>
                <BadgeEstado estado={h.estado} />
                <span className="text-xs text-gray">
                  {h.cantidad_planeada}
                  {h.cantidad_producida ? ` / ${h.cantidad_producida}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {orden.estado === "borrador" && consumoSugerido && (
        <section className="flex flex-col gap-2">
          <h2 className="font-heading text-sm text-dark">Consumo sugerido</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray">
                  <th className="pb-2">Insumo</th>
                  <th className="pb-2">Cantidad sugerida</th>
                  <th className="pb-2">Costo</th>
                  <th className="pb-2"></th>
                </tr>
              </thead>
              <tbody>
                {consumoSugerido.items.map((linea) => (
                  <tr key={linea.articulo_id} className="border-t border-gray/10">
                    <td className="py-2">{linea.articulo_nombre}</td>
                    <td className="py-2">{linea.cantidad_sugerida}</td>
                    <td className="py-2">{linea.costo_linea}</td>
                    <td className="py-2 text-right">
                      {linea.requiere_orden_hija ? (
                        <DialogoOrdenHija ordenId={orden.id} linea={linea} />
                      ) : (
                        <span className="text-xs text-gray">Hay disponible</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {orden.consumos.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="font-heading text-sm text-dark">Consumo real</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray">
                  <th className="pb-2">Insumo</th>
                  <th className="pb-2">Cantidad</th>
                  <th className="pb-2">Costo unit.</th>
                  <th className="pb-2">Desperdicio</th>
                </tr>
              </thead>
              <tbody>
                {orden.consumos.map((c) => (
                  <tr key={c.id} className="border-t border-gray/10">
                    <td className="py-2">{nombreArticulo.get(c.articulo_id) ?? c.articulo_id}</td>
                    <td className="py-2">{c.cantidad}</td>
                    <td className="py-2">{c.costo_unitario}</td>
                    <td className="py-2">{c.peso_desperdicio_real}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
