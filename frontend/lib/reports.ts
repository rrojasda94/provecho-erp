/**
 * Tipos del módulo `reports` (ADR-033): emisión y distribución.
 *
 * No confundir con `lib/reportes.ts`, que es el motor de **consulta** del
 * dashboard (ADR-024). Acá se describe lo que el ERP emite solo cuando pasa
 * algo, y a quién le llega.
 */

export type Emision = {
  codigo: string;
  nombre: string;
  descripcion: string;
  permiso: string;
  nivel: string;
  ambito: string;
  campos: string[];
  areas_sugeridas: string[];
  dinamicos_sugeridos: string[];
  referencia_tipo: string;
};

export type MatrizDestinatario = {
  tipo: string;
  id: string | null;
  etiqueta: string;
};

export type MatrizRegla = {
  id: string;
  sucursal_id: string | null;
  sucursal: string;
  activa: boolean;
  nivel: string;
  canal: string;
  destinatarios: MatrizDestinatario[];
  /** Personas alcanzadas hoy, sin contar resolutores dinámicos. */
  alcance: number;
  /** Regla activa que no llega a nadie. */
  fuga: boolean;
};

export type MatrizFila = {
  codigo: string;
  nombre: string;
  descripcion: string;
  permiso: string;
  nivel: string;
  ambito: string;
  areas_sugeridas: string[];
  reglas: MatrizRegla[];
  /** El hecho ocurre y no se entera nadie. */
  hueco: boolean;
};

export type ReporteEmitido = {
  id: string;
  empresa_id: string | null;
  sucursal_id: string | null;
  codigo_emision: string;
  titulo: string;
  cuerpo: string | null;
  nivel: string;
  referencia_tipo: string | null;
  referencia_id: string | null;
  emitido_at: string;
};

export type Area = {
  id: string;
  empresa_id: string;
  codigo: string;
  nombre: string;
  activa: boolean;
};

/** Cuánto interrumpe, no qué tipo de hecho es. */
export const CLASE_NIVEL: Record<string, string> = {
  info: "bg-gray/15 text-secondary",
  aviso: "bg-amber-100 text-amber-900",
  urgente: "bg-red-100 text-red-900",
};

export function etiquetaAmbito(ambito: string): string {
  return { sucursal: "Sucursal", almacen: "Almacén", empresa: "Empresa" }[ambito] ?? ambito;
}
