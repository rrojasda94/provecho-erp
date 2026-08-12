"use client";

import Link from "next/link";

import { Rastro } from "@/components/shell/rastro";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";

import {
  catalogoApi,
  type GrupoOpcion,
  type Producto,
  type ProductoDetalle,
  type Receta,
  type UnidadMedida,
} from "@/lib/catalogo";
import { ErrorApi, pedir } from "@/lib/cliente-api";
import { aTitulo } from "@/lib/texto";

export type ListaPrecio = {
  id: string;
  nombre: string;
  canal: string | null;
  modalidad: string | null;
  vigente_desde: string;
  vigente_hasta: string | null;
  activa: boolean;
};

/**
 * Ficha del producto comercial: qué se vende, en qué presentaciones y a qué
 * precio.
 *
 * **Acá no se editan recetas, se eligen.** La receta se arma una sola vez en
 * Catálogo → Recetas y desde el producto solo se apunta a ella: tener el
 * editor en los dos lados hacía pensar que eran dos recetas distintas.
 *
 * Un producto puede venderse de dos formas:
 * - **Simple**: una receta, un precio.
 * - **Con presentaciones**: Personal, Mediana y Familiar son productos hijos
 *   (`producto_padre_id`), cada uno con **su** receta y **su** precio
 *   completo (RN-COM-022). Cada fila de esa tabla es una tarjeta obligatoria
 *   en el PDV. El padre agrupa y no se vende.
 */
export function FichaProducto({
  inicial,
  recetas,
  unidades,
  extrasDisponibles,
  listas,
}: {
  inicial: ProductoDetalle;
  recetas: Receta[];
  unidades: UnidadMedida[];
  extrasDisponibles: Producto[];
  listas: ListaPrecio[];
}) {
  const router = useRouter();
  const [producto, setProducto] = useState(inicial);
  const [error, setError] = useState("");

  const recargar = useCallback(async () => {
    try {
      setProducto(await catalogoApi.producto(inicial.id));
      // También el servidor: crear una presentación crea su receta, y sin
      // esto la receta nueva no aparecía en el desplegable que la debe
      // mostrar.
      router.refresh();
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo releer el producto.");
    }
  }, [inicial.id, router]);

  const correr = useCallback(
    async (accion: () => Promise<unknown>) => {
      setError("");
      try {
        await accion();
        await recargar();
      } catch (e) {
        setError(e instanceof ErrorApi ? e.message : "No se pudo guardar el cambio.");
      }
    },
    [recargar],
  );

  const conPresentaciones = producto.variantes.length > 0;

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <div>
        <Rastro hoja={producto.nombre} />
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <input
            defaultValue={producto.nombre}
            maxLength={150}
            className="flex-1 font-heading text-xl text-dark"
            aria-label="Nombre del producto"
            onBlur={(e) => {
              const nombre = aTitulo(e.target.value);
              e.target.value = nombre;
              if (nombre !== producto.nombre) {
                correr(() => catalogoApi.editarProducto(producto.id, { nombre }));
              }
            }}
          />
          <span className="rounded bg-cream px-2 py-1 text-xs font-semibold text-gray">
            {producto.id_interno}
          </span>
          {!producto.es_extra && (
            <Link
              href={`/catalogo/productos/${producto.id}/nodos`}
              className="rounded border border-primary px-2 py-1 text-xs font-semibold text-primary hover:bg-primary/10"
              title="El árbol completo: tamaños, sabores, extras, restas y empaque, con el costo de cada combinación"
            >
              Ver nodos
            </Link>
          )}
          <label className="flex items-center gap-2 text-sm font-semibold">
            <input
              type="checkbox"
              checked={producto.activo}
              onChange={(e) =>
                correr(() =>
                  catalogoApi.editarProducto(producto.id, { activo: e.target.checked }),
                )
              }
            />
            Activo
          </label>
        </div>
        <p className="mt-1 text-xs text-gray">
          {producto.es_extra
            ? "Extra: se agrega a otro producto, no aparece suelto en la carta."
            : conPresentaciones
              ? "Se vende por presentación: el PDV obliga a elegir una tarjeta."
              : "Producto simple: una receta y un precio."}
        </p>
      </div>

      {error && (
        <p role="alert" className="text-sm font-semibold text-secondary">
          {error}
        </p>
      )}

      {!conPresentaciones && (
        <SeccionSimple
          producto={producto}
          recetas={recetas}
          listas={listas}
          onElegirReceta={(recetaId) =>
            correr(() =>
              catalogoApi.editarProducto(producto.id, { receta_id: recetaId }),
            )
          }
          onQuitarReceta={() =>
            correr(() =>
              catalogoApi.editarProducto(producto.id, { quitar_receta: true }),
            )
          }
          onError={setError}
        />
      )}

      {!producto.es_extra && (
        <SeccionPresentaciones
          producto={producto}
          recetas={recetas}
          unidades={unidades}
          listas={listas}
          onCambio={recargar}
          onError={setError}
        />
      )}

      {!producto.es_extra && (
        <SeccionExtras
          producto={producto}
          extrasDisponibles={extrasDisponibles}
          onVincular={(cuerpo) =>
            correr(() => catalogoApi.vincularExtra(producto.id, cuerpo))
          }
          onCrearGrupo={(cuerpo) =>
            correr(() => catalogoApi.crearGrupo(producto.id, cuerpo))
          }
        />
      )}
    </div>
  );
}

