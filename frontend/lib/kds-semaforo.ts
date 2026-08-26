/**
 * Semáforo del KDS: cuánto lleva esperando un pedido y de qué color va.
 *
 * Vive aparte del cliente HTTP por lo mismo que `kds-avance.ts`: es lógica
 * que puede equivocarse en silencio —un pedido que nunca se pone rojo no
 * avisa de nada— y así se prueba con `node --test` sin montar React.
 *
 * El reloj lo corre el navegador. El servidor manda `creado_en` y los
 * umbrales; recalcular y reenviar la cola entera cada segundo para mostrar
 * un cronómetro sería tráfico por algo que la pantalla ya sabe.
 */

export type Semaforo = {
  minutos_ambar: number;
  minutos_rojo: number;
  color_normal: string;
  color_ambar: string;
  color_rojo: string;
};

export type Nivel = "normal" | "ambar" | "rojo";

/** Minutos enteros desde que se tomó el pedido. `0` si la fecha no se
 * entiende: un pedido sin hora legible se pinta como recién llegado, no se
 * esconde ni se pinta de rojo. */
export function minutosDesde(creadoEn: string, ahora: number = Date.now()): number {
  const inicio = new Date(creadoEn).getTime();
  if (Number.isNaN(inicio)) return 0;
  return Math.max(0, Math.floor((ahora - inicio) / 60000));
}

/** En qué franja cae. El rojo se evalúa primero: con umbrales pegados
 * (`ambar: 8`, `rojo: 9`) preguntar por el ámbar antes dejaría el rojo
 * inalcanzable. */
export function nivelDe(minutos: number, s: Semaforo): Nivel {
  if (minutos >= s.minutos_rojo) return "rojo";
  if (minutos >= s.minutos_ambar) return "ambar";
  return "normal";
}

/** `12` → `"12 min"`. Una hora larga en minutos deja de leerse de un
 * vistazo, que es la única forma en que se mira una pantalla de cocina. */
export function reloj(minutos: number): string {
  if (minutos < 60) return `${minutos} min`;
  return `${Math.floor(minutos / 60)} h ${minutos % 60} min`;
}
