import { ModuloShell } from "@/components/shell/modulo-shell";
import { MODULOS } from "@/lib/modulos";

const modulo = MODULOS.find((m) => m.clave === "inventario")!;
const submenu = [
  { label: "Artículos", href: "/inventario/articulos" },
  { label: "Categorías", href: "/inventario/categorias" },
  { label: "Unidades de medida", href: "/inventario/unidades-medida" },
];

export default function InventarioLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuloShell modulo={modulo} submenu={submenu}>
      {children}
    </ModuloShell>
  );
}
