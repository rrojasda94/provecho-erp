import { ModuloShell } from "@/components/shell/modulo-shell";
import { MODULOS } from "@/lib/modulos";

const modulo = MODULOS.find((m) => m.clave === "inventario")!;
const submenu = [
  { label: "Artículos", href: "/inventario/articulos" },
  { label: "Categorías", href: "/inventario/categorias" },
  { label: "Lotes", href: "/inventario/lotes" },
  { label: "Ajustes", href: "/inventario/ajustes" },
  { label: "Devoluciones", href: "/inventario/devoluciones" },
];

export default function InventarioLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuloShell modulo={modulo} submenu={submenu}>
      {children}
    </ModuloShell>
  );
}
