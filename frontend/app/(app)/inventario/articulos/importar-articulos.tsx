"use client";

import { useState } from "react";

import { DialogoImportar } from "@/components/planilla/dialogo-importar";
import {
  catalogoApi,
  type ArticuloRevisado,
  type Categoria,
  type RevisionArticulos,
  RUTA_EXPORTAR_ARTICULOS,
  RUTA_PLANTILLA_ARTICULOS,
} from "@/lib/catalogo";
import { ErrorApi } from "@/lib/cliente-api";

/**
 * Carga masiva del catálogo de artículos (RN-INV-023, ADR-051).
 *
 * La identidad de una fila es el `ID` o, si va vacío, el `Código`: el nombre
 * no sirve de clave porque el nombre es justamente lo que se edita.
 *
 * Una categoría que el catálogo no reconoce no frena la fila —el artículo
 * entra sin categoría— pero se muestra para que alguien la resuelva o la cree.
 * Nunca se crea sola: un "Bevidas" mal tecleado dejaría una categoría
 * duplicada que después hay que fusionar a mano (ADR-046).
 */

type Props = { onImportados: () => void };

export function ImportarArticulos({ onImportados }: Props) {
  const [revision, setRevision] = useState<RevisionArticulos | null>(null);
  const [articulos, setArticulos] = useState<ArticuloRevisado[]>([]);
  const [categorias, setCategorias] = useState<Categoria[]>([]);

  function abrir() {
    setRevision(null);
    setArticulos([]);
    catalogoApi.categorias().then(setCategorias).catch(() => setCategorias([]));
  }

  async function revisar(archivo: File) {
    const datos = await catalogoApi.validarImportacionArticulos(archivo);
    setRevision(datos);
    setArticulos(datos.articulos);
  }

  /** Resuelve una categoría en TODAS las filas que la nombran: el mismo
   * nombre suele repetirse en decenas de artículos. */
  const resolver = (nombre: string, categoriaId: string) =>
    setArticulos((previos) =>
      previos.map((a) =>
        a.categoria === nombre ? { ...a, categoria_id: categoriaId || null } : a,
      ),
    );

  async function crearCategoria(nombre: string) {
    const categoria = await catalogoApi.crearCategoria({ nombre });
    setCategorias((previas) => [...previas, categoria]);
    resolver(nombre, categoria.id);
  }

  const importables = articulos.filter((a) => !a.problemas.length);

  async function confirmar() {
    const resultado = await catalogoApi.importarArticulos(importables);
    onImportados();
    return resultado;
  }

  return (
    <DialogoImportar
      titulo="Importar artículos"
      ayuda="Para corregir artículos que ya existen, parte del catálogo actual: la columna ID —o el Código— es la que le dice al sistema cuál actualizar."
      rutaPlantilla={RUTA_PLANTILLA_ARTICULOS}
      rutaExportar={RUTA_EXPORTAR_ARTICULOS}
      onAbrir={abrir}
      onValidar={revisar}
      onConfirmar={confirmar}
      importables={importables.length}
    >
      {revision && (
        <Revision
          revision={revision}
          articulos={articulos}
          categorias={categorias}
          onResolver={resolver}
          onCrear={crearCategoria}
        />
      )}
    </DialogoImportar>
  );
}

function Revision({
  revision,
  articulos,
  categorias,
  onResolver,
  onCrear,
}: {
  revision: RevisionArticulos;
  articulos: ArticuloRevisado[];
  categorias: Categoria[];
  onResolver: (nombre: string, categoriaId: string) => void;
  onCrear: (nombre: string) => Promise<void>;
}) {
  const conProblema = articulos.filter((a) => a.problemas.length);
  const aActualizar = articulos.filter(
    (a) => a.accion === "actualizar" && !a.problemas.length,
  );
  const pendientes = [
    ...new Set(
      articulos.filter((a) => a.categoria && !a.categoria_id).map((a) => a.categoria),
    ),
  ];

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-dark">
        <strong>{revision.listas}</strong> nuevo(s)
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

      {revision.unidades_desconocidas.length > 0 && (
        <p className="rounded bg-secondary/10 p-3 text-xs text-secondary">
          Estas unidades de medida no existen:{" "}
          <strong>{revision.unidades_desconocidas.join(", ")}</strong>. Créalas
          en la configuración de unidades y vuelve a subir el archivo — una
          unidad define cómo se cuenta el stock, así que no se improvisa acá.
        </p>
      )}

      {revision.skus_sin_articulo.length > 0 && (
        <p className="rounded bg-secondary/10 p-3 text-xs text-secondary">
          Estos SKU nombran un artículo que la hoja «Artículos» no declara, así
          que no se van a cargar:{" "}
          <strong>{revision.skus_sin_articulo.join(", ")}</strong>.
        </p>
      )}

      {pendientes.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-xs font-semibold text-dark">
            Categorías que no están en el catálogo
          </p>
          <p className="text-xs text-gray">
            Elige cuál es o créala. Si la dejas sin resolver, el artículo entra
            igual, sin categoría.
          </p>
          {pendientes.map((nombre) => (
            <ResolverCategoria
              key={nombre}
              nombre={nombre}
              categorias={categorias}
              onResolver={onResolver}
              onCrear={onCrear}
            />
          ))}
        </div>
      )}

      {aActualizar.length > 0 && (
        <div className="flex flex-col gap-1">
          <p className="text-xs font-semibold text-dark">
            Artículos que ya existen y se van a actualizar
          </p>
          {aActualizar.map((a) => (
            <p key={a.fila} className="text-xs text-gray">
              <span className="font-mono">{a.codigo}</span> · {a.nombre}
              {a.cambios.length > 0 && <> — {a.cambios.join(" · ")}</>}
            </p>
          ))}
        </div>
      )}

      {conProblema.length > 0 && (
        <div className="flex flex-col gap-1">
          <p className="text-xs font-semibold text-dark">
            Filas que no se van a importar
          </p>
          {conProblema.map((a) => (
            <p key={`${a.fila}-${a.codigo}`} className="text-xs text-gray">
              <span className="font-mono">Fila {a.fila}</span> · {a.nombre} —{" "}
              <span className="text-secondary">{a.problemas.join("; ")}</span>
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

function ResolverCategoria({
  nombre,
  categorias,
  onResolver,
  onCrear,
}: {
  nombre: string;
  categorias: Categoria[];
  onResolver: (nombre: string, categoriaId: string) => void;
  onCrear: (nombre: string) => Promise<void>;
}) {
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  async function crear() {
    setError("");
    setOcupado(true);
    try {
      await onCrear(nombre);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo crear.");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-2">
        <span className="min-w-40 text-sm text-dark">{nombre}</span>
        <select
          className="flex-1 rounded border border-borde bg-white px-2 py-1 text-sm"
          defaultValue=""
          onChange={(e) => onResolver(nombre, e.target.value)}
        >
          <option value="">Dejar sin categoría</option>
          {categorias.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nombre}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="rounded border border-primary px-2 py-1 text-xs text-primary hover:bg-primary/10 disabled:opacity-50"
          disabled={ocupado}
          onClick={crear}
        >
          Crear «{nombre}»
        </button>
      </div>
      {error && <p className="text-xs text-secondary">{error}</p>}
    </div>
  );
}
