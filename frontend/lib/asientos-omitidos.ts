/**
 * Cómo se nombra y a dónde lleva cada asiento omitido (ADR-089).
 *
 * El aviso de Asientos decía «hay 3 asientos que no se escribieron» y nada
 * más: ni de qué operación, ni cuál, ni dónde verla. Acá el evento técnico
 * (`sales.venta_confirmada`) se traduce a la operación que el contador
 * reconoce y, cuando el documento tiene ficha, a su enlace.
 */

type Origen = { operacion: string; ruta?: (ref: string) => string };

const venta = (ref: string) => `/ventas/${ref}`;
const orden = (ref: string) => `/compras/ordenes-compra/${ref}`;

const ORIGENES: Record<string, Origen> = {
  "sales.venta_confirmada": { operacion: "Venta", ruta: venta },
  "sales.venta_pagada": { operacion: "Cobro de venta", ruta: venta },
  "sales.venta_anulada": { operacion: "Anulación de venta", ruta: venta },
  "sales.comprobante_emitido": { operacion: "IGV de comprobante emitido" },
  "purchases.oc_emitida": { operacion: "Orden de compra emitida", ruta: orden },
  "purchases.compra_recibida": {
    operacion: "Recepción de compra",
    ruta: orden,
  },
  "purchases.comprobante_conforme": {
    operacion: "Factura de proveedor conforme",
  },
  "inventory.consumo_personal_valorizado": {
    operacion: "Consumo del personal",
    ruta: venta,
  },
  "inventory.consumo_personal_reversado": {
    operacion: "Reversa de consumo del personal",
    ruta: venta,
  },
  "inventory.transferencia_recibida": {
    operacion: "Traslado con faltante",
    ruta: () => "/inventario/transferencias",
  },
  "inventory.merma_registrada": {
    operacion: "Merma",
    ruta: (ref) => `/inventario/skus/${ref}`,
  },
  "production.orden_desechada": {
    operacion: "Desecho de producción",
    ruta: (ref) => `/produccion/ordenes/${ref}`,
  },
  "accounting.depreciacion_mensual": {
    operacion: "Depreciación mensual",
    // `<activo_id>:<periodo>`: el activo es lo que tiene ficha.
    ruta: (ref) => `/activos/activos/${ref.split(":")[0]}`,
  },
};

const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(:.*)?$/i;

/** La operación en palabras y, si tiene ficha, su ruta. Un evento nuevo que
 * nadie tradujo se muestra tal cual en vez de desaparecer. */
export function origenDe(
  evento: string,
  referencia: string,
): { operacion: string; ruta: string | null } {
  const origen = ORIGENES[evento];
  if (!origen) return { operacion: evento, ruta: null };
  // Un listener que reventó antes de leer el payload anota `?`: no hay a
  // dónde llevar, y `/ventas/?` sería un 404.
  const valida = UUID.test(referencia);
  return {
    operacion: origen.operacion,
    ruta: origen.ruta && valida ? origen.ruta(referencia) : null,
  };
}

/** Qué hacer con cada motivo. El aviso sirve si dice dónde arreglarlo. */
export const QUE_HACER: Record<string, string> = {
  periodo_cerrado:
    "el mes ya estaba cerrado cuando llegó la operación: se registra con un asiento manual en el periodo abierto",
  sin_cuentas:
    "a la empresa le falta plan de cuentas: importalo en Plan de cuentas y volvé a registrar la operación",
  sin_plantilla:
    "ese evento todavía no tiene asiento definido en el ERP: hay que reportarlo",
  error:
    "el ERP falló al escribir el asiento: reportalo con el detalle y registrá el asiento a mano mientras tanto",
};

export const NOMBRE_MOTIVO: Record<string, string> = {
  periodo_cerrado: "Periodo cerrado",
  sin_cuentas: "Sin plan de cuentas",
  sin_plantilla: "Sin plantilla",
  error: "Error del ERP",
};
