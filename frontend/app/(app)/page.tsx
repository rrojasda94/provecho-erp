import Link from "next/link";

import { AREAS, MODULOS } from "@/lib/modulos";
import { puedeVerModulo } from "@/lib/permisos";
import { obtenerSesion } from "@/lib/sesion";

/** Home de apps (F2.6a, ADR-013): módulos filtrados por permiso — filtro de
 * UX, no de seguridad (el guard real vive en cada `[modulo]/layout.tsx`).
 * `admin` (comodín `*`) ve todo el catálogo.
 *
 * Agrupado por área de negocio y no en una grilla plana de doce fichas: el
 * home deja de ser un cajón de aplicaciones y pasa a mostrar cómo está
 * dividida la operación. Un cajero ve dos áreas y entiende de inmediato cuál
 * es su parte; un gerente ve las cuatro en el mismo orden en que transcurre
 * el día. Un área sin módulos visibles no se dibuja. */
export default async function HomePage() {
  const { usuario } = await obtenerSesion();
  const visibles = MODULOS.filter((m) => puedeVerModulo(usuario.permisos, m));

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <header className="mb-9">
        <p className="rotulo">Provecho</p>
        <h1 className="mt-1 text-3xl">Hola, {usuario.username}</h1>
        <p className="mt-1 text-gray">Elige por dónde empezar.</p>
      </header>

      {visibles.length === 0 ? (
        <p className="rounded-lg border border-border bg-card p-6 text-gray">
          Tu usuario todavía no tiene acceso a ningún módulo. Pídelo a Gerencia.
        </p>
      ) : (
        <div className="flex flex-col gap-9">
          {AREAS.map((area) => {
            const modulos = visibles.filter((m) => m.area === area.clave);
            if (modulos.length === 0) return null;

            return (
              <section key={area.clave}>
                <div className="mb-3">
                  <h2 className="area-titulo rotulo">{area.nombre}</h2>
                  <p className="mt-1 text-sm text-gray">{area.resumen}</p>
                </div>

                <div className="revelar-lista grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                  {modulos.map(({ clave, nombre, descripcion, href, Icono }) => (
                    <Link key={clave} href={href} className="ficha">
                      <span className="ficha-chip">
                        <Icono size={18} strokeWidth={1.75} aria-hidden />
                      </span>
                      <span className="ficha-nombre">{nombre}</span>
                      <span className="text-sm leading-snug text-gray">{descripcion}</span>
                    </Link>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </main>
  );
}
