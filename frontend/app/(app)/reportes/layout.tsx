import { ModuloShell } from "@/components/shell/modulo-shell";
import { MODULOS } from "@/lib/modulos";

const modulo = MODULOS.find((m) => m.clave === "reportes")!;
const submenu = [
  { label: "Mis reportes", href: "/reportes" },
  { label: "Distribución", href: "/reportes/distribucion" },
  { label: "Emitidos", href: "/reportes/emitidos" },
];

export default function ReportesLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuloShell modulo={modulo} submenu={submenu}>
      {children}
    </ModuloShell>
  );
}
