"use client";

import { useState } from "react";

import { DialogoImportar } from "@/components/planilla/dialogo-importar";
import {
  catalogoApi,
  type Articulo,
  type RecetaRevisada,
  type RevisionImportacion,
  type UnidadMedida,
  RUTA_EXPORTAR_RECETAS,
  RUTA_PLANTILLA_RECETAS,
} from "@/lib/catalogo";
import { ErrorApi } from "@/lib/cliente-api";

/**
 * Carga masiva del recetario (RN-COM-031, ADR-052).
 *
 * El recorrido es: bajar la plantilla —o el recetario ya cargado— → subirla →
 * **revisar** → confirmar. La revisión es el punto: el archivo casi nunca
 * viene perfecto, y el modo de falla que hay que evitar es el silencioso —
 * importar la mitad y que nadie se entere de la otra mitad.
 *
 * Por eso un insumo que el catálogo no reconoce no cancela nada: se resuelve
 * fila por fila eligiendo uno existente o creándolo acá mismo, y lo que se
 * deja sin resolver se omite **a la vista**, no en silencio.
 *
 * Una fila con `ID` actualiza en vez de crear. Los ingredientes que el
 * archivo no menciona se conservan salvo que se pida quitarlos, receta por
 * receta y con el número de líneas a la vista: subir una hoja parcial por
 * error no puede vaciar una receta.
 */

type Props = { onImportadas: () => void };

