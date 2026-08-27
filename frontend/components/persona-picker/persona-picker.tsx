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

/** El desplegable de resultados, aparte para no engordar la complejidad de
 * `PersonaPicker` — es puro renderizado, sin estado propio. */
function ListaResultados({
  buscando,
  resultados,
  elegir,
}: {
  buscando: boolean;
  resultados: PersonaBusqueda[];
  elegir: (p: PersonaBusqueda) => void;
}) {
  if (buscando) {
    return (
      <ul className="absolute z-10 mt-1 max-h-48 w-full overflow-auto rounded border border-gray/30 bg-white shadow-md">
        <li className="px-3 py-2 text-sm text-gray">Buscando...</li>
      </ul>
    );
  }
  if (resultados.length === 0) {
    return (
      <ul className="absolute z-10 mt-1 max-h-48 w-full overflow-auto rounded border border-gray/30 bg-white shadow-md">
        <li className="px-3 py-2 text-sm text-gray">Sin resultados.</li>
      </ul>
    );
  }
  return (
    <ul className="absolute z-10 mt-1 max-h-48 w-full overflow-auto rounded border border-gray/30 bg-white shadow-md">
      {resultados.map((p) => (
        <li key={p.id}>
          <button
            type="button"
            // onMouseDown, no onClick: dispara antes del onBlur del input,
            // que si no cierra la lista primero y el click nunca llega al
            // botón.
            onMouseDown={() => elegir(p)}
            className="block w-full px-3 py-2 text-left text-sm hover:bg-cream"
          >
            {etiqueta(p)}
          </button>
        </li>
      ))}
    </ul>
  );
}

/**
 * Buscador de persona existente (`/personas/buscar`, con debounce) — no un
 * `<select>` con todo el catálogo cargado de una vez, que no escala pasadas
 * unas pocas decenas de personas. Manda `persona_id` por un input oculto;
 * la validación de "hace falta elegir alguien" queda del lado del servidor
 * (ya la tenía cada action) — un truco de accesibilidad para que `required`
 * funcione en un input oculto no vale la complejidad que agrega.
 *
 * `inicial` es la persona ya vinculada (edición): sin esto el campo se veía
 * siempre vacío al reabrir un editor, aunque el vínculo sí se hubiera
 * guardado — el bug reportado. Se re-siembra en el `reset` del `<form>`
 * dueño (vía `.form` del input oculto): `DialogoFormulario` deja los hijos
 * montados entre aperturas y llama `form.reset()` al cerrar, y el reset
 * nativo no toca el estado de React — sin este listener, reabrir mostraba
 * lo último tecleado, no lo guardado.
 */
export function PersonaPicker({
  name,
  placeholder = "Buscar por nombre o documento...",
  inicial = null,
}: {
  name: string;
  placeholder?: string;
  inicial?: PersonaBusqueda | null;
}) {
  const [consulta, setConsulta] = useState(inicial ? etiqueta(inicial) : "");
  const [resultados, setResultados] = useState<PersonaBusqueda[]>([]);
  const [elegida, setElegida] = useState<PersonaBusqueda | null>(inicial);
  const [abierto, setAbierto] = useState(false);
  const [buscando, setBuscando] = useState(false);
  const temporizador = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const inputOculto = useRef<HTMLInputElement>(null);

  useEffect(() => () => clearTimeout(temporizador.current), []);

  useEffect(() => {
    const form = inputOculto.current?.form;
    if (!form) return;
    const alResetear = () => {
      setElegida(inicial);
      setConsulta(inicial ? etiqueta(inicial) : "");
      setResultados([]);
      setAbierto(false);
    };
    form.addEventListener("reset", alResetear);
    return () => form.removeEventListener("reset", alResetear);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  function quitar() {
    // `""` en el input oculto es lo que la action lee como "desvincular"
    // (ADR-070): tiene que ser un clic deliberado, no el efecto de borrar
    // el texto con backspace.
    setElegida(null);
    setConsulta("");
    setResultados([]);
    setAbierto(false);
  }

  return (
    <div className="relative flex items-center gap-2">
      <input type="hidden" name={name} value={elegida?.id ?? ""} ref={inputOculto} />
      <input
        className="flex-1"
        value={consulta}
        onChange={(e) => alCambiar(e.target.value)}
        onFocus={() => resultados.length > 0 && setAbierto(true)}
        onBlur={() => setTimeout(() => setAbierto(false), 150)}
        placeholder={placeholder}
        autoComplete="off"
      />
      {(elegida || consulta) && (
        <button
          type="button"
          onClick={quitar}
          className="shrink-0 text-xs font-medium text-gray hover:text-foreground"
        >
          Quitar
        </button>
      )}
      {abierto && (
        <ListaResultados buscando={buscando} resultados={resultados} elegir={elegir} />
      )}
    </div>
  );
}
