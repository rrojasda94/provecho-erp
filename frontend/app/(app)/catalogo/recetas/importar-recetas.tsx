"use client";

import { useRef, useState } from "react";

import {
  catalogoApi,
  type Articulo,
  type RecetaRevisada,
  type RevisionImportacion,
  RUTA_PLANTILLA_RECETAS,
} from "@/lib/catalogo";
import { ErrorApi } from "@/lib/cliente-api";

/**
 * Carga masiva del recetario (RN-COM-031).
 *
 * El recorrido es: descargar plantilla → subirla → **revisar** → confirmar.
 * La revisión es el punto: el archivo casi nunca viene perfecto, y el modo
 * de falla que hay que evitar es el silencioso — importar la mitad y que
 * nadie se entere de la otra mitad.
 *
 * Por eso un insumo que el catálogo no reconoce no cancela nada: se resuelve
 * fila por fila eligiendo uno existente o creándolo acá mismo, y lo que se
 * deja sin resolver se omite **a la vista**, no en silencio.
 */

type Props = { onImportadas: () => void };

export function ImportarRecetas({ onImportadas }: Props) {
  const dialogo = useRef<HTMLDialogElement>(null);
  const [revision, setRevision] = useState<RevisionImportacion | null>(null);
  const [recetas, setRecetas] = useState<RecetaRevisada[]>([]);
  const [articulos, setArticulos] = useState<Articulo[]>([]);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [resultado, setResultado] = useState<string | null>(null);

  const abrir = () => {
    setRevision(null);
    setRecetas([]);
    setError("");
    setResultado(null);
    catalogoApi.articulos().then(setArticulos).catch(() => setArticulos([]));
    dialogo.current?.showModal();
  };

  async function revisar(archivo: File) {
    setError("");
    setOcupado(true);
    try {
      const datos = await catalogoApi.validarImportacion(archivo);
      setRevision(datos);
      setRecetas(datos.recetas);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo leer el archivo.");
    } finally {
      setOcupado(false);
    }
  }

  /** Resuelve un insumo en TODAS las filas que lo nombran: el mismo nombre
   * mal escrito suele repetirse en veinte recetas, y arreglarlo una por una
   * es lo que hace que nadie termine la importación. */
  const resolver = (insumo: string, articuloId: string) =>
    setRecetas((previas) =>
      previas.map((r) => ({
        ...r,
        ingredientes: r.ingredientes.map((i) =>
          i.insumo === insumo ? { ...i, articulo_id: articuloId || null } : i,
        ),
      })),
    );

  async function confirmar() {
    setError("");
    setOcupado(true);
    try {
      const { creadas, omitidas } = await catalogoApi.importarRecetas(
        recetas.filter((r) => r.unidad_medida_id),
      );
      setResultado(
        `${creadas.length} receta(s) importada(s)` +
          (omitidas.length ? `, ${omitidas.length} omitida(s).` : "."),
      );
      onImportadas();
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo importar.");
    } finally {
      setOcupado(false);
    }
  }

  const pendientes = sinResolver(recetas);
  const importables = recetas.filter((r) => r.unidad_medida_id && !r.problemas.length);

  return (
    <>
      <button
        type="button"
        onClick={abrir}
        className="rounded border border-primary px-4 py-2 text-sm font-bold text-primary hover:bg-primary/10"
      >
        Importar
      </button>

      <dialog
        ref={dialogo}
        className="w-full max-w-3xl rounded-lg p-0 backdrop:bg-dark/40"
      >
        <div className="flex max-h-[80vh] flex-col gap-4 overflow-y-auto p-6">
          <h2 className="font-heading text-lg text-dark">Importar recetario</h2>

          <a
            href={RUTA_PLANTILLA_RECETAS}
            className="text-sm text-primary underline"
            download
          >
            Descargar plantilla (.xlsx)
          </a>

          <label className="flex flex-col gap-1 text-xs text-gray">
            Archivo llenado
            <input
              type="file"
              accept=".xlsx"
              className="text-sm text-dark"
              onChange={(e) => {
                const archivo = e.target.files?.[0];
                if (archivo) revisar(archivo);
              }}
            />
          </label>

          {ocupado && <p className="text-sm text-gray">Procesando…</p>}
          {error && <p className="text-sm text-secondary">{error}</p>}
          {resultado && <p className="text-sm font-semibold text-dark">{resultado}</p>}

          {revision && !resultado && (
            <Revision
              revision={revision}
              recetas={recetas}
              articulos={articulos}
              pendientes={pendientes}
              onResolver={resolver}
            />
          )}

          <div className="flex justify-end gap-2 border-t border-borde pt-4">
            <button
              type="button"
              className="px-4 py-2 text-sm text-gray"
              onClick={() => dialogo.current?.close()}
            >
              {resultado ? "Cerrar" : "Cancelar"}
            </button>
            {revision && !resultado && (
              <button
                type="button"
                className="rounded bg-primary px-4 py-2 text-sm font-bold text-white disabled:opacity-50"
                disabled={ocupado || importables.length === 0}
                onClick={confirmar}
              >
                Importar {importables.length} receta(s)
              </button>
            )}
          </div>
        </div>
      </dialog>
    </>
  );
}

