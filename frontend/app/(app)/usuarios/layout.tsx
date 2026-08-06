import { ModuloShell } from "@/components/shell/modulo-shell";
import { MODULOS } from "@/lib/modulos";

const modulo = MODULOS.find((m) => m.clave === "usuarios")!;
const submenu = [
  { label: "Cuentas", href: "/usuarios" },
  { label: "Roles", href: "/usuarios/roles" },
];

export default function UsuariosLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuloShell modulo={modulo} submenu={submenu}>
      {children}
    </ModuloShell>
  );
}
