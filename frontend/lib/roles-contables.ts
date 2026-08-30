/**
 * Los roles contables que una categoría puede mapear a una cuenta del PCGE
 * (ADR-086), con lo que significan para quien los configura —que no es
 * contador— y el código que el ERP usa si nadie configura nada.
 *
 * Vive en `lib/` y no dentro de la pantalla porque los usan **dos** piezas
 * —el formulario y la server action que lo lee—, y dos listas de siete
 * strings se separan en el primer rol que alguien agregue. Que además no se
 * separen del backend lo fija `roles-contables.test.ts`, que las compara
 * contra `AsientoContableConfig` del contrato exportado.
 */

export type RolContable = {
  /** La clave del JSON y el sufijo del campo del formulario. */
  rol: string;
  etiqueta: string;
  /** Qué cuenta usa si nadie configura nada, y por qué existe el rol. */
  ayuda: string;
};

export const ROLES_CONTABLES: RolContable[] = [
  {
    rol: "compra",
    etiqueta: "Compra (elemento 6)",
    ayuda: "6011 · qué cuenta debita lo que se compra",
  },
  {
    rol: "existencia",
    etiqueta: "Existencia (elemento 2)",
    ayuda: "201 · a qué cuenta entra al almacén",
  },
  {
    rol: "variacion_existencia",
    etiqueta: "Variación de existencia",
    ayuda: "611 · la contrapartida del ingreso al almacén",
  },
  {
    rol: "servicio",
    etiqueta: "Servicio (elemento 63)",
    ayuda:
      "6399 · si el artículo es un servicio, reemplaza a la cuenta de compra y no se escribe el ingreso al almacén",
  },
  {
    rol: "ingreso",
    etiqueta: "Venta (elemento 7)",
    ayuda: "7011 · qué cuenta acredita lo vendido",
  },
  { rol: "merma", etiqueta: "Merma y faltante", ayuda: "6599" },
  { rol: "consumo_personal", etiqueta: "Consumo del personal", ayuda: "625" },
];

/** Solo las claves, para armar y leer el formulario. */
export const CLAVES_ROL = ROLES_CONTABLES.map((r) => r.rol);
