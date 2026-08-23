/**
 * Puente temporal: el pinpad se mudó a `components/pinpad/` (ADR-050).
 *
 * Existe para no tocar los `import` de `dialogos.tsx` y `bloqueo.tsx`
 * mientras otra rama trabaja sobre ellos — cambiarlos acá y allá a la vez es
 * un conflicto garantizado sobre un archivo de 900 líneas. Se borra con esos
 * dos imports en la rama que los toque; queda anotado en
 * `docs/roadmap/deuda/frontend.md`.
 */
export { default } from "@/components/pinpad/pinpad";
