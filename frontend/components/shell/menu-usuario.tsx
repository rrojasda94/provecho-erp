"use client";

import { Check, Contrast, LogOut, Moon, Sun, Type } from "lucide-react";
import { useTransition } from "react";

import { guardarPreferenciaAction, logoutAction } from "@/app/(app)/actions";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { Paleta, TamanoFuente, Tema } from "@/lib/sesion";

const TAMANOS: { valor: TamanoFuente; etiqueta: string }[] = [
  { valor: "estandar", etiqueta: "Estándar" },
  { valor: "grande", etiqueta: "Grande" },
  { valor: "muy_grande", etiqueta: "Muy grande" },
  { valor: "maximo", etiqueta: "Máximo" },
];

/**
 * Menú de la sesión: quién está conectado, cómo quiere ver el ERP y cómo se
 * sale. Antes eran tres elementos sueltos en la barra —monograma, nombre y un
 * botón de cerrar sesión que competía en peso con el logotipo.
 *
 * Las tres preferencias se guardan en el perfil y no en el navegador, así que
 * cada cambio es un viaje al servidor. Se aceptó ese costo: son acciones que
 * una persona hace una vez y espera encontrar igual en la tablet del almacén.
 * `useTransition` deja el menú utilizable mientras tanto.
 */
export function MenuUsuario({
  username,
  tema,
  tamano,
  paleta,
}: {
  username: string;
  tema: Tema;
  tamano: TamanoFuente;
  paleta: Paleta;
}) {
  const [pendiente, iniciar] = useTransition();
  const oscuro = tema === "oscuro";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <button
            type="button"
            aria-label={`Sesión de ${username}`}
            className="flex items-center gap-2 rounded-md py-1 pr-1.5 pl-1 transition-colors hover:bg-muted"
          />
        }
      >
        <span
          aria-hidden
          className="grid size-7 place-items-center rounded-full bg-muted text-xs font-semibold text-muted-foreground uppercase"
        >
          {username.slice(0, 2)}
        </span>
        <span className="hidden text-sm font-medium sm:inline">{username}</span>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-56" data-pendiente={pendiente || undefined}>
        {/* `DropdownMenuLabel` exige vivir dentro de un `Group`: Base UI lo
            asocia al grupo por `aria-labelledby`, y suelto lanza en runtime. */}
        <DropdownMenuGroup>
          <DropdownMenuLabel className="text-muted-foreground">Presentación</DropdownMenuLabel>

          <DropdownMenuItem
            closeOnClick={false}
            onClick={() =>
              iniciar(() => guardarPreferenciaAction({ tema: oscuro ? "claro" : "oscuro" }))
            }
          >
            {oscuro ? <Sun aria-hidden /> : <Moon aria-hidden />}
            {oscuro ? "Modo claro" : "Modo oscuro"}
          </DropdownMenuItem>

          {/* Alto contraste no es un tema alternativo: cambia solo los colores
              de estado (stock, caja, comprobantes) por la paleta que distingue
              quien no separa rojo de verde. La marca no se toca. */}
          <DropdownMenuItem
            closeOnClick={false}
            onClick={() =>
              iniciar(() =>
                guardarPreferenciaAction({
                  paleta: paleta === "alto_contraste" ? "estandar" : "alto_contraste",
                }),
              )
            }
          >
            <Contrast aria-hidden />
            Alto contraste
            {paleta === "alto_contraste" && <Check aria-hidden className="ml-auto" />}
          </DropdownMenuItem>
        </DropdownMenuGroup>

        <DropdownMenuSeparator />

        <DropdownMenuGroup>
          <DropdownMenuLabel className="flex items-center gap-1.5 text-muted-foreground">
            <Type size={13} aria-hidden />
            Tamaño de letra
          </DropdownMenuLabel>

          {TAMANOS.map(({ valor, etiqueta }) => (
            <DropdownMenuItem
              key={valor}
              closeOnClick={false}
              onClick={() => iniciar(() => guardarPreferenciaAction({ tamano_fuente: valor }))}
            >
              {etiqueta}
              {tamano === valor && <Check aria-hidden className="ml-auto" />}
            </DropdownMenuItem>
          ))}
        </DropdownMenuGroup>

        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => logoutAction()}>
          <LogOut aria-hidden />
          Cerrar sesión
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
