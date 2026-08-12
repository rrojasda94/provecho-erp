import Link from "next/link";

import { Campana } from "@/components/shell/campana";
import { MenuUsuario } from "@/components/shell/menu-usuario";
import { PaletaComandos } from "@/components/shell/paleta-comandos";
import { destinos } from "@/lib/navegacion";
import type { Usuario } from "@/lib/sesion";

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
export function TopBar({ usuario }: { usuario: Usuario }) {
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
        {/* Los destinos se resuelven en el servidor y ya vienen filtrados por
            permiso: la paleta no puede ofrecer una pantalla a la que su
            usuario recibiría un 403. */}
        <PaletaComandos destinos={destinos(usuario.permisos)} />

        <Campana />

        <span aria-hidden className="h-5 w-px bg-border" />

        {/* Monograma, nombre, preferencias y salida en un solo control: eran
            tres elementos sueltos, y «Cerrar sesión» en texto competía en peso
            con el logotipo por algo que se usa una vez al día. */}
        <MenuUsuario
          username={usuario.username}
          tema={usuario.preferencia_tema}
          tamano={usuario.preferencia_tamano_fuente}
          paleta={usuario.preferencia_paleta}
        />
      </div>
    </header>
  );
}
