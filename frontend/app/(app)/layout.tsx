import { Revelar } from "@/components/shell/revelar";
import { TopBar } from "@/components/shell/top-bar";
import { obtenerSesion } from "@/lib/sesion";

/** Nivel 1 del shell Odoo (F2.6, ADR-013): guard de sesión + barra superior,
 * comunes a toda pantalla autenticada. El sidebar por módulo va un nivel
 * más adentro (`[modulo]/layout.tsx`, vía `ModuloShell`) — el home de apps
 * (`page.tsx` de esta misma carpeta) no lleva sidebar. */
export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const { usuario } = await obtenerSesion();

  return (
    // `erp`: raíz del back office. La usa `globals.css` para vestir los
    // `<dialog>` y campos nativos que trece pantallas todavía escriben a mano,
    // sin que esos estilos alcancen al PDV, al KDS ni al lienzo — que viven
    // fuera de este layout y tienen su propia paleta oscura.
    <div className="erp flex min-h-screen flex-col bg-background">
      <TopBar usuario={usuario} />
      {/* flex-1, no un cálculo con la altura de TopBar en píxeles: el alto
          real de la barra (fuentes custom, line-height) no es una constante
          que valga la pena asumir. */}
      <div className="flex-1">
        <Revelar>{children}</Revelar>
      </div>
    </div>
  );
}
