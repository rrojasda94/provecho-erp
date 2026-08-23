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
  almacen_id: string | null;
  codigo_emision: string;
  titulo: string;
  cuerpo: string | null;
  nivel: string;
  referencia_tipo: string | null;
  referencia_id: string | null;
  emitido_at: string;
  actor_id: string | null;
  /** Nombre de quien provocó el hecho, o "Sistema" si lo detectó un barrido. */
  actor: string;
  /** Endpoint donde se mira el hecho. Nulo si no apunta a ninguna entidad. */
  referencia_url: string | null;
};

export type EntregaReporte = {
  usuario_id: string;
  usuario: string;
  /** `area:<id>`, `rol:<id>`, `usuario`, `dinamico:<nombre>`. */
  motivo: string;
  canal: string;
};

export type ReporteEmitidoDetalle = ReporteEmitido & {
  datos: Record<string, unknown>;
  regla_id: string | null;
  entregas: EntregaReporte[];
};

/** A dónde lleva un `referencia_tipo` y con qué permiso (ADR-036). */
export type Destino = { ruta: string; permiso: string; etiqueta: string };

export type CatalogoEmisiones = {
  emisiones: Emision[];
  niveles: string[];
  dinamicos: string[];
  destinos: Record<string, Destino>;
};

export type AccionEscalamiento = {
  nivel: string;
  usuario_id: string;
  accion: string;
  descripcion: string;
  ts: string;
};

export type Escalamiento = {
  id: string;
  empresa_id: string;
  sucursal_id: string | null;
  reporte_emitido_id: string;
  origen: string;
  motivo: string;
  descripcion: string;
  reportado_por_id: string;
  evidencia_id: string | null;
  nivel_actual: string;
  estado: string;
  cerrado_at: string | null;
  created_at: string;
  acciones?: AccionEscalamiento[];
  /** A quién le llega en el nivel actual. Vacío = no llega a nadie, y hay
   * que verlo (RN-REP-005). */
  destinatarios?: string[];
};

export const MOTIVOS_ESCALAMIENTO = [
  "queja",
  "demora",
  "error_sistema",
  "desistimiento_no_resuelto",
  "no_conformidad_calidad",
] as const;

export const ETIQUETA_MOTIVO: Record<string, string> = {
  queja: "Queja",
  demora: "Demora",
  error_sistema: "Error del sistema",
  desistimiento_no_resuelto: "Desistimiento no resuelto",
  no_conformidad_calidad: "No conformidad de calidad",
};

export const ETIQUETA_NIVEL: Record<string, string> = {
  supervisor: "Supervisor",
  comercial: "Comercial",
  gerencia: "Gerencia",
};

export const ETIQUETA_ESTADO: Record<string, string> = {
  abierto: "Abierto",
  resuelto_supervisor: "Resuelto por el supervisor",
  escalado: "Escalado",
  resuelto: "Resuelto",
  cerrado: "Cerrado",
};

/** Los tres estados que ya terminaron: ni se elevan ni admiten acciones. */
export const ESTADOS_TERMINADOS = ["resuelto_supervisor", "resuelto", "cerrado"];

export function terminado(estado: string): boolean {
  return ESTADOS_TERMINADOS.includes(estado);
}

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
