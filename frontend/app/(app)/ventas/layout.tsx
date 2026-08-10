import { ModuloShell } from "@/components/shell/modulo-shell";
import { MODULOS } from "@/lib/modulos";

const modulo = MODULOS.find((m) => m.clave === "ventas")!;
const submenu = [
  { label: "Jornada", href: "/ventas" },
  { label: "Clientes", href: "/ventas/clientes" },
  { label: "Abrir el PDV", href: "/pdv" },
];

export default function VentasLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuloShell modulo={modulo} submenu={submenu}>
      {children}
    </ModuloShell>
  );
}
