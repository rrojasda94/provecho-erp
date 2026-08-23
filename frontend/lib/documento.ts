/**
 * Qué documento es, por su largo. Es la única regla que distingue a una
 * persona natural de una empresa en todo el ERP de cara al cliente: 8 dígitos
 * es DNI (RENIEC, boleta), 11 es RUC (SUNAT, factura) — RN-CPP-003.
 *
 * Vive acá y no dentro de un componente por lo mismo que `permisos.ts`:
 * `npm test` corre sobre Node pelado, que hace type-stripping pero no
 * transforma JSX. La regla que decide a qué padrón se le pregunta tiene que
 * poder probarse sin montar React.
 */

export const LARGO_DNI = 8;
export const LARGO_RUC = 11;

export type TipoConsulta = "dni" | "ruc";

/**
 * `null` cuando el número todavía no es ninguno de los dos: 7 dígitos no es
 * "un DNI casi listo", es un número que no se puede consultar. Se prefiere
 * decirlo a adivinar — una consulta a ciegas gasta cuota de un proveedor
 * pago y vuelve con "no encontrado" que no significa nada.
 */
export function tipoPorLargo(numero: string): TipoConsulta | null {
  const limpio = numero.trim();
  if (!/^\d+$/.test(limpio)) return null;
  if (limpio.length === LARGO_DNI) return "dni";
  if (limpio.length === LARGO_RUC) return "ruc";
  return null;
}

/** Vacío también vale: se vende sin documento (RN-PER-005), y el
 * comprobante sale a nombre de «Clientes varios». */
export function documentoValido(numero: string): boolean {
  return numero.length === 0 || tipoPorLargo(numero) !== null;
}
