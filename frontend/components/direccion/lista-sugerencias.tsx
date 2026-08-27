"use client";

import type { Sugerencia } from "./buscador-lugares";

/**
 * El desplegable del combobox de dirección (ADR-072). Presentación pura:
 * devuelve `null` con la lista vacía para que el padre no gaste un `&&` —el
 * componente ya roza el límite de complejidad del linter.
 *
 * Filas con `onMouseDown` y no `onClick`: el click tiene que ganarle al
 * `blur` del input, que si no cierra la lista antes de que el click llegue
 * (mismo criterio que `PersonaPicker`).
 *
 * La atribución de Google al pie es obligatoria: `PlaceAutocompleteElement`
 * la dibujaba solo, y una lista propia que muestra resultados de Places
 * fuera de un mapa de Google tiene que mostrarla ella misma.
 */
export function ListaSugerencias({
  sugerencias,
  activo,
  idLista,
  idOpcion,
  onTomar,
}: {
  sugerencias: Sugerencia[];
  activo: number;
  idLista: string;
  idOpcion: (i: number) => string;
  onTomar: (i: number) => void;
}) {
  if (sugerencias.length === 0) return null;

  return (
    <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-lg bg-popover text-popover-foreground shadow-md ring-1 ring-foreground/10">
      <ul id={idLista} role="listbox" className="max-h-56 overflow-auto py-1">
        {sugerencias.map((s, i) => (
          <li
            key={s.id}
            id={idOpcion(i)}
            role="option"
            aria-selected={i === activo}
            className={`cursor-pointer px-3 py-2 text-sm ${i === activo ? "bg-muted" : ""}`}
            onMouseDown={(e) => {
              e.preventDefault();
              onTomar(i);
            }}
          >
            <span className="block font-medium">{s.principal}</span>
            {s.secundario && (
              <span className="block text-xs text-muted-foreground">{s.secundario}</span>
            )}
          </li>
        ))}
      </ul>
      {/* Dos variantes por tema: el logo "on white" es ilegible sobre el
          fondo oscuro de `--popover` en modo oscuro. */}
      <div className="flex justify-end border-t border-border px-3 py-1.5">
        {/* eslint-disable-next-line @next/next/no-img-element -- logo remoto
            de Google, no una imagen local que `next/image` pueda optimizar. */}
        <img
          src="https://maps.gstatic.com/mapfiles/api-3/images/powered-by-google-on-white3.png"
          alt="Con tecnología de Google"
          className="h-4 dark:hidden"
        />
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="https://maps.gstatic.com/mapfiles/api-3/images/powered-by-google-on-non-white3.png"
          alt="Con tecnología de Google"
          className="hidden h-4 dark:block"
        />
      </div>
    </div>
  );
}
