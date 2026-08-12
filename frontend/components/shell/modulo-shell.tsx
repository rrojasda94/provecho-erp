import { ChevronLeft } from "lucide-react";
import Link from "next/link";

import { NavModulo } from "@/components/shell/nav-modulo";
import type { Modulo } from "@/lib/modulos";
import { puedeVerModulo } from "@/lib/permisos";
import { obtenerSesion } from "@/lib/sesion";

type ItemSubmenu = { label: string; href: string };

/** Nivel 2 del shell Odoo (F2.6b): sidebar del módulo activo + guard real
 * server-side. Cada `[modulo]/layout.tsx` es un archivo real (Next.js lo
 * exige por ruta) pero delega todo el cuerpo acá — nada de sidebar
 * reinventado por módulo.
 *
 * El único acento en reposo es el ítem activo del submenú (`NavModulo`): es
 * la pregunta que la pantalla tiene que responder sin que nadie la lea
 * —dónde estoy—. El resto del sidebar es neutro (ADR-013 §8). */
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
  const { Icono } = modulo;

  if (!puedeVerModulo(usuario.permisos, modulo)) {
    return (
      <main className="mx-auto max-w-md px-6 py-16 text-center">
        <p className="text-lg font-semibold text-secondary">Sin permiso</p>
        <p className="mt-2 text-gray">
          Tu usuario no tiene acceso a {modulo.nombre}. Pídelo a Gerencia si lo necesitas.
        </p>
        <Link
          href="/"
          className="mt-4 inline-flex items-center gap-1 font-medium text-primary hover:underline"
        >
          <ChevronLeft size={16} strokeWidth={2} aria-hidden />
          Volver al inicio
        </Link>
      </main>
    );
  }

  return (
    <div className="flex h-full flex-col md:flex-row">
      {/* En pantalla ancha: columna fija y `sticky` con la altura de la barra
          descontada, para que el submenú acompañe las tablas largas en vez de
          quedarse arriba del todo.

          En móvil se convierte en banda superior. Antes era una columna de
          224 px inamovible: en un teléfono dejaba 150 px para la tabla, que
          es no mostrar nada. */}
      <aside className="w-full shrink-0 border-b border-border bg-card px-3 py-4 md:sticky md:top-14 md:h-[calc(100vh-3.5rem)] md:w-56 md:overflow-y-auto md:border-r md:border-b-0 md:py-5">
        <Link
          href="/"
          className="mb-4 inline-flex items-center gap-1 px-2 text-sm text-gray transition-colors hover:text-dark md:mb-5"
        >
          <ChevronLeft size={15} strokeWidth={1.75} aria-hidden />
          Inicio
        </Link>

        <div className="mb-3 flex items-center gap-2.5 px-2 md:mb-4">
          <span className="ficha-chip size-8">
            <Icono size={16} strokeWidth={1.75} aria-hidden />
          </span>
          <h2 className="text-base leading-tight">{modulo.nombre}</h2>
        </div>

        {submenu && submenu.length > 0 && (
          <nav className="flex gap-0.5 overflow-x-auto md:flex-col md:overflow-visible">
            {submenu.map((item) => (
              <NavModulo key={item.href} href={item.href} label={item.label} />
            ))}
          </nav>
        )}
      </aside>

      <div className="min-w-0 flex-1 overflow-x-auto p-4 md:p-6">{children}</div>
    </div>
  );
}
