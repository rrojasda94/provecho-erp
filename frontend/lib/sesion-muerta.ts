/**
 * La sesión del navegador se murió: no hay renovación posible, hay que
 * volver a entrar.
 *
 * Es un dato de una sola vía —una vez muerta no revive sin recargar— y por
 * eso alcanza un módulo con una bandera y sus suscriptores, sin contexto de
 * React ni librería de estado. Lo consume `lib/cliente-api.ts`, que es por
 * donde salen **todas** las llamadas del navegador, y lo dibuja
 * `components/sesion/aviso-sesion-expirada.tsx`.
 *
 * Por qué un 401 del navegador significa exactamente eso: desde ADR-073 el
 * token de acceso lo rota `middleware.ts` en cada request, refresco
 * incluido, y ADR-084 le puso el tope de las ocho horas quietas. Un 401 que
 * llega igual ya pasó por ese intento: el refresh está vencido, revocado o
 * reusado. No es un parpadeo de red — es la señal más confiable de "volvé a
 * entrar" que tiene el cliente, y hasta hoy no la escuchaba nadie.
 *
 * Sin imports, como `lib/carga.ts` y `lib/errores.ts`, para que `node --test`
 * lo corra sin arrastrar nada de Next.
 */

let muerta = false;
const oyentes = new Set<() => void>();

/** ¿Ya sabemos que la sesión no vale? */
export function estaMuerta(): boolean {
  return muerta;
}

/**
 * Marca la sesión como muerta y avisa una sola vez.
 *
 * Idempotente a propósito: el KDS refresca cada 3 s y el PDV guarda su
 * borrador cada 800 ms, así que la primera sesión vencida dispara una
 * andanada de 401 — con un aviso por cada uno, el usuario vería el mismo
 * cartel montándose sobre sí mismo.
 */
export function marcarMuerta(): void {
  if (muerta) return;
  muerta = true;
  for (const oyente of oyentes) oyente();
}

/** Se suscribe al momento de la muerte. Devuelve cómo desuscribirse, que es
 * la forma que espera el `useEffect` que lo use. */
export function suscribir(oyente: () => void): () => void {
  oyentes.add(oyente);
  return () => {
    oyentes.delete(oyente);
  };
}

/** Solo para las pruebas: el estado real solo se limpia recargando. */
export function reiniciar(): void {
  muerta = false;
  oyentes.clear();
}
