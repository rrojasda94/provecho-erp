"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { evaluar, formatear } from "@/lib/aritmetica";
import { catalogoApi, type Grilla } from "@/lib/catalogo";
import { ErrorApi } from "@/lib/cliente-api";
import {
  armar,
  cambios,
  clave,
  copiar,
  costo,
  escribir,
  haySinGuardar,
  leerPegado,
  pegar,
  type Celda,
  type InsumoFila,
  type Modelo,
} from "@/lib/matriz";

/**
 * El recetario como una hoja de cálculo (ADR-057).
 *
 * El editor de a una receta funciona y no alcanza: corregir el queso de las
 * tres presentaciones de ocho pizzas son veinticuatro fichas abiertas de a
 * una, y comparar dos recetas obliga a recordar la primera mientras se mira
 * la segunda.
 *
 * Tres decisiones que se notan al usarla:
 *
 * - **Se guarda por lote, con un botón.** Guardar en cada `onBlur` (como el
 *   editor de receta) sería una ida a la red por celda; en una grilla sería
 *   una por tabulación. Acá se edita todo y se manda lo que cambió.
 * - **Se puede pegar desde Excel.** Es el gesto que la gente ya tiene, y sin
 *   él la grilla es una tabla de inputs más.
 * - **La celda muestra lo tecleado, no el resultado.** Quien escribió
 *   "450/3" vuelve a ver la división; el número lo calcula el servidor
 *   (RN-COM-024) y la vista previa aparece debajo mientras se escribe.
 */
