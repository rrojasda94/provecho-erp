import Link from "next/link";

import type { Modulo } from "@/lib/modulos";
import { puedeVerModulo } from "@/lib/permisos";
import { obtenerSesion } from "@/lib/sesion";

type ItemSubmenu = { label: string; href: string };

/** Nivel 2 del shell Odoo (F2.6b): sidebar del módulo activo + guard real
 * server-side. Cada `[modulo]/layout.tsx` es un archivo real (Next.js lo
 * exige por ruta) pero delega todo el cuerpo acá — nada de sidebar
 * reinventado por módulo. Sin resaltado del ítem activo todavía: exigiría
 * un wrapper cliente solo para leer el pathname, y ningún módulo tiene más
 * de un ítem de submenú aún — se agrega cuando el segundo lo justifique. */
export async function ModuloShell({
  modulo,
  submenu,
  children,
}: {
  modulo: Modulo;
  submenu?: ItemSubmenu[];
  children: React.ReactNode;
}) {
  const { usuario } = await obtenerSesion();

  if (!puedeVerModulo(usuario.permisos, modulo)) {
    return (
      <main className="mx-auto max-w-md px-6 py-16 text-center">
        <p className="font-heading text-lg italic uppercase text-secondary">Sin permiso</p>
        <p className="mt-2 text-gray">
          Tu usuario no tiene acceso a {modulo.nombre}. Pídelo a Gerencia si lo necesitas.
        </p>
        <Link href="/" className="mt-4 inline-block font-semibold text-primary hover:underline">
          ← Volver al inicio
        </Link>
      </main>
    );
  }

  return (
    <div className="flex min-h-[calc(100vh-56px)]">
      <aside className="w-56 shrink-0 border-r border-gray/20 bg-white px-4 py-6">
        <Link href="/" className="mb-6 block text-sm text-gray hover:text-primary">
          ← Inicio
        </Link>
        <h2 className="mb-3 font-heading text-lg italic uppercase text-dark">
          {modulo.icono} {modulo.nombre}
        </h2>
        {submenu && submenu.length > 0 && (
          <nav className="flex flex-col gap-1">
            {submenu.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="rounded px-3 py-2 text-sm font-semibold text-dark hover:bg-cream"
              >
                {item.label}
              </Link>
            ))}
          </nav>
        )}
      </aside>
      <div className="flex-1 overflow-x-auto p-6">{children}</div>
    </div>
  );
}
