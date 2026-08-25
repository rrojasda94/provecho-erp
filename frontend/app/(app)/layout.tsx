import { redirect } from "next/navigation";

import { ProveedorConfigMapas } from "@/components/direccion/config-mapas";
import { RastreoDeNavegacion } from "@/components/shell/rastro";
import { Revelar } from "@/components/shell/revelar";
import { TopBar } from "@/components/shell/top-bar";
import { configMapas } from "@/lib/mapas";
import { obtenerSesion } from "@/lib/sesion";

/** Nivel 1 del shell Odoo (F2.6, ADR-013): guard de sesión + barra superior,
 * comunes a toda pantalla autenticada. El sidebar por módulo va un nivel
 * más adentro (`[modulo]/layout.tsx`, vía `ModuloShell`) — el home de apps
 * (`page.tsx` de esta misma carpeta) no lleva sidebar. */
export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const { usuario } = await obtenerSesion();

  // Con el PIN reseteado no hay nada que mostrar: el servidor le responde 403
  // a todo salvo cambiarlo, así que el shell dibujaría un ERP entero de
  // pantallas vacías. `/cambiar-pin` vive fuera de este layout justamente
  // para que este redirect no se llame a sí mismo.
  if (usuario.debe_cambiar_pin) redirect("/cambiar-pin");

  return (
    // `erp`: raíz del back office. La usa `globals.css` para vestir los
    // `<dialog>` y campos nativos que trece pantallas todavía escriben a mano,
    // sin que esos estilos alcancen al PDV ni al KDS — que viven fuera de
    // este layout y tienen su propia paleta oscura.
    <div className="erp flex min-h-screen flex-col bg-background">
      {/* Acá y no en cada ficha: cuenta las navegaciones del shell desde que
          se entra, que es lo que decide si el `←` puede volver o tiene que
          subir al padre. */}
      <RastreoDeNavegacion />
      <TopBar usuario={usuario} />
      {/* flex-1, no un cálculo con la altura de TopBar en píxeles: el alto
          real de la barra (fuentes custom, line-height) no es una constante
          que valga la pena asumir. */}
      <div className="flex-1">
        {/* La clave de Google Maps la lee el servidor y baja por contexto:
            declararla acá es lo que hace que un campo de dirección nuevo la
            encuentre solo, sin tocar su página ni su componente cliente. */}
        <ProveedorConfigMapas config={configMapas()}>
          <Revelar>{children}</Revelar>
        </ProveedorConfigMapas>
      </div>
    </div>
  );
}
