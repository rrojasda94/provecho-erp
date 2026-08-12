import { ModuloShell } from "@/components/shell/modulo-shell";
import { MODULOS } from "@/lib/modulos";

const modulo = MODULOS.find((m) => m.clave === "organizacion")!;

export default function OrganizacionLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuloShell modulo={modulo}>
      {children}
    </ModuloShell>
  );
}
