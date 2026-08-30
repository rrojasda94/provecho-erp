/**
 * Tipos y estado inicial del formulario de postulación.
 *
 * Viven acá y no en `actions.ts` por lo mismo que en la landing: ese archivo
 * lleva `"use server"` y un módulo con esa directiva **solo puede exportar
 * funciones asíncronas** — exportar una constante desde ahí compila, pasa el
 * build y revienta en el navegador la primera vez que alguien abre la página.
 */

export type EstadoPostulacion = {
  error: string;
  /** El acuse. La API no devuelve la ficha del postulante a quien no tiene
   *  sesión (ADR-087), así que lo único que vuelve es que entró y a qué. */
  puesto: string;
};

export const ESTADO_INICIAL: EstadoPostulacion = { error: "", puesto: "" };
