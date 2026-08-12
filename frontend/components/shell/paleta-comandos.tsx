"use client";

import { Autocomplete } from "@base-ui/react/autocomplete";
import { Dialog } from "@base-ui/react/dialog";
import { Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { MODULOS } from "@/lib/modulos";
import type { Destino } from "@/lib/navegacion";

const ICONOS = Object.fromEntries(MODULOS.map((m) => [m.clave, m.Icono]));

/**
 * Paleta de comandos: `Ctrl+K` (`⌘K` en Mac) abre el buscador de pantallas.
 *
 * Es la pieza que cambia cómo se siente el ERP. Llegar a «Plan de cuentas»
 * eran tres clics —inicio, Contabilidad, Plan de cuentas— y ahora son cinco
 * teclas; en una jornada de ocho horas saltando entre módulos, esa es la
 * diferencia entre una herramienta y un sitio web. Cierra F2.29, que estaba
 * sin decidir.
 *
 * Construida sobre `@base-ui/react` Autocomplete + Dialog, ya instalados. La
 * alternativa habitual (`cmdk`) trae su propio motor de coincidencia difusa
 * para un conjunto de ~50 entradas estáticas, y arrastra el árbol de Radix
 * que ADR-013 descartó explícitamente.
 *
 * El placeholder es la frase de campaña de la marca. Es el único lugar del
 * back office donde aparece: en el login se presenta el producto, acá se
 * pregunta a dónde vas.
 */
export function PaletaComandos({ destinos }: { destinos: Destino[] }) {
  const [abierta, setAbierta] = useState(false);

  useEffect(() => {
    function alTeclear(e: KeyboardEvent) {
      if (e.key !== "k" || !(e.metaKey || e.ctrlKey)) return;
      e.preventDefault();
      setAbierta((v) => !v);
    }
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, []);

  return (
    <>
      <button
        type="button"
        onClick={() => setAbierta(true)}
        className="flex items-center gap-2 rounded-lg border border-border px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        <Search size={14} strokeWidth={2} aria-hidden />
        <span className="hidden lg:inline">Buscar pantalla</span>
        {/* `hidden` en táctil: una tablet no tiene Ctrl que mostrar. */}
        <kbd className="hidden rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[0.6875rem] lg:inline">
          Ctrl K
        </kbd>
      </button>

      <Dialog.Root open={abierta} onOpenChange={setAbierta}>
        <Dialog.Portal>
          <Dialog.Backdrop className="fixed inset-0 z-50 bg-dark/40 backdrop-blur-[2px] data-[ending-style]:opacity-0 data-[starting-style]:opacity-0 [transition:opacity_160ms]" />
          <Dialog.Popup className="fixed top-[18vh] left-1/2 z-50 w-[min(32rem,calc(100vw-2rem))] -translate-x-1/2 overflow-hidden rounded-xl border border-border bg-popover text-popover-foreground shadow-[var(--sombra-3)] data-[ending-style]:scale-98 data-[ending-style]:opacity-0 data-[starting-style]:scale-98 data-[starting-style]:opacity-0 [transition:opacity_180ms,scale_180ms]">
            <Dialog.Title className="sr-only">Buscar pantalla</Dialog.Title>

            {/* `Autocomplete` filtra; no selecciona. Para una paleta eso es
                lo correcto: cada resultado es un enlace de verdad, así que
                Enter, clic, clic central y «abrir en pestaña nueva» funcionan
                sin que haya que programarlos. */}
            <Autocomplete.Root
              items={destinos}
              itemToStringValue={(d: Destino) => `${d.titulo} ${d.modulo}`}
              autoHighlight
            >
              <div className="flex items-center gap-2 border-b border-border px-3.5">
                <Search size={15} strokeWidth={2} aria-hidden className="text-muted-foreground" />
                <Autocomplete.Input
                  autoFocus
                  placeholder="¿Qué se te antoja hoy?"
                  aria-label="Buscar pantalla del ERP"
                  className="w-full bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground"
                />
              </div>

              <Autocomplete.List className="max-h-72 overflow-y-auto p-1.5">
                <Autocomplete.Empty className="px-3 py-6 text-center text-sm text-muted-foreground">
                  Ninguna pantalla coincide.
                </Autocomplete.Empty>
                <Autocomplete.Collection>
                  {(destino: Destino) => {
                    const Icono = ICONOS[destino.clave];
                    return (
                      <Autocomplete.Item
                        key={destino.href}
                        value={destino}
                        render={<Link href={destino.href} onClick={() => setAbierta(false)} />}
                        className="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm data-highlighted:bg-muted"
                      >
                        <Icono
                          size={15}
                          strokeWidth={1.75}
                          aria-hidden
                          className="text-muted-foreground"
                        />
                        <span className="font-medium">{destino.titulo}</span>
                        {/* El módulo desambigua: hay "Clientes" en Ventas y
                          campañas con clientes en Marketing. */}
                        <span className="ml-auto text-xs text-muted-foreground">
                          {destino.modulo}
                        </span>
                      </Autocomplete.Item>
                    );
                  }}
                </Autocomplete.Collection>
              </Autocomplete.List>
            </Autocomplete.Root>
          </Dialog.Popup>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
