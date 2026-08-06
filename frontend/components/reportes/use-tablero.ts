"use client";

import { useState } from "react";

import {
  borrarTablero,
  conUid,
  FILTROS_INICIALES,
  guardarTablero,
  reordenar,
  sinUid,
  type Filtros,
  type Tablero as TableroGuardado,
  type Tarjeta,
  type TarjetaViva,
} from "@/lib/reportes";

/**
 * Estado del tablero: qué tarjetas se ven, con qué filtros, y la
 * persistencia contra la API.
 *
 * Vive aparte del componente porque mezclarlo con el JSX empujaba a
 * `Tablero` sobre el límite de complejidad del lint — que en este caso
 * señalaba algo real: renderizar y administrar el ciclo de vida de un
 * recurso son dos responsabilidades.
 *
 * Único nombre en inglés del módulo: React exige que un hook empiece con
 * `use` (así lo detectan el linter de reglas de hooks y las devtools), no
 * es una preferencia de estilo que se pueda traducir.
 */
export function useTablero(iniciales: TableroGuardado[]) {
  const inicial = iniciales.find((t) => t.predeterminado) ?? iniciales[0] ?? null;

  const [guardados, setGuardados] = useState(iniciales);
  const [actual, setActual] = useState<TableroGuardado | null>(inicial);
  const [tarjetas, setTarjetas] = useState<TarjetaViva[]>(
    conUid(inicial?.tarjetas ?? []),
  );
  const [filtros, setFiltros] = useState<Filtros>(inicial?.filtros ?? FILTROS_INICIALES);
  const [rolId, setRolId] = useState<string | null>(inicial?.rol_id ?? null);
  const [aviso, setAviso] = useState<string | null>(null);

  function cargar(tablero: TableroGuardado | null) {
    setActual(tablero);
    setTarjetas(conUid(tablero?.tarjetas ?? []));
    setFiltros(tablero?.filtros ?? FILTROS_INICIALES);
    setRolId(tablero?.rol_id ?? null);
  }

  function seleccionar(id: string) {
    const elegido = guardados.find((t) => t.id === id);
    if (elegido) cargar(elegido);
  }

  function cambiarTarjeta(uid: string, cambios: Partial<Tarjeta>) {
    setTarjetas((ts) => ts.map((t) => (t.uid === uid ? { ...t, ...cambios } : t)));
  }

  function agregarTarjeta(tarjeta: Tarjeta) {
    setTarjetas((ts) => [...ts, { ...tarjeta, uid: crypto.randomUUID() }]);
  }

  function quitarTarjeta(uid: string) {
    setTarjetas((ts) => ts.filter((t) => t.uid !== uid));
  }

  function moverTarjeta(desdeUid: string, hastaUid: string) {
    setTarjetas((ts) =>
      reordenar(
        ts,
        ts.findIndex((t) => t.uid === desdeUid),
        ts.findIndex((t) => t.uid === hastaUid),
      ),
    );
  }

  async function guardar(nombre: string, comoNuevo: boolean) {
    try {
      const salvado = await guardarTablero(
        {
          nombre,
          // El primero que se guarda es el que abre el dashboard.
          predeterminado: actual?.predeterminado ?? guardados.length === 0,
          tarjetas: sinUid(tarjetas),
          filtros,
          rol_id: rolId,
        },
        comoNuevo ? undefined : actual?.id,
      );
      setGuardados((gs) => [...gs.filter((g) => g.id !== salvado.id), salvado]);
      setActual(salvado);
      setAviso(
        salvado.rol_id ? "Tablero guardado y compartido." : "Tablero guardado.",
      );
      return true;
    } catch {
      setAviso("No se pudo guardar el tablero.");
      return false;
    }
  }

  async function eliminar() {
    if (!actual) return;
    try {
      await borrarTablero(actual.id);
      const resto = guardados.filter((g) => g.id !== actual.id);
      setGuardados(resto);
      cargar(resto[0] ?? null);
      setAviso("Tablero eliminado.");
    } catch {
      setAviso("No se pudo eliminar el tablero.");
    }
  }

  return {
    guardados,
    actual,
    tarjetas,
    filtros,
    rolId,
    aviso,
    setFiltros,
    setRolId,
    seleccionar,
    cambiarTarjeta,
    agregarTarjeta,
    quitarTarjeta,
    moverTarjeta,
    guardar,
    eliminar,
  };
}