/** Desplegable de recetas ya creadas, con salida al módulo que sí las edita. */
function SelectorReceta({
  recetas,
  valor,
  deshabilitado,
  onElegir,
}: {
  recetas: Receta[];
  valor: string | null;
  deshabilitado?: boolean;
  onElegir: (recetaId: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <select
        value={valor ?? ""}
        disabled={deshabilitado}
        aria-label="Receta"
        className="min-w-56 text-sm"
        onChange={(e) => e.target.value && onElegir(e.target.value)}
      >
        <option value="">Elegir receta...</option>
        {recetas.map((r) => (
          <option key={r.id} value={r.id}>
            {r.nombre}
          </option>
        ))}
      </select>
      {valor && (
        <Link
          href={`/catalogo/recetas/${valor}`}
          className="text-xs text-primary hover:underline"
        >
          editar
        </Link>
      )}
    </div>
  );
}

function SeccionSimple({
  producto,
  recetas,
  listas,
  onElegirReceta,
  onQuitarReceta,
  onError,
}: {
  producto: ProductoDetalle;
  recetas: Receta[];
  listas: ListaPrecio[];
  onElegirReceta: (recetaId: string) => void;
  onQuitarReceta: () => void;
  onError: (mensaje: string) => void;
}) {
  return (
    <section className="rounded-lg border border-gray/20 bg-white p-4">
      <h2 className="mb-1 font-heading text-lg text-dark">Receta</h2>
      <p className="mb-3 text-xs text-gray">
        Se elige entre las que ya existen. Para armarla o corregirla, ve a{" "}
        <Link href="/catalogo/recetas" className="text-primary hover:underline">
          Catálogo → Recetas
        </Link>
        .
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <SelectorReceta
          recetas={recetas}
          valor={producto.receta_id}
          onElegir={onElegirReceta}
        />
        {producto.receta_id && !producto.es_extra && (
          <button
            type="button"
            onClick={onQuitarReceta}
            className="text-xs text-secondary hover:underline"
            title="Deja el producto sin receta para poder venderlo por presentaciones. La receta no se borra"
          >
            Quitar receta y vender por presentaciones
          </button>
        )}
      </div>
      {producto.receta_id && (
        <Precio producto={producto} listas={listas} onError={onError} />
      )}
    </section>
  );
}

/**
 * Presentaciones: una fila por tarjeta del PDV.
 *
 * Cada fila es un producto hijo con receta y precio propios; el nombre de la
 * fila es lo que el cajero ve en la tarjeta.
 */
function SeccionPresentaciones({
  producto,
  recetas,
  unidades,
  listas,
  onCambio,
  onError,
}: {
  producto: ProductoDetalle;
  recetas: Receta[];
  unidades: UnidadMedida[];
  listas: ListaPrecio[];
  onCambio: () => void;
  onError: (mensaje: string) => void;
}) {
  const conPresentaciones = producto.variantes.length > 0;

  async function onBorrar(v: Producto) {
    // Una "×" se toca sin querer; borrar una presentación no se deshace.
    if (!window.confirm(`¿Borrar la presentación "${v.nombre}"?`)) return;
    try {
      await catalogoApi.eliminarProducto(v.id);
      onCambio();
    } catch (e) {
      onError(e instanceof ErrorApi ? e.message : "No se pudo borrar.");
    }
  }

  const tieneRecetaPropia = !conPresentaciones && Boolean(producto.receta_id);

  async function editarVariante(
    id: string,
    cuerpo: Parameters<typeof catalogoApi.editarProducto>[1],
  ) {
    try {
      await catalogoApi.editarProducto(id, cuerpo);
      onCambio();
    } catch (e) {
      onError(e instanceof ErrorApi ? e.message : "No se pudo guardar el cambio.");
    }
  }

  return (
    <section className="rounded-lg border border-gray/20 bg-white p-4">
      <h2 className="mb-1 font-heading text-lg text-dark">
        Presentaciones
      </h2>
      <p className="mb-3 text-xs text-gray">
        Personal, Mediana, Familiar... Cada fila es una tarjeta en el PDV y
        elegir una es obligatorio. El nombre de la fila es lo que ve el cajero.
      </p>

      {tieneRecetaPropia && (
        <p className="mb-3 text-sm text-gray">
          Este producto tiene receta propia, así que se vende tal cual. Para
          venderlo por presentaciones, quítasela primero: la lleva cada una.
        </p>
      )}

      {conPresentaciones && (
        <table className="mb-3 w-full text-sm">
          <thead className="text-left text-xs uppercase text-gray">
            <tr>
              <th className="py-1">Tarjeta en el PDV</th>
              <th className="py-1">Receta</th>
              <th className="py-1 w-20">Orden</th>
              <th className="py-1 w-56">Precio</th>
              <th className="py-1 w-8" />
            </tr>
          </thead>
          <tbody>
            {producto.variantes.map((v) => (
              <tr key={v.id} className="border-t border-gray/20 align-top">
                <td className="py-2 pr-2">
                  <input
                    defaultValue={etiquetaCorta(v.nombre, producto.nombre)}
                    className="w-32"
                    aria-label={`Nombre de ${v.nombre}`}
                    onBlur={(e) => {
                      const corto = aTitulo(e.target.value);
                      e.target.value = corto;
                      const completo = `${producto.nombre} ${corto}`.trim();
                      if (corto && completo !== v.nombre) {
                        editarVariante(v.id, { nombre: completo });
                      }
                    }}
                  />
                  <span className="mt-0.5 block text-xs text-gray">
                    {v.id_interno} · {v.nombre}
                  </span>
                </td>
                <td className="py-2 pr-2">
                  <SelectorReceta
                    recetas={recetas}
                    valor={v.receta_id}
                    onElegir={(recetaId) => editarVariante(v.id, { receta_id: recetaId })}
                  />
                </td>
                <td className="py-2 pr-2">
                  <input
                    type="number"
                    defaultValue={v.orden}
                    className="w-16"
                    aria-label={`Orden de ${v.nombre}`}
                    onBlur={(e) => {
                      const orden = Number(e.target.value);
                      if (orden !== v.orden) editarVariante(v.id, { orden });
                    }}
                  />
                </td>
                <td className="py-2">
                  <Precio producto={v} listas={listas} onError={onError} compacto />
                </td>
                <td className="py-2 text-right">
                  <button
                    type="button"
                    onClick={() => onBorrar(v)}
                    className="text-secondary hover:underline"
                    aria-label={`Borrar ${v.nombre}`}
                    title="Solo si nunca se vendió; si ya tiene ventas, desmárcala como activa"
                  >
                    ×
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <NuevaPresentacion
        padre={producto}
        recetas={recetas}
        unidades={unidades}
        deshabilitado={tieneRecetaPropia}
        onCreada={onCambio}
        onError={onError}
      />
    </section>
  );
}

/** "Pizza Peperoni Familiar" dentro de "Pizza Peperoni" → "Familiar". El
 * nombre completo se conserva para el ticket y el comprobante. */
function etiquetaCorta(nombre: string, nombrePadre: string): string {
  return nombre.toLowerCase().startsWith(nombrePadre.toLowerCase())
    ? nombre.slice(nombrePadre.length).trim() || nombre
    : nombre;
}

function NuevaPresentacion({
  padre,
  recetas,
  unidades,
  deshabilitado,
  onCreada,
  onError,
}: {
  padre: Producto;
  recetas: Receta[];
  unidades: UnidadMedida[];
  deshabilitado: boolean;
  onCreada: () => void;
  onError: (mensaje: string) => void;
}) {
  const [nombre, setNombre] = useState("");
  const [idInterno, setIdInterno] = useState("");
  const [recetaId, setRecetaId] = useState("");
  const [guardando, setGuardando] = useState(false);

  async function crear() {
    setGuardando(true);
    try {
      // Si no se eligió receta, se crea una vacía con el nombre de la
      // presentación: la variante no puede existir sin receta, y mandar al
      // usuario a otro módulo antes de poder crear la fila era peor.
      const receta =
        recetaId ||
        (
          await catalogoApi.crearReceta({
            nombre: `${padre.nombre} ${nombre}`.trim(),
            rendimiento_cantidad: "1",
            rendimiento_unidad_medida_id: unidades[0]?.id ?? "",
          })
        ).id;
      await catalogoApi.crearProducto({
        id_interno: idInterno.trim().toUpperCase(),
        marca_id: padre.marca_id,
        nombre: `${padre.nombre} ${nombre}`.trim(),
        receta_id: receta,
        producto_padre_id: padre.id,
      });
      setNombre("");
      setIdInterno("");
      setRecetaId("");
      onCreada();
    } catch (e) {
      onError(e instanceof ErrorApi ? e.message : "No se pudo crear la presentación.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="flex flex-wrap items-end gap-2 rounded bg-cream/60 p-3">
      <label className="flex flex-col gap-1 text-xs font-semibold">
        Tarjeta
        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          onBlur={() => setNombre((n) => aTitulo(n))}
          placeholder="Familiar"
          className="w-32"
          disabled={deshabilitado}
        />
      </label>
      <label className="flex flex-col gap-1 text-xs font-semibold">
        Código
        <input
          value={idInterno}
          onChange={(e) => setIdInterno(e.target.value.slice(0, 4))}
          placeholder="PZPF"
          className="w-20"
          disabled={deshabilitado}
        />
      </label>
      <label className="flex flex-col gap-1 text-xs font-semibold">
        Receta
        <select
          value={recetaId}
          onChange={(e) => setRecetaId(e.target.value)}
          className="min-w-48"
          disabled={deshabilitado}
        >
          <option value="">Crear una vacía con este nombre</option>
          {recetas.map((r) => (
            <option key={r.id} value={r.id}>
              {r.nombre}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        onClick={crear}
        disabled={deshabilitado || guardando || !nombre.trim() || !idInterno}
        className="rounded bg-primary px-3 py-1.5 text-xs font-bold text-white disabled:opacity-50"
      >
        {guardando ? "Creando..." : "+ Presentación"}
      </button>
    </div>
  );
}

function vinculados(producto: ProductoDetalle): string[] {
  return [
    ...producto.extras_sueltos.map((e) => e.extra_id),
    ...producto.grupos.flatMap((g) => g.extras.map((e) => e.extra_id)),
  ];
}

/** Grupos de extras: acá se decide qué es obligatorio elegir en el PDV. */
function SeccionExtras({
  producto,
  extrasDisponibles,
  onVincular,
  onCrearGrupo,
}: {
  producto: ProductoDetalle;
  extrasDisponibles: Producto[];
  onVincular: (cuerpo: { extra_id: string; grupo_id: string }) => void;
  onCrearGrupo: (cuerpo: {
    nombre: string;
    minimo: number;
    maximo: number | null;
  }) => void;
}) {
  return (
    <section className="rounded-lg border border-gray/20 bg-white p-4">
      <h2 className="mb-1 font-heading text-lg text-dark">
        Extras y opciones
      </h2>
      <p className="mb-3 text-xs text-gray">
        Marca un grupo como obligatorio y el PDV no dejará agregar el producto al
        carrito hasta elegir en él.
      </p>
      {producto.grupos.map((grupo) => (
        <GrupoEditor
          key={grupo.id}
          grupo={grupo}
          extrasDisponibles={extrasDisponibles}
          yaVinculados={vinculados(producto)}
          onVincular={onVincular}
        />
      ))}
      <NuevoGrupo onCrear={onCrearGrupo} />
      {producto.extras_sueltos.length > 0 && (
        <p className="mt-3 text-xs text-gray">
          Sin grupo (siempre opcionales):{" "}
          {producto.extras_sueltos.map((e) => e.nombre).join(", ")}
        </p>
      )}
    </section>
  );
}

function GrupoEditor({
  grupo,
  extrasDisponibles,
  yaVinculados,
  onVincular,
}: {
  grupo: GrupoOpcion;
  extrasDisponibles: Producto[];
  yaVinculados: string[];
  onVincular: (cuerpo: { extra_id: string; grupo_id: string }) => void;
}) {
  const disponibles = extrasDisponibles.filter((e) => !yaVinculados.includes(e.id));
  return (
    <div className="border-t border-gray/20 py-3">
      <p className="font-semibold text-dark">
        {grupo.nombre}{" "}
        <span className="text-xs font-normal text-gray">
          {grupo.minimo >= 1 ? `obligatorio · elige ${grupo.minimo}` : "opcional"}
          {grupo.maximo ? ` · hasta ${grupo.maximo}` : ""}
        </span>
      </p>
      <ul className="ml-4 list-disc text-sm text-dark">
        {grupo.extras.map((e) => (
          <li key={e.extra_id}>
            {e.nombre}
            {e.maximo ? ` (hasta ${e.maximo} por plato)` : ""}
          </li>
        ))}
      </ul>
      {disponibles.length > 0 && (
        <select
          defaultValue=""
          className="mt-2 text-sm"
          onChange={(e) => {
            if (!e.target.value) return;
            onVincular({ extra_id: e.target.value, grupo_id: grupo.id });
            e.target.value = "";
          }}
        >
          <option value="">+ Agregar extra al grupo...</option>
          {disponibles.map((e) => (
            <option key={e.id} value={e.id}>
              {e.nombre}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}

function NuevoGrupo({
  onCrear,
}: {
  onCrear: (cuerpo: {
    nombre: string;
    minimo: number;
    maximo: number | null;
  }) => void;
}) {
  const [nombre, setNombre] = useState("");
  const [obligatorio, setObligatorio] = useState(false);
  const [maximo, setMaximo] = useState("");

  return (
    <div className="mt-3 flex flex-wrap items-end gap-2 rounded bg-cream/60 p-3">
      <label className="flex flex-col gap-1 text-xs font-semibold">
        Nombre del grupo
        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          onBlur={() => setNombre((n) => aTitulo(n))}
          placeholder="Salsas"
          className="min-w-40"
        />
      </label>
      <label className="flex items-center gap-2 pb-2 text-xs font-semibold">
        <input
          type="checkbox"
          checked={obligatorio}
          onChange={(e) => setObligatorio(e.target.checked)}
        />
        Obligatorio
      </label>
      <label className="flex flex-col gap-1 text-xs font-semibold">
        Máximo
        <input
          value={maximo}
          onChange={(e) => setMaximo(e.target.value)}
          type="number"
          min={1}
          placeholder="sin tope"
          className="w-24"
        />
      </label>
      <button
        type="button"
        disabled={!nombre.trim()}
        onClick={() => {
          onCrear({
            nombre,
            // El toggle es esto: obligatorio = hay que elegir al menos uno.
            minimo: obligatorio ? 1 : 0,
            maximo: maximo ? Number(maximo) : null,
          });
          setNombre("");
          setMaximo("");
          setObligatorio(false);
        }}
        className="rounded bg-primary px-3 py-1.5 text-xs font-bold text-white disabled:opacity-50"
      >
        Crear grupo
      </button>
    </div>
  );
}

/** El precio es inmutable por lista (RN-PRC-005): corregirlo es lista nueva,
 * no edición. Por eso acá solo se puede fijar, nunca cambiar. */
function Precio({
  producto,
  listas,
  onError,
  compacto,
}: {
  producto: Producto;
  listas: ListaPrecio[];
  onError: (mensaje: string) => void;
  compacto?: boolean;
}) {
  const vigentes = listas.filter((l) => l.activa);
  const [listaId, setListaId] = useState(vigentes[0]?.id ?? "");
  const [monto, setMonto] = useState("");
  const [ok, setOk] = useState(false);

  if (vigentes.length === 0) {
    return (
      <p className="mt-3 text-xs text-gray">
        No hay lista de precios vigente para esta marca: sin precio, el producto
        no aparece en la carta.
      </p>
    );
  }

  return (
    <div className={`flex flex-wrap items-end gap-2 ${compacto ? "" : "mt-3"}`}>
      {!compacto && (
        <label className="flex flex-col gap-1 text-xs font-semibold">
          Lista de precios
          <select value={listaId} onChange={(e) => setListaId(e.target.value)}>
            {vigentes.map((l) => (
              <option key={l.id} value={l.id}>
                {l.nombre}
                {l.modalidad ? ` · ${l.modalidad}` : ""}
              </option>
            ))}
          </select>
        </label>
      )}
      <input
        value={monto}
        onChange={(e) => setMonto(e.target.value)}
        inputMode="decimal"
        placeholder="S/"
        className="w-20"
        aria-label={`Precio de ${producto.nombre}`}
      />
      <button
        type="button"
        disabled={!monto}
        onClick={async () => {
          setOk(false);
          try {
            await pedir(`/sales/listas-precio/${listaId}/precios`, {
              metodo: "POST",
              cuerpo: { producto_comercial_id: producto.id, monto },
            });
            setOk(true);
            setMonto("");
          } catch (e) {
            onError(e instanceof ErrorApi ? e.message : "No se pudo fijar el precio.");
          }
        }}
        className="rounded border border-gray px-3 py-1.5 text-xs font-semibold text-dark disabled:opacity-50"
      >
        Fijar
      </button>
      {ok && <span className="pb-2 text-xs text-primary">✓</span>}
    </div>
  );
}
