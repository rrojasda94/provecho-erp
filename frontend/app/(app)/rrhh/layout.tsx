import { ModuloShell } from "@/components/shell/modulo-shell";
import { MODULOS } from "@/lib/modulos";

const modulo = MODULOS.find((m) => m.clave === "rrhh")!;
const submenu = [{ label: "Trabajadores", href: "/rrhh/trabajadores" }];

export default function RrhhLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuloShell modulo={modulo} submenu={submenu}>
      {children}
    </ModuloShell>
  );
}
