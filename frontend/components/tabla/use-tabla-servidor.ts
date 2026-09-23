"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { PaginationState, Updater } from "@tanstack/react-table";
import { useEffect, useRef, useState, useTransition } from "react";

/** La página que el servidor ya cortó, con lo que se pidió para cortarla. */
export type PaginaServidor = {
  total: number;
  page: number;
  pageSize: number;
  /** Lo buscado. `undefined` si el endpoint no busca: se oculta el buscador. */
  q?: string;
};

const RETRASO_MS = 300;

/**
 * El estado de una tabla paginada en el servidor vive en la URL (`?page`,
 * `?page_size`, `?q`): recargar, compartir el enlace o volver atrás deja la
 * tabla donde estaba, y el Server Component de la página vuelve a pedir.
 */
export function useTablaServidor(servidor: PaginaServidor | undefined) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [pendiente, startTransition] = useTransition();
  const [busqueda, setBusqueda] = useState(servidor?.q ?? "");
  const temporizador = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => () => clearTimeout(temporizador.current), []);

  const ir = (cambios: Record<string, string | null>) => {
    const nuevos = new URLSearchParams(params.toString());
    for (const [clave, valor] of Object.entries(cambios)) {
      if (valor) nuevos.set(clave, valor);
      else nuevos.delete(clave);
    }
    startTransition(() => router.replace(`${pathname}?${nuevos}`, { scroll: false }));
  };

  const buscar = (valor: string) => {
    setBusqueda(valor);
    clearTimeout(temporizador.current);
    // Buscar vuelve a la primera página: la 7 de otra búsqueda suele no existir.
    temporizador.current = setTimeout(() => ir({ q: valor.trim() || null, page: null }), RETRASO_MS);
  };

  const paginar = (pageIndex: number, pageSize: number) =>
    ir({
      page: pageIndex > 0 ? String(pageIndex + 1) : null,
      page_size: String(pageSize),
    });

  return { busqueda, buscar, paginar, pendiente };
}

/**
 * Filtro y paginación de la tabla, locales o contra el servidor. Una sola
 * forma para que `TablaDatos` no ramifique en cada opción.
 */
export function useFiltroTabla(servidor: PaginaServidor | undefined, cargando: boolean) {
  const [local, setLocal] = useState("");
  const remota = useTablaServidor(servidor);
  if (!servidor) {
    return {
      filtro: local,
      alFiltrar: setLocal,
      ocupado: cargando,
      total: undefined,
      sinBuscador: false,
      estado: {},
      opciones: {},
    };
  }
  const actual: PaginationState = { pageIndex: servidor.page - 1, pageSize: servidor.pageSize };
  return {
    filtro: remota.busqueda,
    alFiltrar: remota.buscar,
    ocupado: cargando || remota.pendiente,
    total: servidor.total,
    // Sin `q` el endpoint no busca: un buscador que filtra solo la página
    // visible mentiría sobre lo que hay.
    sinBuscador: servidor.q === undefined,
    estado: { pagination: actual },
    opciones: {
      manualPagination: true,
      manualFiltering: true,
      rowCount: servidor.total,
      onPaginationChange: (cambio: Updater<PaginationState>) => {
        const nueva = typeof cambio === "function" ? cambio(actual) : cambio;
        remota.paginar(nueva.pageIndex, nueva.pageSize);
      },
    },
  };
}
