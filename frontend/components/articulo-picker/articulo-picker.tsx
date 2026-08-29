"use client";

import { ComboboxRemoto, type Opcion } from "@/components/ui/combobox";

import { buscarArticulosAction } from "./actions";

/**
 * Elegir un artículo del catálogo de inventario, buscando por nombre o por
 * código interno.
 *
 * Es el único selector del ERP que pregunta al servidor en cada búsqueda —el
 * porqué está en `actions.ts`—. Se envuelve acá y no se arma en cada pantalla
 * para que las seis que eligen un artículo no repitan el cableado ni se
 * desincronicen el día que la búsqueda cambie.
 */
export function ArticuloPicker({
  name,
  etiqueta,
  tipos,
  requerido,
  deshabilitado,
  className,
  marcador,
  iniciales,
  value,
  defaultValue,
  alCambiar,
}: {
  name?: string;
  etiqueta: string;
  /** Acota el catálogo a uno o varios tipos (`empaque`, `subreceta`...) como
   * ya hacía el `<select>` que esto reemplaza. El filtro lo aplica la base:
   * hacerlo acá filtraría solo lo que vino en la página. */
  tipos?: readonly string[];
  requerido?: boolean;
  deshabilitado?: boolean;
  className?: string;
  marcador?: string;
  iniciales?: readonly Opcion[];
  value?: string | null;
  defaultValue?: string | null;
  alCambiar?: (valor: string | null) => void;
}) {
  return (
    <ComboboxRemoto
      name={name}
      etiqueta={etiqueta}
      requerido={requerido}
      deshabilitado={deshabilitado}
      className={className}
      marcador={marcador ?? "Buscar por nombre o código..."}
      iniciales={iniciales}
      value={value}
      defaultValue={defaultValue}
      alCambiar={alCambiar}
      buscar={(consulta) => buscarArticulosAction(consulta, tipos)}
    />
  );
}
