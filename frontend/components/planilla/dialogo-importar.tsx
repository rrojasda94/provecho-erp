"use client";

import { useRef, useState, type ReactNode } from "react";

import { ErrorApi } from "@/lib/cliente-api";

/**
 * La carcasa de una carga masiva por planilla (ADR-052).
 *
 * Lo que es igual en recetas, artículos y clientes no tiene nada de negocio
 * adentro: el botón, el modal, los dos enlaces de descarga, el `<input
 * type="file">`, ocupado/error/resultado y el pie. Lo que cambia —qué se
 * revisa y qué se manda— entra por `children` y por los dos callbacks, y lo
 * escribe cada pantalla en su propio archivo.
 *
 * El estado de la revisión lo tiene el consumidor, no esta carcasa: es él
 * quien la modifica cuando alguien resuelve una referencia o decide qué
 * borrar, y devolverle un setter genérico solo agregaría una capa.
 */

export type ResultadoPlanilla = {
  creadas: unknown[];
  actualizadas: unknown[];
  omitidas: unknown[];
};

type Props = {
  titulo: string;
  /** Ayuda de una línea sobre para qué sirve bajar el archivo actual. */
  ayuda: string;
  rutaPlantilla: string;
  rutaExportar: string;
  /** Se llama al abrir: el momento de cargar los catálogos de resolución. */
  onAbrir: () => void;
  onValidar: (archivo: File) => Promise<void>;
  onConfirmar: () => Promise<ResultadoPlanilla>;
  /** Cuántas filas entran hoy. `0` deshabilita el botón de importar. */
  importables: number;
  /** El cuerpo de la revisión, o `null` si todavía no se subió nada. */
  children: ReactNode;
};

export function DialogoImportar({
  titulo,
  ayuda,
  rutaPlantilla,
  rutaExportar,
  onAbrir,
  onValidar,
  onConfirmar,
  importables,
  children,
}: Props) {
  const dialogo = useRef<HTMLDialogElement>(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [resultado, setResultado] = useState<string | null>(null);

  const abrir = () => {
    setError("");
    setResultado(null);
    onAbrir();
    dialogo.current?.showModal();
  };

  async function revisar(archivo: File) {
    setError("");
    setOcupado(true);
    try {
      await onValidar(archivo);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo leer el archivo.");
    } finally {
      setOcupado(false);
    }
  }

  async function confirmar() {
    setError("");
    setOcupado(true);
    try {
      const { creadas, actualizadas, omitidas } = await onConfirmar();
      setResultado(
        [
          `${creadas.length} importada(s)`,
          actualizadas.length ? `${actualizadas.length} actualizada(s)` : "",
          omitidas.length ? `${omitidas.length} omitida(s)` : "",
        ]
          .filter(Boolean)
          .join(", ") + ".",
      );
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo importar.");
    } finally {
      setOcupado(false);
    }
  }

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
          <h2 className="font-heading text-lg text-dark">{titulo}</h2>

          <div className="flex flex-wrap gap-4">
            <a href={rutaPlantilla} className="text-sm text-primary underline" download>
              Descargar plantilla vacía (.xlsx)
            </a>
            <a href={rutaExportar} className="text-sm text-primary underline" download>
              Descargar lo que ya está cargado (.xlsx)
            </a>
          </div>
          <p className="text-xs text-gray">{ayuda}</p>

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

          {!resultado && children}

          <div className="flex justify-end gap-2 border-t border-borde pt-4">
            <button
              type="button"
              className="px-4 py-2 text-sm text-gray"
              onClick={() => dialogo.current?.close()}
            >
              {resultado ? "Cerrar" : "Cancelar"}
            </button>
            {!resultado && importables > 0 && (
              <button
                type="button"
                className="rounded bg-primary px-4 py-2 text-sm font-bold text-white disabled:opacity-50"
                disabled={ocupado}
                onClick={confirmar}
              >
                Importar {importables} fila(s)
              </button>
            )}
          </div>
        </div>
      </dialog>
    </>
  );
}
