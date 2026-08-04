import { ModuloShell } from "@/components/shell/modulo-shell";
import { MODULOS } from "@/lib/modulos";

const modulo = MODULOS.find((m) => m.clave === "gerencia")!;
const submenu = [
  { label: "Parámetros", href: "/gerencia/parametros" },
  { label: "Decisiones", href: "/gerencia/decisiones" },
  { label: "Divisas", href: "/gerencia/divisas" },
];

export default function GerenciaLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuloShell modulo={modulo} submenu={submenu}>
      {children}
    </ModuloShell>
  );
}
