"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useActionState, useEffect, useMemo, useRef, useState } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";
import { ArticuloPicker } from "@/components/articulo-picker/articulo-picker";

import {
  completarOrdenAction,
  crearOrdenAction,
  registrarConsumoAction,
  type EstadoOrden,
} from "./actions";
import { Combobox } from "@/components/ui/combobox";

export type Orden = {
  id: string;
  articulo_id: string;
  almacen_id: string;
  cantidad_planeada: string;
  cantidad_producida: string | null;
  estado: string;
  costo_insumos: string | null;
  costo_real_unitario: string | null;
  merma_cantidad: string | null;
  merma_motivo: string | null;
};
export type Articulo = { id: string; nombre: string; id_interno: string; tipo: string };
/** Lo que una orden puede producir. Va al servidor como filtro (`?tipo=`) y
 * no se resuelve en la pantalla: filtrar acá recorta solo lo que vino en la
 * página, que de un catálogo de miles es casi nada. */
const PRODUCIBLES: string[] = ["subreceta", "mercaderia"];

function comoOpciones(articulos: Articulo[]) {
  return articulos.map((a) => ({
    valor: a.id,
    etiqueta: a.nombre,
    pista: a.id_interno,
  }));
}

export type Almacen = { id: string; nombre: string };

const ESTADO_INICIAL: EstadoOrden = { error: "", ok: false };

const ETIQUETA_ESTADO: Record<string, string> = {
  borrador: "Borrador",
  en_proceso: "En proceso",
  conforme: "Conforme",
  no_conforme_reprocesado: "No conforme · reprocesado",
  no_conforme_desechado: "No conforme · desechado",
};

function useCerrarAlGuardar(ok: boolean) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  useEffect(() => {
    if (ok) {
      formRef.current?.reset();
      dialogRef.current?.close();
    }
  }, [ok]);
  return { dialogRef, formRef };
}

