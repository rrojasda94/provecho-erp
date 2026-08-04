import { ModuloShell } from "@/components/shell/modulo-shell";
import { MODULOS } from "@/lib/modulos";

const modulo = MODULOS.find((m) => m.clave === "contabilidad")!;
const submenu = [
  { label: "Asientos", href: "/contabilidad" },
  { label: "Periodos", href: "/contabilidad/periodos" },
  { label: "Plan de cuentas", href: "/contabilidad/plan-cuentas" },
  { label: "Pagos a proveedor", href: "/contabilidad/pagos" },
  { label: "Caja", href: "/contabilidad/caja" },
];

export default function ContabilidadLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuloShell modulo={modulo} submenu={submenu}>
      {children}
    </ModuloShell>
  );
}
