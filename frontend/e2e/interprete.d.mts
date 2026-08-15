/**
 * Tipos de `interprete.mjs`.
 *
 * El módulo es `.mjs` porque lo importan los scripts que corren con `node` a
 * secas —`preparar-bd.mjs`, `servidor-api.mjs`—, que no pasan por
 * TypeScript. Desde que una prueba de uso también lo usa (`uso/planilla.ts`),
 * `tsc` lo alcanza y sin declaración lo trata como `any` implícito, que con
 * `strict` es error. Escribir la firma es más barato que convertir el módulo
 * a `.mts` y arrastrar a los tres scripts que lo importan.
 */

/** Raíz del checkout desde el que se corre (worktree o repo principal). */
export declare const RAIZ: string;

/** Ruta al Python que tiene instaladas las dependencias del repo. */
export declare function interprete(): string;
