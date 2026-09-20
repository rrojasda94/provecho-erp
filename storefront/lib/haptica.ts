"use client";

/**
 * Vibración corta al tocar algo que cuenta (agregar al carrito, marcar
 * favorito). Mejora progresiva: Safari de iOS no implementa `vibrate` y
 * Chrome la ignora si el visitante nunca interactuó con la página, así que
 * nada depende de que funcione — el aviso visual va siempre aparte.
 *
 * Se respeta `prefers-reduced-motion`: quien la pide suele pedirla por
 * sensibilidad vestibular, y una vibración es movimiento.
 */
export function vibrar(ms = 10): void {
  try {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    navigator.vibrate?.(ms);
  } catch {
    // Navegador sin `vibrate` o con permisos raros: no pasa nada.
  }
}
