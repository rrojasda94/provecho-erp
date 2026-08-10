import { ModuloShell } from "@/components/shell/modulo-shell";
import { MODULOS } from "@/lib/modulos";

const modulo = MODULOS.find((m) => m.clave === "organizacion")!;
const submenu = [
  { label: "Empresas", href: "/organizacion/empresas" },
  { label: "Marcas", href: "/organizacion/marcas" },
  { label: "Sucursales", href: "/organizacion/sucursales" },
  { label: "Almacenes", href: "/organizacion/almacenes" },
];

export default function OrganizacionLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuloShell modulo={modulo} submenu={submenu}>
      {children}
    </ModuloShell>
  );
}
