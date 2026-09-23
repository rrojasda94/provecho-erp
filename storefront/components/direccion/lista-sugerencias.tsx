"use client";

import type { Sugerencia } from "./buscador-lugares";

/**
 * El desplegable del combobox de dirección (ADR-072). Copia de
 * `frontend/components/direccion/lista-sugerencias.tsx` con la paleta de la
 * marca: este sitio no tiene modo oscuro ni los tokens del ERP.
 *
 * Presentación pura: devuelve `null` con la lista vacía para que el padre no
 * gaste un `&&` —el componente ya roza el límite de complejidad del linter.
 *
 * Filas con `onMouseDown` y no `onClick`: el click tiene que ganarle al
 * `blur` del input, que si no cierra la lista antes de que el click llegue.
 *
 * La atribución de Google al pie es obligatoria: una lista propia que muestra
 * resultados de Places fuera de un mapa de Google tiene que mostrarla ella
 * misma.
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
    <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-lg border-2 border-negro bg-white shadow-lg">
      <ul id={idLista} role="listbox" className="max-h-56 overflow-auto py-1">
        {sugerencias.map((s, i) => (
          <li
            key={s.id}
            id={idOpcion(i)}
            role="option"
            aria-selected={i === activo}
            className={`cursor-pointer px-3 py-2 text-sm ${i === activo ? "bg-crema-2" : ""}`}
            onMouseDown={(e) => {
              e.preventDefault();
              onTomar(i);
            }}
          >
            <span className="block font-bold">{s.principal}</span>
            {s.secundario && <span className="block text-xs text-humo">{s.secundario}</span>}
          </li>
        ))}
      </ul>
      <div className="flex justify-end border-t border-negro/20 px-3 py-1.5">
        {/* eslint-disable-next-line @next/next/no-img-element -- logo remoto
            de Google, no una imagen local que `next/image` pueda optimizar. */}
        <img
          src="https://maps.gstatic.com/mapfiles/api-3/images/powered-by-google-on-white3.png"
          alt="Con tecnología de Google"
          className="h-4"
        />
      </div>
    </div>
  );
}
