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

/**
 * El vocabulario de `persona.tipo_documento`, espejo de `src/shared/documento.py`.
 * Estaba escrito a mano en tres formularios que no coincidían —uno ofrecía
 * `ruc`, otro `carne_extranjeria`— y el backend rechazaba los dos con un 500.
 */
export const TIPOS_DOCUMENTO = ["dni", "ce", "pasaporte", "ruc"] as const;

export type TipoDocumento = (typeof TIPOS_DOCUMENTO)[number];

/** Los de una persona natural: en Ventas, 11 dígitos hacen al cliente
 * jurídico y su RUC va en el cliente, no en la persona. */
export const TIPOS_DOCUMENTO_NATURAL = ["dni", "ce", "pasaporte"] as const;

export const ETIQUETA_DOCUMENTO: Record<TipoDocumento, string> = {
  dni: "DNI",
  ce: "Carné de extranjería",
  pasaporte: "Pasaporte",
  ruc: "RUC",
};

/** Los que son un número de largo fijo. CE y pasaporte no: los emite otro país. */
export const LARGO_EXACTO: Partial<Record<TipoDocumento, number>> = {
  dni: LARGO_DNI,
  ruc: LARGO_RUC,
};

export const LARGO_MAXIMO_DOCUMENTO = 20;
const LARGO_MINIMO_DOCUMENTO = 6;

/** Vacío vale: el documento es opcional (ADR-018). Con algo escrito, el largo
 * lo manda el tipo — es la misma regla que `shared.documento.validar`. */
export function documentoValidoPorTipo(tipo: string, numero: string): boolean {
  const limpio = numero.trim();
  if (limpio.length === 0) return true;
  const exacto = LARGO_EXACTO[tipo as TipoDocumento];
  if (exacto !== undefined) return /^\d+$/.test(limpio) && limpio.length === exacto;
  return (
    /^[a-zA-Z0-9]+$/.test(limpio) &&
    limpio.length >= LARGO_MINIMO_DOCUMENTO &&
    limpio.length <= LARGO_MAXIMO_DOCUMENTO
  );
}
