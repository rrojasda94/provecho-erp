import { ModuloShell } from "@/components/shell/modulo-shell";
import { MODULOS } from "@/lib/modulos";

const modulo = MODULOS.find((m) => m.clave === "marketing")!;
const submenu = [
  { label: "Campañas", href: "/marketing" },
  { label: "Contenido", href: "/marketing/contenido" },
];

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuloShell modulo={modulo} submenu={submenu}>
      {children}
    </ModuloShell>
  );
}
