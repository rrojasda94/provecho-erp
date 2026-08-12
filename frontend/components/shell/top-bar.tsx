import { LogOut } from "lucide-react";
import Link from "next/link";

import { logoutAction } from "@/app/(app)/actions";
import { Campana } from "@/components/shell/campana";

/** Barra superior del shell (F2.6): siempre visible, home de apps a un
 * click, usuario + logout en un solo lugar — antes cada pantalla repetía su
 * propio botón de salir.
 *
 * `sticky`: las pantallas del ERP son tablas largas (movimientos de stock,
 * asientos, planilla). Perder la salida al inicio a los tres scrolls obligaba
 * a subir hasta arriba para cambiar de módulo.
 *
 * El borde inferior es una línea de 1px, no los 2px de tinta que tenía: a esa
 * altura la barra parecía el encabezado de un afiche. Lo que separa la barra
 * del contenido ahora es el cambio de superficie —blanco sobre acero—, que no
 * necesita subrayarse. */
export function TopBar({ username }: { username: string }) {
  return (
    <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-border bg-card px-4 md:px-6">
      <Link
        href="/"
        className="group flex items-center gap-2.5 transition-opacity hover:opacity-80"
      >
        {/* La brasa de la marca reducida a un cuadro de 8px. Es la única
            firma cromática de la barra; el resto es tinta sobre blanco. */}
        <span
          aria-hidden
          className="size-2 rounded-[2px] bg-primary transition-transform duration-200 group-hover:rotate-45"
        />
        <span className="logotipo text-lg leading-none">Provecho</span>
      </Link>

      <div className="flex items-center gap-3">
        <Campana />

        <span aria-hidden className="h-5 w-px bg-border" />

        <span className="flex items-center gap-2">
          {/* Monograma: identifica la sesión de un vistazo en un turno donde
              varias personas comparten la misma máquina. */}
          <span
            aria-hidden
            className="grid size-7 place-items-center rounded-full bg-muted text-xs font-semibold text-gray uppercase"
          >
            {username.slice(0, 2)}
          </span>
          {/* En móvil manda el monograma: el nombre completo empujaba el
              botón de cerrar sesión fuera de la barra. */}
          <span className="hidden text-sm font-medium text-dark sm:inline">{username}</span>
        </span>

        <form action={logoutAction}>
          <button
            type="submit"
            className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm font-medium text-gray transition-colors hover:bg-muted hover:text-dark"
          >
            <LogOut size={15} strokeWidth={1.75} aria-hidden />
            Cerrar sesión
          </button>
        </form>
      </div>
    </header>
  );
}