export function ImportarRecetas({ onImportadas }: Props) {
  const [revision, setRevision] = useState<RevisionImportacion | null>(null);
  const [recetas, setRecetas] = useState<RecetaRevisada[]>([]);
  const [articulos, setArticulos] = useState<Articulo[]>([]);
  const [unidades, setUnidades] = useState<UnidadMedida[]>([]);

  function abrir() {
    setRevision(null);
    setRecetas([]);
    catalogoApi.articulos().then(setArticulos).catch(() => setArticulos([]));
    catalogoApi.unidadesMedida().then(setUnidades).catch(() => setUnidades([]));
  }

  async function revisar(archivo: File) {
    const datos = await catalogoApi.validarImportacion(archivo);
    setRevision(datos);
    setRecetas(datos.recetas);
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

  /** El insumo recién creado entra al catálogo local y se resuelve solo: si
   * hubiera que recargar la lista a mano, crear uno costaría lo mismo que
   * irse a `/inventario/articulos`, que es justo lo que esto evita. */
  async function crearInsumo(insumo: string, datos: DatosArticulo) {
    const articulo = await catalogoApi.crearArticulo({
      id_interno: datos.codigo,
      nombre: insumo,
      unidad_medida_id: datos.unidadId,
      tipo: datos.tipo,
    });
    setArticulos((previos) => [...previos, articulo]);
    resolver(insumo, articulo.id);
  }

  const marcarAusentes = (fila: number, valor: "conservar" | "quitar") =>
    setRecetas((previas) =>
      previas.map((r) =>
        r.fila === fila ? { ...r, ingredientes_ausentes: valor } : r,
      ),
    );

  const importables = recetas.filter((r) => r.unidad_medida_id && !r.problemas.length);

  async function confirmar() {
    const resultado = await catalogoApi.importarRecetas(importables);
    onImportadas();
    return resultado;
  }

  return (
    <DialogoImportar
      titulo="Importar recetario"
      ayuda="Para corregir recetas que ya existen, parte del recetario actual: la columna ID es la que le dice al sistema cuál actualizar."
      rutaPlantilla={RUTA_PLANTILLA_RECETAS}
      rutaExportar={RUTA_EXPORTAR_RECETAS}
      onAbrir={abrir}
      onValidar={revisar}
      onConfirmar={confirmar}
      importables={importables.length}
    >
      {revision && (
        <Revision
          revision={revision}
          recetas={recetas}
          articulos={articulos}
          unidades={unidades}
          pendientes={sinResolver(recetas)}
          onResolver={resolver}
          onCrear={crearInsumo}
          onMarcarAusentes={marcarAusentes}
        />
      )}
    </DialogoImportar>
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

type DatosArticulo = { codigo: string; unidadId: string; tipo: string };

function Revision({
  revision,
  recetas,
  articulos,
  unidades,
  pendientes,
  onResolver,
  onCrear,
  onMarcarAusentes,
}: {
  revision: RevisionImportacion;
  recetas: RecetaRevisada[];
  articulos: Articulo[];
  unidades: UnidadMedida[];
  pendientes: string[];
  onResolver: (insumo: string, articuloId: string) => void;
  onCrear: (insumo: string, datos: DatosArticulo) => Promise<void>;
  onMarcarAusentes: (fila: number, valor: "conservar" | "quitar") => void;
}) {
  const conProblema = recetas.filter((r) => r.problemas.length);
  const aActualizar = recetas.filter(
    (r) => r.accion === "actualizar" && !r.problemas.length,
  );
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-dark">
        <strong>{revision.listas}</strong> nueva(s)
        {aActualizar.length > 0 && (
          <>
            {" · "}
            <strong>{aActualizar.length}</strong> a actualizar
          </>
        )}
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
            Elige cuál es, créalo, o déjalo sin resolver para omitir esa línea.
            Lo que elijas se aplica a todas las recetas que lo nombran.
          </p>
          {pendientes.map((insumo) => (
            <ResolverInsumo
              key={insumo}
              insumo={insumo}
              articulos={articulos}
              unidades={unidades}
              onResolver={onResolver}
              onCrear={onCrear}
            />
          ))}
        </div>
      )}

      {aActualizar.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-xs font-semibold text-dark">
            Recetas que ya existen y se van a actualizar
          </p>
          {aActualizar.map((r) => (
            <div
              key={r.fila}
              className="rounded border border-borde p-3 text-xs text-gray"
            >
              <p className="font-semibold text-dark">{r.nombre}</p>
              {r.cambios.length > 0 && <p>{r.cambios.join(" · ")}</p>}
              {r.se_quitarian.length > 0 && (
                <label className="mt-2 flex items-start gap-2 text-xs text-dark">
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={r.ingredientes_ausentes === "quitar"}
                    onChange={(e) =>
                      onMarcarAusentes(
                        r.fila,
                        e.target.checked ? "quitar" : "conservar",
                      )
                    }
                  />
                  <span>
                    Quitar los {r.se_quitarian.length} ingrediente(s) que el
                    archivo no menciona:{" "}
                    <span className="text-gray">
                      {r.se_quitarian.join(", ")}
                    </span>
                  </span>
                </label>
              )}
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

/** Una línea de resolución: elegir, crear, u omitir.
 *
 * Crear el insumo acá es lo que evita perder el trabajo de resolver las otras
 * cincuenta filas (RN-COM-031). No lo crea el importador solo: un nombre mal
 * escrito ensuciaría el catálogo con un duplicado que después hay que fusionar
 * a mano (ADR-046). */
function ResolverInsumo({
  insumo,
  articulos,
  unidades,
  onResolver,
  onCrear,
}: {
  insumo: string;
  articulos: Articulo[];
  unidades: UnidadMedida[];
  onResolver: (insumo: string, articuloId: string) => void;
  onCrear: (insumo: string, datos: DatosArticulo) => Promise<void>;
}) {
  const [creando, setCreando] = useState(false);
  const [codigo, setCodigo] = useState("");
  const [unidadId, setUnidadId] = useState("");
  const [tipo, setTipo] = useState("insumo");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  async function crear() {
    setError("");
    setOcupado(true);
    try {
      await onCrear(insumo, { codigo: codigo.toUpperCase(), unidadId, tipo });
      setCreando(false);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo crear el insumo.");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
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
        <button
          type="button"
          className="rounded border border-primary px-2 py-1 text-xs text-primary hover:bg-primary/10"
          onClick={() => setCreando((v) => !v)}
        >
          {creando ? "Cancelar" : "Crear"}
        </button>
      </div>

      {creando && (
        <div className="flex flex-wrap items-end gap-2 rounded bg-fondo p-2">
          <label className="flex flex-col gap-1 text-xs text-gray">
            Código (4)
            <input
              value={codigo}
              maxLength={4}
              onChange={(e) => setCodigo(e.target.value)}
              className="w-20 rounded border border-borde px-2 py-1 text-sm uppercase"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-gray">
            Unidad
            <select
              value={unidadId}
              onChange={(e) => setUnidadId(e.target.value)}
              className="rounded border border-borde bg-white px-2 py-1 text-sm"
            >
              <option value="">Elegir…</option>
              {unidades.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.nombre}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-gray">
            Tipo
            <select
              value={tipo}
              onChange={(e) => setTipo(e.target.value)}
              className="rounded border border-borde bg-white px-2 py-1 text-sm"
            >
              <option value="insumo">Insumo</option>
              <option value="subreceta">Subreceta</option>
            </select>
          </label>
          <button
            type="button"
            className="rounded bg-primary px-3 py-1 text-xs font-bold text-white disabled:opacity-50"
            disabled={ocupado || !codigo || !unidadId}
            onClick={crear}
          >
            Crear «{insumo}»
          </button>
          {error && <p className="w-full text-xs text-secondary">{error}</p>}
        </div>
      )}
    </div>
  );
}