export function MatrizCliente({
  grilla,
  filtro,
}: {
  grilla: Grilla;
  filtro: string;
}) {
  const [modelo, setModelo] = useState<Modelo>(() => armar(grilla));
  const [guardando, setGuardando] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [foco, setFoco] = useState<{ fila: number; columna: number } | null>(
    null,
  );
  const sinGuardar = haySinGuardar(modelo);
  const pendientes = cambios(modelo).length;

  const alPegar = useCallback(
    (e: React.ClipboardEvent, fila: number, columna: number) => {
      const texto = e.clipboardData.getData("text/plain");
      // Un solo valor sin tabulador ni salto de línea es un pegado normal:
      // se deja al input, que ya sabe hacerlo.
      if (!texto.includes("\t") && !texto.includes("\n")) return;
      e.preventDefault();
      setModelo((m) => pegar(m, fila, columna, leerPegado(texto)));
    },
    [],
  );

  const guardar = async () => {
    const celdas = cambios(modelo);
    if (!celdas.length) return;
    setGuardando(true);
    setError(null);
    setAviso(null);
    try {
      const r = await catalogoApi.guardarMatriz(celdas);
      // Se relee del servidor en vez de marcar las celdas como limpias: el
      // redondeo por UdM se decide allá, y una grilla que muestra lo que el
      // navegador creyó guardar es la que después no cuadra con la ficha.
      setModelo(armar(await catalogoApi.matriz(filtro ? filtro.split(",") : undefined)));
      const problemas = r.resultados.filter((x) => x.accion === "problema");
      setAviso(
        `${r.aplicadas} celda(s) guardada(s)` +
          (r.con_problema ? `, ${r.con_problema} con problema` : ""),
      );
      if (problemas.length) {
        setError(problemas.map((p) => p.detalle).join(" · "));
      }
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo guardar.");
    } finally {
      setGuardando(false);
    }
  };

  const copiarTodo = async () => {
    await navigator.clipboard.writeText(copiar(modelo));
    setAviso("Copiado. Se puede pegar en Excel.");
  };

  const costos = useMemo(
    () =>
      Object.fromEntries(
        modelo.recetas.map((r) => [r.id, costo(modelo, r.id, evaluar)]),
      ),
    [modelo],
  );

  if (!modelo.recetas.length) {
    return (
      <div className="space-y-4">
        <Encabezado />
        <p className="text-secondary">
          No hay recetas para mostrar.{" "}
          <Link className="underline" href="/catalogo/recetas">
            Crear la primera
          </Link>
          .
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Encabezado />
      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={guardar} disabled={!sinGuardar || guardando}>
          {guardando
            ? "Guardando…"
            : sinGuardar
              ? `Guardar ${pendientes} cambio(s)`
              : "Sin cambios"}
        </Button>
        <Button variant="outline" onClick={copiarTodo}>
          Copiar a Excel
        </Button>
        <Link
          className="text-sm underline text-secondary"
          href="/catalogo/recetas"
        >
          Volver al listado
        </Link>
      </div>

      {aviso && (
        <p className="text-sm text-secondary" role="status">
          {aviso}
        </p>
      )}
      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}

      <div className="overflow-x-auto rounded-md border">
        <table className="w-full text-sm">
          <caption className="sr-only">
            Recetas en las columnas, insumos en las filas. Cada celda es la
            cantidad de ese insumo en esa receta; acepta operaciones como
            1000/3.
          </caption>
          <thead>
            <tr className="border-b bg-muted/40">
              <th scope="col" className="sticky left-0 z-10 bg-muted/40 p-2 text-left">
                Insumo
              </th>
              {modelo.recetas.map((r) => (
                <th key={r.id} scope="col" className="p-2 text-left font-medium">
                  <Link className="underline" href={`/catalogo/recetas/${r.id}`}>
                    {r.nombre}
                  </Link>
                  {r.es_kit && (
                    <span className="ml-1 text-xs text-secondary">(kit)</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {modelo.insumos.map((insumo, fila) => (
              <tr key={insumo.articulo_id} className="border-b last:border-0">
                <th
                  scope="row"
                  className="sticky left-0 z-10 bg-background p-2 text-left font-normal"
                >
                  {insumo.nombre}{" "}
                  <span className="text-xs text-secondary">{insumo.unidad}</span>
                </th>
                {modelo.recetas.map((receta, columna) => (
                  <CeldaEditable
                    key={receta.id}
                    celda={modelo.celdas.get(clave(receta.id, insumo.articulo_id))}
                    insumo={insumo}
                    nombreReceta={receta.nombre}
                    enfocada={foco?.fila === fila && foco?.columna === columna}
                    alEnfocar={() => setFoco({ fila, columna })}
                    alPegar={(e) => alPegar(e, fila, columna)}
                    alEscribir={(valor) =>
                      setModelo((m) => escribir(m, receta.id, insumo, valor))
                    }
                  />
                ))}
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t bg-muted/40">
              <th scope="row" className="sticky left-0 z-10 bg-muted/40 p-2 text-left">
                Costo
              </th>
              {modelo.recetas.map((r) => (
                <td key={r.id} className="p-2 tabular-nums">
                  S/ {costos[r.id].toFixed(2)}
                </td>
              ))}
            </tr>
          </tfoot>
        </table>
      </div>

      <p className="text-xs text-secondary">
        La cantidad acepta operaciones (<code>1000/3</code>) y la evalúa el
        servidor. Vaciar una celda quita el insumo de esa receta. Se puede
        pegar un rectángulo copiado de Excel.
      </p>
    </div>
  );
}

/**
 * Una celda de la grilla.
 *
 * Componente propio y no un `map` en el medio de la tabla: la celda es lo
 * único de esta pantalla con estado visible propio —lo tecleado, si está
 * sucia, la vista previa— y mezclarlo con el armado de filas hace una
 * función que nadie puede leer entera.
 */
function CeldaEditable({
  celda,
  insumo,
  nombreReceta,
  enfocada,
  alEnfocar,
  alPegar,
  alEscribir,
}: {
  celda: Celda | undefined;
  insumo: InsumoFila;
  nombreReceta: string;
  enfocada: boolean;
  alEnfocar: () => void;
  alPegar: (e: React.ClipboardEvent) => void;
  alEscribir: (valor: string) => void;
}) {
  const texto = celda?.texto ?? "";
  const previa = /[+\-*/()]/.test(texto) ? evaluar(texto) : null;
  return (
    <td className="p-1 align-top">
      <input
        className={
          "w-24 rounded border bg-transparent px-2 py-1 " +
          (celda?.sucia ? "border-primary" : "border-input")
        }
        // El nombre accesible sale de acá: en una grilla el input no tiene
        // etiqueta visible propia, y un lector de pantalla diría "campo de
        // texto" cuarenta veces seguidas.
        aria-label={`${insumo.nombre} en ${nombreReceta}`}
        inputMode="decimal"
        value={texto}
        onFocus={alEnfocar}
        onPaste={alPegar}
        onChange={(e) => alEscribir(e.target.value)}
      />
      {enfocada && previa !== null && (
        <p className="px-2 text-xs text-secondary">
          = {formatear(previa, celda?.decimales ?? insumo.decimales)}
        </p>
      )}
    </td>
  );
}

function Encabezado() {
  return (
    <div>
      <h1 className="text-xl font-semibold">Matriz de recetas</h1>
      <p className="text-sm text-secondary">
        Insumos en las filas, recetas en las columnas. Para corregir un gramaje
        en varias presentaciones sin abrir una ficha por cada una.
      </p>
    </div>
  );
}
