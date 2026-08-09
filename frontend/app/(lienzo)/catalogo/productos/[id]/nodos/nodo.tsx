"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import Link from "next/link";

import type { TipoNodo } from "@/lib/lienzo";

/**
 * Los tres tipos de nodo del lienzo.
 *
 * El nodo **es** un `<button aria-pressed>` de verdad, no un `div` con
 * `onClick`: la pantalla ya era operable por teclado antes del rediseño y eso
 * no se puede regresar. El orden de tabulación sigue el de las columnas, que
 * es el de RN-PRD-004.
 *
 * Los botones internos (ver receta, quitar) llevan la clase `nodrag` de
 * react-flow: sin ella, apretarlos arrastra el nodo en vez de accionar.
 */

export type DatosNodo = {
  titulo: string;
  aria?: string;
  pie?: string;
  activo: boolean;
  columna: string;
  recetaId?: string | null;
  /** Total del plato armado, **ya formateado** — solo lo usa el nodo
   * `plato`. Llega hecho para que el nodo no vuelva a formatear un texto
   * que ya lo estaba. */
  total?: string;
  onToggle?: () => void;
  onQuitar?: () => void;
};

const PUERTOS = (
  <>
    <Handle type="target" position={Position.Left} isConnectable={false} />
    <Handle type="source" position={Position.Right} isConnectable={false} />
  </>
);

function Tarjeta({
  datos,
  clase,
  children,
}: {
  datos: DatosNodo;
  clase: string;
  children?: React.ReactNode;
}) {
  return (
    <>
      {PUERTOS}
      <button
        type="button"
        className={`nodo ${clase}${datos.activo ? " activo" : ""}`}
        aria-pressed={datos.onToggle ? datos.activo : undefined}
        disabled={!datos.onToggle}
        onClick={datos.onToggle}
        aria-label={datos.aria}
        title={datos.aria ?? datos.titulo}
      >
        <span className="nodo-columna">{datos.columna}</span>
        <span className="nodo-titulo">{datos.titulo}</span>
        {datos.pie && <span className="nodo-pie">{datos.pie}</span>}
        {children}
      </button>
    </>
  );
}

export function NodoTarjeta({ data }: NodeProps) {
  const datos = data as DatosNodo;
  return (
    <Tarjeta datos={datos} clase="">
      {(datos.recetaId || datos.onQuitar) && (
        <span className="nodo-acciones">
          {datos.recetaId && (
            <Link
              href={`/catalogo/recetas/${datos.recetaId}`}
              className="nodo-accion nodrag"
              onClick={(e) => e.stopPropagation()}
            >
              receta
            </Link>
          )}
          {datos.onQuitar && (
            <span
              role="button"
              tabIndex={0}
              className="nodo-accion riesgo nodrag"
              title="Deja de ofrecerlo en este producto. El extra no se borra"
              onClick={(e) => {
                e.stopPropagation();
                datos.onQuitar?.();
              }}
              onKeyDown={(e) => {
                if (e.key !== "Enter" && e.key !== " ") return;
                e.stopPropagation();
                e.preventDefault();
                datos.onQuitar?.();
              }}
            >
              quitar
            </span>
          )}
        </span>
      )}
    </Tarjeta>
  );
}

export function NodoResta({ data }: NodeProps) {
  const datos = data as DatosNodo;
  // El "−" delante y no la palabra "sin": el chip es angosto y el glifo dice
  // lo mismo sin gastar ancho. El nombre accesible sí lleva "sin".
  return (
    <Tarjeta datos={{ ...datos, titulo: `− ${datos.titulo}` }} clase="resta" />
  );
}

export function NodoPlato({ data }: NodeProps) {
  const datos = data as DatosNodo;
  return (
    <>
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <div className="nodo plato">
        <span className="nodo-columna">Plato</span>
        <span className="nodo-total">{datos.total ?? "—"}</span>
      </div>
    </>
  );
}

/** Tipos de nodo como constante de módulo: react-flow exige referencia
 * estable, y de paso la complejidad del componente no crece con los casos. */
export const TIPOS_NODO: Record<TipoNodo, typeof NodoTarjeta> = {
  producto: NodoTarjeta,
  tamano: NodoTarjeta,
  opcion: NodoTarjeta,
  empaque: NodoTarjeta,
  resta: NodoResta,
  plato: NodoPlato,
};