function DialogoNuevaOrden({
  articulos,
  almacenes,
}: {
  articulos: Articulo[];
  almacenes: Almacen[];
}) {
  const [estado, formAction, pendiente] = useActionState(crearOrdenAction, ESTADO_INICIAL);
  const { dialogRef, formRef } = useCerrarAlGuardar(estado.ok);
  // Solo se produce lo que tiene receta: subrecetas y mercadería propia. Un
  // insumo comprado no se fabrica, se compra.
  const producibles = comoOpciones(
    articulos.filter((a) => PRODUCIBLES.includes(a.tipo)),
  );

  return (
    <>
      <button
        type="button"
        onClick={() => dialogRef.current?.showModal()}
        className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
      >
        + Nueva orden
      </button>
      <dialog ref={dialogRef} className="w-full max-w-md rounded-lg p-0 backdrop:bg-dark/40">
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg text-dark">Nueva orden</h2>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Qué se produce
            <ArticuloPicker
              name="articulo_id"
              etiqueta="Qué se produce"
              requerido
              marcador="Elegir artículo..."
              tipos={PRODUCIBLES}
              iniciales={producibles}
            />
            <span className="text-xs font-normal text-gray">
              Sin receta la orden se rechaza: no habría qué consumir.
            </span>
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Almacén
            <Combobox
              name="almacen_id"
              etiqueta="Almacén"
              requerido
              marcador="Elegir almacén..."
              opciones={almacenes.map((a) => ({ valor: a.id, etiqueta: a.nombre }))}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Cantidad planeada
            <input name="cantidad_planeada" type="number" step="0.0001" min="0.0001" required />
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
              {pendiente ? "Creando..." : "Crear"}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

type LineaConsumo = { clave: number; articulo: string; cantidad: string; costo: string };

function DialogoConsumo({ orden, articulos }: { orden: Orden; articulos: Articulo[] }) {
  const [estado, formAction, pendiente] = useActionState(registrarConsumoAction, ESTADO_INICIAL);
  const { dialogRef, formRef } = useCerrarAlGuardar(estado.ok);
  const [lineas, setLineas] = useState<LineaConsumo[]>([
    { clave: 1, articulo: "", cantidad: "", costo: "" },
  ]);

  const editar = (clave: number, campo: keyof LineaConsumo, valor: string) =>
    setLineas((prev) => prev.map((l) => (l.clave === clave ? { ...l, [campo]: valor } : l)));

  return (
    <>
      <button
        type="button"
        onClick={() => dialogRef.current?.showModal()}
        className="text-xs font-bold text-primary hover:underline"
      >
        Consumo
      </button>
      <dialog ref={dialogRef} className="w-full max-w-xl rounded-lg p-0 backdrop:bg-dark/40">
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          <input type="hidden" name="orden_id" value={orden.id} />
          <h2 className="font-heading text-lg text-dark">
            Consumo de insumos
          </h2>
          <p className="text-sm text-gray">
            Lo que la cocina sacó de verdad del almacén. Descuenta stock y arma el costo
            real de la orden — por eso se registra antes de completarla.
          </p>
          {lineas.map((linea) => (
            <div key={linea.clave} className="flex items-end gap-2">
              <label className="flex flex-1 flex-col gap-1 text-xs font-semibold">
                Insumo
                <ArticuloPicker
                  name="consumo_articulo_id"
                  etiqueta="Insumo"
                  requerido
                  marcador="Elegir insumo..."
                  iniciales={comoOpciones(articulos)}
                  value={linea.articulo}
                  alCambiar={(v) => editar(linea.clave, "articulo", v ?? "")}
                />
              </label>
              <label className="flex w-28 flex-col gap-1 text-xs font-semibold">
                Cantidad
                <input
                  name="consumo_cantidad"
                  type="number"
                  step="0.0001"
                  min="0.0001"
                  required
                  value={linea.cantidad}
                  onChange={(e) => editar(linea.clave, "cantidad", e.target.value)}
                  className="rounded border border-gray/40 px-2 py-1 text-sm"
                />
              </label>
              <label className="flex w-28 flex-col gap-1 text-xs font-semibold">
                Costo unit.
                <input
                  name="consumo_costo"
                  type="number"
                  step="0.0001"
                  min="0"
                  required
                  value={linea.costo}
                  onChange={(e) => editar(linea.clave, "costo", e.target.value)}
                  className="rounded border border-gray/40 px-2 py-1 text-sm"
                />
              </label>
              <button
                type="button"
                aria-label="Quitar insumo"
                disabled={lineas.length <= 1}
                onClick={() => setLineas((prev) => prev.filter((l) => l.clave !== linea.clave))}
                className="pb-1.5 text-gray hover:text-secondary disabled:opacity-30"
              >
                ×
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={() =>
              setLineas((prev) => [
                ...prev,
                { clave: Math.max(...prev.map((l) => l.clave)) + 1, articulo: "", cantidad: "", costo: "" },
              ])
            }
            className="self-start text-sm font-semibold text-primary hover:underline"
          >
            + Agregar insumo
          </button>
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
              {pendiente ? "Registrando..." : "Registrar"}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

function DialogoCompletar({ orden }: { orden: Orden }) {
  const [estado, formAction, pendiente] = useActionState(completarOrdenAction, ESTADO_INICIAL);
  const { dialogRef, formRef } = useCerrarAlGuardar(estado.ok);
  const [resultado, setResultado] = useState("conforme");

  return (
    <>
      <button
        type="button"
        onClick={() => dialogRef.current?.showModal()}
        className="text-xs font-bold text-primary hover:underline"
      >
        Completar
      </button>
      <dialog ref={dialogRef} className="w-full max-w-md rounded-lg p-0 backdrop:bg-dark/40">
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          <input type="hidden" name="orden_id" value={orden.id} />
          <h2 className="font-heading text-lg text-dark">
            Control de calidad
          </h2>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Resultado
            <select
              name="resultado"
              value={resultado}
              onChange={(e) => setResultado(e.target.value)}
            >
              <option value="conforme">Conforme</option>
              <option value="no_conforme_reprocesado">No conforme · reprocesado</option>
              <option value="no_conforme_desechado">No conforme · desechado</option>
            </select>
          </label>
          {resultado === "conforme" && (
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Cantidad producida
              <input
                name="cantidad_producida"
                type="number"
                step="0.0001"
                min="0.0001"
                required
                defaultValue={orden.cantidad_planeada}
              />
              <span className="text-xs font-normal text-gray">
                Lo que salió de verdad, no lo planeado: de acá sale el costo unitario.
              </span>
            </label>
          )}
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Horas hombre
            <input name="horas_hombre" type="number" step="0.01" min="0" placeholder="Opcional" />
          </label>
          <div className="flex gap-2">
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              Merma
              <input name="merma_cantidad" type="number" step="0.0001" min="0.0001" placeholder="Opcional" />
            </label>
            <label className="flex flex-[2] flex-col gap-1 text-sm font-semibold">
              Motivo de la merma
              <input name="merma_motivo" maxLength={255} placeholder="Obligatorio si hay merma" />
            </label>
          </div>
          {resultado === "no_conforme_desechado" && (
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Evidencia de destrucción
              <input name="evidencia_destruccion_url" maxLength={500} placeholder="URL de la foto o acta" />
            </label>
          )}
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
              {pendiente ? "Cerrando..." : "Completar"}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

export function OrdenesCliente({
  ordenes,
  articulos,
  almacenes,
}: {
  ordenes: Orden[];
  articulos: Articulo[];
  almacenes: Almacen[];
}) {
  const nombreArticulo = useMemo(
    () => new Map(articulos.map((a) => [a.id, `${a.id_interno} · ${a.nombre}`])),
    [articulos],
  );
  const nombreAlmacen = useMemo(
    () => new Map(almacenes.map((a) => [a.id, a.nombre])),
    [almacenes],
  );

  const columnas: ColumnDef<Orden>[] = useMemo(
    () => [
      {
        id: "articulo",
        header: "Produce",
        accessorFn: (o) => nombreArticulo.get(o.articulo_id) ?? o.articulo_id,
      },
      {
        id: "almacen",
        header: "Almacén",
        accessorFn: (o) => nombreAlmacen.get(o.almacen_id) ?? "—",
      },
      {
        id: "cantidad",
        header: "Planeado / producido",
        accessorFn: (o) => `${o.cantidad_planeada} / ${o.cantidad_producida ?? "—"}`,
      },
      {
        id: "costo",
        header: "Costo unitario",
        accessorFn: (o) => o.costo_real_unitario ?? "—",
      },
      {
        accessorKey: "estado",
        header: "Estado",
        cell: ({ getValue }) => {
          const estado = getValue<string>();
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
        },
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => {
          const orden = row.original;
          // El ciclo es lineal: se consume en borrador, se completa en
          // proceso. Mostrar el botón que no aplica solo invita al 409.
          if (orden.estado === "borrador") {
            return <DialogoConsumo orden={orden} articulos={articulos} />;
          }
          if (orden.estado === "en_proceso") return <DialogoCompletar orden={orden} />;
          return <span className="text-xs text-gray">—</span>;
        },
      },
    ],
    [articulos, nombreArticulo, nombreAlmacen],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl text-dark">
          Órdenes de producción
        </h1>
        <DialogoNuevaOrden articulos={articulos} almacenes={almacenes} />
      </div>
      <p className="text-sm text-gray">
        Fabricar una subreceta o un producto propio: se crea la orden, se registra lo que
        la cocina consumió de verdad y se cierra con el control de calidad. Recién ahí
        entra el resultado al stock, con su costo real.
      </p>
      <TablaDatos columnas={columnas} datos={ordenes} placeholderBusqueda="Buscar orden..." />
    </div>
  );
}
