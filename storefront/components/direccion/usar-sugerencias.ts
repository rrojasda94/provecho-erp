"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";

import { siguienteActivo } from "@/lib/direcciones";

import type { Buscador, Sugerencia } from "./buscador-lugares";

const RETRASO_MS = 300;
const LARGO_MINIMO = 3;

/**
 * Estado y manejadores del combobox de dirección (ADR-072). Rebote, apertura,
 * fila resaltada y teclado — todo lo que no es SDK ni JSX, aparte del
 * componente por el límite de complejidad del linter.
 */
export function useSugerencias(buscador: Buscador | null, alElegir: (s: Sugerencia) => void) {
  const [lista, setLista] = useState<Sugerencia[]>([]);
  const [abierto, setAbierto] = useState(false);
  const [activo, setActivo] = useState(-1);
  const idLista = useId();

  const temporizador = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  // Descarta una respuesta que llegó tarde, de una búsqueda que ya no es la
  // última: `fetchAutocompleteSuggestions` no acepta `AbortSignal`.
  const pedido = useRef(0);

  useEffect(() => () => clearTimeout(temporizador.current), []);

  const cerrar = useCallback(() => {
    setAbierto(false);
    setActivo(-1);
  }, []);

  const alTeclear = useCallback(
    (texto: string) => {
      clearTimeout(temporizador.current);
      if (!buscador || texto.trim().length < LARGO_MINIMO) {
        setLista([]);
        cerrar();
        return;
      }
      const mio = ++pedido.current;
      temporizador.current = setTimeout(async () => {
        const encontradas = await buscador.buscar(texto.trim());
        if (mio !== pedido.current) return;
        setLista(encontradas);
        setActivo(-1);
        setAbierto(encontradas.length > 0);
      }, RETRASO_MS);
    },
    [buscador, cerrar],
  );

  const tomar = useCallback(
    (indice: number) => {
      const elegida = lista[indice];
      if (!elegida) return;
      alElegir(elegida);
      setLista([]);
      cerrar();
    },
    [lista, alElegir, cerrar],
  );

  const alTeclado = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (!abierto) return;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        setActivo((a) => siguienteActivo(a, lista.length, e.key));
        return;
      }
      if (e.key === "Enter" && activo >= 0) {
        // Sin esto, elegir con el teclado envía el `<form>` que contiene el
        // campo (`DialogoFormulario`) en vez de anclar la dirección.
        e.preventDefault();
        tomar(activo);
        return;
      }
      if (e.key === "Escape") {
        // `stopPropagation` además del `preventDefault`: el `<dialog>` nativo
        // que envuelve al formulario también escucha Escape, y sin cortar la
        // propagación acá se cierra el diálogo entero por bajar una
        // sugerencia y arrepentirse.
        e.preventDefault();
        e.stopPropagation();
        cerrar();
        return;
      }
      if (e.key === "Tab") cerrar();
    },
    [abierto, lista.length, activo, tomar, cerrar],
  );

  const alPerderFoco = useCallback(() => {
    // No cierra al toque: si cerrara antes, el `onMouseDown` de la fila
    // nunca llegaría a disparar (mismo criterio que `PersonaPicker`).
    setTimeout(cerrar, 150);
  }, [cerrar]);

  // Reabre la última lista sin volver a preguntarle a Google: una tecla
  // gastada por sesión ya cuesta lo suyo (ADR-072), y recuperar el foco no
  // es un tecleo nuevo.
  const alEnfocar = useCallback(() => {
    if (lista.length > 0) setAbierto(true);
  }, [lista.length]);

  return {
    lista,
    abierto,
    activo,
    idLista,
    idOpcion: (i: number) => `${idLista}-${i}`,
    alTeclear,
    alTeclado,
    alEnfocar,
    alPerderFoco,
    tomar,
  };
}

export type Sugerencias = ReturnType<typeof useSugerencias>;
