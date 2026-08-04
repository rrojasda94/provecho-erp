import Link from "next/link";

import { MODULOS } from "@/lib/modulos";
import { puedeVerModulo } from "@/lib/permisos";
import { obtenerSesion } from "@/lib/sesion";

/** Home de apps (F2.6a, ADR-013): grilla de módulos filtrada por permiso —
 * filtro de UX, no de seguridad (el guard real vive en cada
 * `[modulo]/layout.tsx`). `admin` (comodín `*`) ve todo el catálogo. */
export default async function HomePage() {
  const { usuario } = await obtenerSesion();
  const visibles = MODULOS.filter((m) => puedeVerModulo(usuario.permisos, m));

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="mb-1 font-heading text-2xl italic uppercase text-primary">
        Hola, {usuario.username}
      </h1>
      <p className="mb-8 text-gray">Elige un módulo para empezar.</p>

      {visibles.length === 0 ? (
        <p className="text-gray">Tu usuario no tiene acceso a ningún módulo todavía.</p>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {visibles.map((modulo) => (
            <Link
              key={modulo.clave}
              href={modulo.href}
              className="group flex flex-col gap-2 rounded-lg border border-gray/30 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-primary hover:shadow-md"
            >
              <span className="text-3xl">{modulo.icono}</span>
              <span className="font-heading text-base italic uppercase text-dark group-hover:text-primary">
                {modulo.nombre}
              </span>
              <span className="text-sm text-gray">{modulo.descripcion}</span>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
