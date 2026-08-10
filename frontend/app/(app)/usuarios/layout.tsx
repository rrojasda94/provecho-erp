import { ModuloShell } from "@/components/shell/modulo-shell";
import { MODULOS } from "@/lib/modulos";

const modulo = MODULOS.find((m) => m.clave === "usuarios")!;
const submenu = [
  { label: "Cuentas", href: "/usuarios" },
  { label: "Roles", href: "/usuarios/roles" },
  // Personas vive acá y no en RRHH porque no es solo el legajo: es la ficha
  // única que comparten trabajador, proveedor natural y cliente (RN-GEN-007),
  // y su backend es `users`.
  { label: "Personas", href: "/usuarios/personas" },
];

export default function UsuariosLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuloShell modulo={modulo} submenu={submenu}>
      {children}
    </ModuloShell>
  );
}
