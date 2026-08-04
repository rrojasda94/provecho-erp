"use client";

import { useEffect, useRef, useState } from "react";

import { buscarPersonasAction, type PersonaBusqueda } from "./actions";

const RETRASO_MS = 300;
const LARGO_MINIMO = 2;

function etiqueta(p: PersonaBusqueda): string {
  return p.numero_documento
    ? `${p.apellidos}, ${p.nombres} — ${p.numero_documento}`
    : `${p.apellidos}, ${p.nombres}`;
}

/**
 * Buscador de persona existente (`/personas/buscar`, con debounce) — no un
 * `<select>` con todo el catálogo cargado de una vez, que no escala pasadas
 * unas pocas decenas de personas. Manda `persona_id` por un input oculto;
 * la validación de "hace falta elegir alguien" queda del lado del servidor
 * (ya la tenía cada action) — un truco de accesibilidad para que `required`
 * funcione en un input oculto no vale la complejidad que agrega.
 */
export function PersonaPicker({
  name,
  placeholder = "Buscar por nombre o documento...",
}: {
  name: string;
  placeholder?: string;
}) {
  const [consulta, setConsulta] = useState("");
  const [resultados, setResultados] = useState<PersonaBusqueda[]>([]);
  const [elegida, setElegida] = useState<PersonaBusqueda | null>(null);
  const [abierto, setAbierto] = useState(false);
  const [buscando, setBuscando] = useState(false);
  const temporizador = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => () => clearTimeout(temporizador.current), []);

  function alCambiar(valor: string) {
    setConsulta(valor);
    setElegida(null);
    clearTimeout(temporizador.current);
    if (valor.trim().length < LARGO_MINIMO) {
      setResultados([]);
      setAbierto(false);
      return;
    }
    setBuscando(true);
    setAbierto(true);
    temporizador.current = setTimeout(async () => {
      const encontradas = await buscarPersonasAction(valor.trim());
      setResultados(encontradas);
      setBuscando(false);
    }, RETRASO_MS);
  }

  function elegir(p: PersonaBusqueda) {
    setElegida(p);
    setConsulta(etiqueta(p));
    setAbierto(false);
  }

  return (
    <div className="relative">
      <input type="hidden" name={name} value={elegida?.id ?? ""} />
      <input
        value={consulta}
        onChange={(e) => alCambiar(e.target.value)}
        onFocus={() => resultados.length > 0 && setAbierto(true)}
        onBlur={() => setTimeout(() => setAbierto(false), 150)}
        placeholder={placeholder}
        autoComplete="off"
      />
      {abierto && (
        <ul className="absolute z-10 mt-1 max-h-48 w-full overflow-auto rounded border border-gray/30 bg-white shadow-md">
          {buscando ? (
            <li className="px-3 py-2 text-sm text-gray">Buscando...</li>
          ) : resultados.length === 0 ? (
            <li className="px-3 py-2 text-sm text-gray">Sin resultados.</li>
          ) : (
            resultados.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  // onMouseDown, no onClick: dispara antes del onBlur del
                  // input, que si no cierra la lista primero y el click
                  // nunca llega al botón.
                  onMouseDown={() => elegir(p)}
                  className="block w-full px-3 py-2 text-left text-sm hover:bg-cream"
                >
                  {etiqueta(p)}
                </button>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
