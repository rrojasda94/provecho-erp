/**
 * Los tipos y el estado inicial del formulario.
 *
 * Viven acá y no en `actions.ts` porque ese archivo lleva `"use server"`, y
 * un módulo con esa directiva **solo puede exportar funciones asíncronas**:
 * cada export se convierte en un endpoint. Exportar `ESTADO_INICIAL` desde
 * ahí compila y pasa el build sin una palabra, y revienta en el navegador
 * con «A "use server" file can only export async functions, found object» la
 * primera vez que alguien abre la página.
 *
 * Los `type` no molestan —TypeScript los borra— pero se mudan igual: tenerlos
 * al lado del valor evita que el siguiente que agregue una constante la
 * ponga del lado equivocado.
 */

export type Cupon = {
  codigo: string;
  vigente_hasta: string;
  descuento_porcentaje: string;
  ya_estaba_registrado: boolean;
};

export type EstadoRegistro = {
  error: string;
  cupon: Cupon | null;
};

export const ESTADO_INICIAL: EstadoRegistro = { error: "", cupon: null };
