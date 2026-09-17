"use client";

import { useEffect } from "react";

/**
 * Anima la entrada de todo elemento `.revelar` cuando cruza el viewport
 * (ADR-103 decisión 10 — CSS + `IntersectionObserver`, sin librería).
 *
 * Un `MutationObserver` re-observa lo que el router de Next agregue al
 * navegar entre páginas del sitio (mismo layout, `<main>` reemplazado):
 * sin esto, el observer se armaría solo una vez con los elementos de la
 * primera página y nunca vería los de las siguientes.
 */
export function RevelarObservador() {
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const interseccion = new IntersectionObserver(
      (entradas) => {
        for (const entrada of entradas) {
          if (entrada.isIntersecting) {
            entrada.target.classList.add("visible");
            interseccion.unobserve(entrada.target);
          }
        }
      },
      { threshold: 0.15 },
    );

    const observarTodo = () => {
      document.querySelectorAll(".revelar:not(.visible)").forEach((el) => interseccion.observe(el));
    };
    observarTodo();

    const mutaciones = new MutationObserver(observarTodo);
    mutaciones.observe(document.body, { childList: true, subtree: true });

    return () => {
      interseccion.disconnect();
      mutaciones.disconnect();
    };
  }, []);

  return null;
}
