"use client";

/**
 * ¿Hay una pantalla **de esta app** a la que volver?
 *
 * Se cuenta a mano porque no hay de dónde leerlo: en Next 16 App Router
 * `window.history.state` no trae índice (solo `__NA` y el árbol interno),
 * `document.referrer` queda vacío en las navegaciones blandas —que son
 * todas, dentro del shell— y `history.length` incluye lo que el usuario hizo
 * antes de entrar al ERP. Medido en el navegador, no supuesto.
 *
 * Módulo y no estado de React: el contador tiene que sobrevivir a que cada
 * pantalla monte y desmonte sus componentes, y un módulo del bundle se
 * evalúa una sola vez. Se reinicia con una recarga dura, y ahí el `←` cae al
 * padre: conservador a propósito, porque después de un F5 no sabemos qué hay
 * detrás.
 */

let saltos = 0;

export function anotarNavegacion(): void {
  saltos += 1;
}

/** `> 1` y no `> 0`: el primer conteo es la pantalla de entrada, que no es
 * un salto — todavía no hay nada atrás. */
export function hayHistorialPropio(): boolean {
  return saltos > 1;
}

/** Solo para las pruebas: cada caso arranca de cero. */
export function reiniciarHistorial(): void {
  saltos = 0;
}
