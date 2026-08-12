import { AlertTriangle, CheckCircle2, Circle, Info, XCircle, type LucideIcon } from "lucide-react";

/**
 * Insignia de estado: "activa", "cerrado", "descuadra", "pendiente".
 *
 * Existe por una regla de accesibilidad que un token de color no puede
 * imponer solo (docs/product/ui-ux.md): **ningún estado se comunica solo por
 * color**. El ERP tenía ~30 insignias escritas a mano como
 * `bg-accent/30 … text-dark` para lo bueno y `bg-gray/20 … text-gray` para lo
 * apagado — para quien no distingue rojo de verde, ambas son la misma píldora
 * gris.
 *
 * El ícono viaja atado al tono, no como prop opcional: si fuera opcional, la
 * pantalla número treinta y uno lo olvidaría y nadie lo notaría en la
 * revisión. Va `aria-hidden` porque el texto de la insignia ya dice lo mismo;
 * el ícono es redundancia visual, no información nueva.
 */
export type Tono = "exito" | "alerta" | "peligro" | "info" | "neutro";

const TONOS: Record<Tono, { Icono: LucideIcon; clase: string }> = {
  exito: {
    Icono: CheckCircle2,
    clase: "bg-status-success-surface text-status-success",
  },
  alerta: {
    Icono: AlertTriangle,
    clase: "bg-status-warning-surface text-status-warning",
  },
  peligro: {
    Icono: XCircle,
    clase: "bg-status-danger-surface text-status-danger",
  },
  info: {
    Icono: Info,
    clase: "bg-status-info-surface text-status-info",
  },
  neutro: {
    Icono: Circle,
    clase: "bg-muted text-muted-foreground",
  },
};

export function Insignia({ tono, children }: { tono: Tono; children: React.ReactNode }) {
  const { Icono, clase } = TONOS[tono];

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${clase}`}
    >
      <Icono size={12} strokeWidth={2.25} aria-hidden />
      {children}
    </span>
  );
}

/**
 * Atajo para el caso más repetido del ERP: una fila que está activa o no lo
 * está. Nueve pantallas escribían el mismo ternario de clases.
 */
export function InsigniaActiva({
  activa,
  si = "Activa",
  no = "Inactiva",
}: {
  activa: boolean;
  si?: string;
  no?: string;
}) {
  return <Insignia tono={activa ? "exito" : "neutro"}>{activa ? si : no}</Insignia>;
}