/** Insumos que siguen sin artículo, sin repetir. */
function sinResolver(recetas: RecetaRevisada[]): string[] {
  return [
    ...new Set(
      recetas.flatMap((r) =>
        r.ingredientes.filter((i) => !i.articulo_id).map((i) => i.insumo),
      ),
    ),
  ];
}

function Revision({
  revision,
  recetas,
  articulos,
  pendientes,
  onResolver,
}: {
  revision: RevisionImportacion;
  recetas: RecetaRevisada[];
  articulos: Articulo[];
  pendientes: string[];
  onResolver: (insumo: string, articuloId: string) => void;
}) {
  const conProblema = recetas.filter((r) => r.problemas.length);
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-dark">
        <strong>{revision.listas}</strong> lista(s) para importar
        {conProblema.length > 0 && (
          <>
            {" · "}
            <span className="text-secondary">
              {conProblema.length} con problemas
            </span>
          </>
        )}
      </p>

      {revision.ingredientes_sin_receta.length > 0 && (
        <p className="rounded bg-secondary/10 p-3 text-xs text-secondary">
          Estos ingredientes nombran una receta que la hoja «Recetas» no
          declara, así que no se van a cargar:{" "}
          <strong>{revision.ingredientes_sin_receta.join(", ")}</strong>. Suele
          ser una diferencia de escritura entre las dos hojas.
        </p>
      )}

      {pendientes.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-xs font-semibold text-dark">
            Insumos que no están en el catálogo
          </p>
          <p className="text-xs text-gray">
            Elige cuál es, o déjalo sin resolver para omitir esa línea. Lo que
            elijas se aplica a todas las recetas que lo nombran.
          </p>
          {pendientes.map((insumo) => (
            <div key={insumo} className="flex items-center gap-2">
              <span className="min-w-40 text-sm text-dark">{insumo}</span>
              <select
                className="flex-1 rounded border border-borde bg-white px-2 py-1 text-sm"
                defaultValue=""
                onChange={(e) => onResolver(insumo, e.target.value)}
              >
                <option value="">Omitir esta línea</option>
                {articulos.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.nombre}
                  </option>
                ))}
              </select>
            </div>
          ))}
        </div>
      )}

      {conProblema.length > 0 && (
        <div className="flex flex-col gap-1">
          <p className="text-xs font-semibold text-dark">
            Filas que no se van a importar
          </p>
          {conProblema.map((r) => (
            <p key={`${r.fila}-${r.nombre}`} className="text-xs text-gray">
              <span className="font-mono">Fila {r.fila}</span> · {r.nombre} —{" "}
              <span className="text-secondary">{r.problemas.join("; ")}</span>
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
