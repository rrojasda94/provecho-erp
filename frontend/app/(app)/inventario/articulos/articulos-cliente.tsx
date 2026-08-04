"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useRef, useState } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";
import {
  catalogoApi,
  TIPOS_ARTICULO,
  type Articulo,
  type Categoria,
  type UnidadMedida,
} from "@/lib/catalogo";
import { ErrorApi } from "@/lib/proxy";
import { aTitulo } from "@/lib/texto";

/**
 * Artículos: lo que se compra, se guarda y se consume.
 *
 * Es la base de toda receta — sin insumos propios cargados, la ficha de un
 * producto solo puede ofrecer los tres del seeder de demo. Por eso esta
 * pantalla existe antes que cualquier otra de inventario: stock, lotes y
 * conteos ya tienen API, pero no sirven de nada si no hay qué contar.
 *
 * La unidad de medida **no se edita** después de crear el artículo: cambiarla
 * reescribiría en silencio el significado de todo el stock y de cada receta
 * que lo use (RN-UDM-002 exige un proceso propio de conversión).
 */
export function ArticulosCliente({
  articulos,
  unidades,
  categorias,
}: {
  articulos: Articulo[];
  unidades: UnidadMedida[];
  categorias: Categoria[];
}) {
  const [filas, setFilas] = useState(articulos);
  const nombreUdm = useMemo(
    () => new Map(unidades.map((u) => [u.id, u.nombre])),
    [unidades],
  );
  const etiquetaTipo = useMemo(
    () =>
      new Map<string, string>(
        TIPOS_ARTICULO.map((t) => [t.valor, t.etiqueta.split(" (")[0]]),
      ),
    [],
  );

  const columnas = useMemo<ColumnDef<Articulo>[]>(
    () => [
      { accessorKey: "nombre", header: "Artículo" },
      { accessorKey: "id_interno", header: "Código" },
      {
        id: "tipo",
        header: "Tipo",
        accessorFn: (a) => etiquetaTipo.get(a.tipo) ?? a.tipo,
      },
      {
        id: "unidad",
        header: "Unidad",
        accessorFn: (a) => nombreUdm.get(a.unidad_medida_id) ?? "—",
      },
      {
        id: "costo",
        header: "Costo promedio",
        accessorFn: (a) => `S/ ${Number(a.costo_promedio).toFixed(4)}`,
      },
      {
        accessorKey: "controla_lote",
        header: "Lote / FEFO",
        cell: ({ getValue }) => (getValue<boolean>() ? "Sí" : "—"),
      },
    ],
    [etiquetaTipo, nombreUdm],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-xl italic uppercase text-dark">Artículos</h1>
          <p className="text-xs text-gray">
            Insumos, subrecetas, mercadería y empaques. Son los que aparecen al
            armar una receta.
          </p>
        </div>
        <DialogoNuevoArticulo
          unidades={unidades}
          categorias={categorias}
          onCreado={(a) => setFilas((f) => [...f, a].sort((x, y) => x.nombre.localeCompare(y.nombre)))}
        />
      </div>
      <TablaDatos
        columnas={columnas}
        datos={filas}
        placeholderBusqueda="Buscar artículo..."
      />
    </div>
  );
}

function DialogoNuevoArticulo({
  unidades,
  categorias,
  onCreado,
}: {
  unidades: UnidadMedida[];
  categorias: Categoria[];
  onCreado: (articulo: Articulo) => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [nombre, setNombre] = useState("");
  const [idInterno, setIdInterno] = useState("");
  const [tipo, setTipo] = useState<string>("insumo");
  const [udmId, setUdmId] = useState(unidades[0]?.id ?? "");
  const [categoriaId, setCategoriaId] = useState("");
  const [costo, setCosto] = useState("0");
  const [controlaLote, setControlaLote] = useState(false);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  async function crear() {
    setError("");
    setGuardando(true);
    try {
      const articulo = await catalogoApi.crearArticulo({
        id_interno: idInterno.trim().toUpperCase(),
        nombre,
        unidad_medida_id: udmId,
        tipo,
        categoria_id: categoriaId || null,
        costo_promedio: costo || "0",
        controla_lote: controlaLote,
      });
      onCreado(articulo);
      dialogRef.current?.close();
      setNombre("");
      setIdInterno("");
      setCosto("0");
      setControlaLote(false);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo crear el artículo.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => dialogRef.current?.showModal()}
        className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
        disabled={unidades.length === 0}
      >
        + Nuevo artículo
      </button>
      <dialog ref={dialogRef} className="w-full max-w-md rounded-lg p-0 backdrop:bg-dark/40">
        <div className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg italic uppercase text-dark">
            Nuevo artículo
          </h2>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Nombre
            <input
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              onBlur={() => setNombre((n) => aTitulo(n))}
              maxLength={150}
              placeholder="Queso Mozzarella"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Código interno (4)
            <input
              value={idInterno}
              onChange={(e) => setIdInterno(e.target.value.slice(0, 4))}
              maxLength={4}
              placeholder="QMOZ"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Tipo
            <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
              {TIPOS_ARTICULO.map((t) => (
                <option key={t.valor} value={t.valor}>
                  {t.etiqueta}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Unidad de medida
            <select value={udmId} onChange={(e) => setUdmId(e.target.value)}>
              {unidades.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.nombre} ({u.decimales} decimales)
                </option>
              ))}
            </select>
            <span className="text-xs font-normal text-gray">
              No se puede cambiar después: cambiaría el significado de todo el
              stock y de cada receta que lo use.
            </span>
          </label>
          {categorias.length > 0 && (
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Categoría
              <select
                value={categoriaId}
                onChange={(e) => setCategoriaId(e.target.value)}
              >
                <option value="">Sin categoría</option>
                {categorias.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nombre}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Costo promedio (S/)
            <input
              value={costo}
              onChange={(e) => setCosto(e.target.value)}
              inputMode="decimal"
            />
            <span className="text-xs font-normal text-gray">
              Se recalcula solo con cada compra recibida; esto es el valor de
              arranque.
            </span>
          </label>
          <label className="flex items-center gap-2 text-sm font-semibold">
            <input
              type="checkbox"
              checked={controlaLote}
              onChange={(e) => setControlaLote(e.target.checked)}
            />
            Controla lote y vencimiento (FEFO)
          </label>
          {error && (
            <p role="alert" className="text-sm font-semibold text-secondary">
              {error}
            </p>
          )}
          <div className="mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => dialogRef.current?.close()}
              className="rounded border border-gray px-4 py-2 text-sm font-semibold text-dark"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={crear}
              disabled={guardando || !nombre.trim() || !idInterno || !udmId}
              className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary disabled:opacity-50"
            >
              {guardando ? "Creando..." : "Crear artículo"}
            </button>
          </div>
        </div>
      </dialog>
    </>
  );
}
