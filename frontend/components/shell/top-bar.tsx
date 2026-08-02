import Link from "next/link";

import { logoutAction } from "@/app/(app)/actions";

/** Barra superior del shell (F2.6): siempre visible, home de apps a un
 * click, usuario + logout en un solo lugar — antes cada pantalla repetía su
 * propio botón de salir. */
export function TopBar({ username }: { username: string }) {
  return (
    <header className="flex items-center justify-between border-b-2 border-dark bg-white px-6 py-3">
      <Link href="/" className="font-heading text-xl italic uppercase text-primary">
        Provecho
      </Link>
      <div className="flex items-center gap-4">
        <span className="text-sm font-semibold text-gray">{username}</span>
        <form action={logoutAction}>
          <button
            type="submit"
            className="rounded border border-gray px-3 py-1.5 text-sm font-semibold text-dark hover:border-dark"
          >
            Cerrar sesión
          </button>
        </form>
      </div>
    </header>
  );
}
