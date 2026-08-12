import type { LucideIcon } from "lucide-react";
import { Inbox } from "lucide-react";

/**
 * Estado vacío. Reemplaza al `Sin resultados.` suelto que la tabla escribía
 * en una celda.
 *
 * Un vacío no es un error —esa distinción es regla dura del proyecto
 * (`lib/carga.ts`: un fetch que falló nunca se dibuja como lista vacía)— pero
 * tampoco es el final del camino: casi siempre hay algo que la persona puede
 * hacer, y decírselo es más barato que dejarla mirando una tabla en blanco
 * preguntándose si el sistema se rompió.
 *
 * `accion` es opcional a propósito: hay vacíos que de verdad no admiten
 * acción (una búsqueda sin coincidencias), y ofrecer un botón inventado ahí
 * es peor que no ofrecer ninguno.
 */
export function Vacio({
  titulo,
  detalle,
  Icono = Inbox,
  accion,
}: {
  titulo: string;
  detalle?: string;
  Icono?: LucideIcon;
  accion?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-12 text-center">
      <span className="grid size-10 place-items-center rounded-full bg-muted text-muted-foreground">
        <Icono size={18} strokeWidth={1.75} aria-hidden />
      </span>
      <p className="font-medium text-foreground">{titulo}</p>
      {detalle && <p className="max-w-sm text-sm text-muted-foreground">{detalle}</p>}
      {accion && <div className="mt-2">{accion}</div>}
    </div>
  );
}
