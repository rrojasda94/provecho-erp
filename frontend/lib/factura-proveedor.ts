/**
 * El cuerpo de la factura del proveedor, armado desde un formulario.
 *
 * Vive en `lib/` y no junto a las acciones porque un archivo `"use server"`
 * solo puede exportar funciones `async`, y esto es una transformación pura.
 * Que además se pueda probar sin levantar nada es la razón por la que el
 * proyecto ya empuja este tipo de reglas acá (`lib/cobro.ts`, `lib/carga.ts`).
 *
 * Lo que resuelve, y que un `Object.fromEntries(formData)` no: un campo vacío
 * tiene que **desaparecer**, no viajar como `""`. El contrato espera esos
 * campos ausentes o con valor, y `fecha_emision: ""` es un 422.
 */

/** Lo que se lee de un formulario: `FormData` o cualquier cosa con `get`. */
export type CamposFactura = { get(nombre: string): FormDataEntryValue | null };

export type CuerpoFactura = {
  idempotency_key: string;
  tipo: string;
  serie: string;
  correlativo: number;
  sustento: string;
  emisor_num_doc?: string;
  fecha_emision?: string;
  total?: string;
  gravado_igv?: boolean;
};

export function cuerpoDeFactura(
  campos: CamposFactura,
  idempotencyKey: string,
): CuerpoFactura {
  const texto = (campo: string) => String(campos.get(campo) ?? "").trim();
  const opcional = (campo: string) => texto(campo) || undefined;
  const gravado = texto("gravado_igv");

  return {
    idempotency_key: idempotencyKey,
    tipo: texto("tipo") || "factura",
    serie: texto("serie"),
    correlativo: Number(campos.get("correlativo") ?? 0),
    sustento: texto("sustento") || "contrato_credito",
    emisor_num_doc: opcional("emisor_num_doc"),
    fecha_emision: opcional("fecha_emision"),
    total: opcional("total"),
    // Tres estados y no un checkbox: vacío significa "que lo decida el
    // régimen de la empresa" (ADR-081), que no es lo mismo que "no lleva
    // IGV". Un booleano no puede expresar la diferencia.
    gravado_igv: gravado === "" ? undefined : gravado === "si",
  };
}

/** Qué le falta a la factura para poder mandarse. `null` = está completa. */
export function faltaEnLaFactura(cuerpo: CuerpoFactura): string | null {
  if (!cuerpo.serie) return "La factura necesita su serie.";
  if (!cuerpo.correlativo || cuerpo.correlativo < 1) {
    return "La factura necesita su número.";
  }
  return null;
}
