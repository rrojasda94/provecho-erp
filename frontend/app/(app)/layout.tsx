import { TopBar } from "@/components/shell/top-bar";
import { obtenerSesion } from "@/lib/sesion";

/** Nivel 1 del shell Odoo (F2.6, ADR-013): guard de sesión + barra superior,
 * comunes a toda pantalla autenticada. El sidebar por módulo va un nivel
 * más adentro (`[modulo]/layout.tsx`, vía `ModuloShell`) — el home de apps
 * (`page.tsx` de esta misma carpeta) no lleva sidebar. */
export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const { usuario } = await obtenerSesion();

  return (
    <div className="min-h-screen bg-background">
      <TopBar username={usuario.username} />
      {children}
    </div>
  );
}
