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
  /** Qué dice el `title` de "quitar" — lo que se retira no es lo mismo en un
   * extra (se desvincula) que en un grupo (se borra). */
  quitarAria?: string;
};

// Los puertos se cablean. Van habilitados en todos los nodos a propósito:
// `conexiones.ts` rechaza el par que el dominio no admite **explicando qué sí
// se puede**, y eso solo puede pasar si el arrastre llega a empezar. Con
// `isConnectable={false}` react-flow ni siquiera dejaba tomar el puerto, así
// que el lienzo se sentía un dibujo.
const PUERTOS = (
  <>
    <Handle type="target" position={Position.Left} />
    <Handle type="source" position={Position.Right} />
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
        // Deshabilitado solo si NO hay nada que hacer con él: un `<button
        // disabled>` se traga los clicks de todo lo que tiene adentro, y con
        // eso "quitar" y "receta" quedaban muertos en cualquier nodo que no
        // se pudiera tocar —el grupo, sin ir más lejos—.
        disabled={!datos.onToggle && !datos.onQuitar && !datos.recetaId}
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

/** Enlaces del pie del nodo. `<span role="button">` y no `<button>`: esto va
 * dentro del botón del nodo, y anidar botones es HTML inválido. */
function Acciones({ datos }: { datos: DatosNodo }) {
  if (!datos.recetaId && !datos.onQuitar) return null;
  return (
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
          title={datos.quitarAria ?? "Deja de ofrecerlo en este producto. El extra no se borra"}
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
  );
}

export function NodoTarjeta({ data }: NodeProps) {
  const datos = data as DatosNodo;
  return (
    <Tarjeta datos={datos} clase="">
      <Acciones datos={datos} />
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

/** Cabecera de una columna de opciones. Existe como nodo para ser el destino
 * de una conexión: colgar un extra ahí es colgarlo DENTRO de ese grupo. Y para
 * poder borrarlo desde donde se lo ve, que es lo que faltaba: sus opciones
 * siguen ofreciéndose, ya sin mínimo. */
export function NodoGrupo({ data }: NodeProps) {
  const datos = data as DatosNodo;
  return (
    <Tarjeta datos={datos} clase="grupo">
      <Acciones datos={datos} />
    </Tarjeta>
  );
}

/** Un extra que existe y este producto todavía no ofrece. Se cablea a un
 * grupo (o al tamaño) para vincularlo. */
export function NodoDisponible({ data }: NodeProps) {
  return <Tarjeta datos={data as DatosNodo} clase="disponible" />;
}

export function NodoPlato({ data }: NodeProps) {
  const datos = data as DatosNodo;
  return (
    <>
      <Handle type="target" position={Position.Left} />
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
  grupo: NodoGrupo,
  opcion: NodoTarjeta,
  disponible: NodoDisponible,
  empaque: NodoTarjeta,
  resta: NodoResta,
  plato: NodoPlato,
};
