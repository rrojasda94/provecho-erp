"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  catalogoApi,
  type Articulo,
  type GrupoOpcion,
  type Producto,
  type ProductoDetalle,
  type Receta,
  type RecetaDetalle,
  type UnidadMedida,
} from "@/lib/catalogo";
import { ErrorApi } from "@/lib/cliente-api";
import {
  alternar,
  armarPartes,
  elegidosDelCamino,
  elegirEnGrupo,
  etiquetaCorta,
  faltantesDeGrupos,
  nombreReceta,
  recetasDe,
  reglaDeGrupo,
  resolverEmpaque,
  sinVincular,
  tituloDelPlato,
  type Camino,
} from "@/lib/lienzo";
import { cantidadCorta, fusionar, margen, soles } from "@/lib/nodos";
import { aTitulo } from "@/lib/texto";

/**
 * Lienzo de nodos del producto comercial: el árbol completo de lo que se
 * puede pedir, en el orden en que el sistema lo arma (RN-PRD-004).
 *
 *     producto → tamaño → combinación (sabor) → extras → restas → empaque
 *
 * Cada nodo aporta **su propia receta** y el plato es la suma. Eso no es un
 * modelo nuevo: el tamaño ya es un producto hijo (RN-COM-022) y el sabor ya
 * es una opción de grupo con receta (RN-COM-021/023). Lo que faltaba era
 * verlo junto y poder recorrerlo — armar una pizza mentalmente para saber
 * qué consume y qué margen deja obligaba a abrir cinco pantallas.
 *
 * **Acá se edita la estructura, no las cantidades.** Agregar un tamaño,
 * abrir un grupo, colgar un sabor, elegir empaque: sí. Los gramos de cada
 * receta se editan en Catálogo → Recetas, con un enlace desde cada nodo. Es
 * la corrección de ADR-023 §4: el editor de receta en dos pantallas hace
 * pensar que son dos recetas distintas.
 *
 * El panel de la derecha recalcula en cada click —receta fusionada, costo,
 * margen— sin guardar nada. Es un simulador: lo que se descuenta de verdad
 * lo calcula el servidor al confirmar la venta.
 */
export function LienzoNodos({
  inicial,
  variantesIniciales,
  recetas,
  unidades,
  extrasDisponibles,
  empaques,
}: {
  inicial: ProductoDetalle;
  variantesIniciales: ProductoDetalle[];
  recetas: Receta[];
  unidades: UnidadMedida[];
  extrasDisponibles: Producto[];
  empaques: Articulo[];
}) {
  const [padre, setPadre] = useState(inicial);
  const [variantes, setVariantes] = useState(variantesIniciales);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  // Tamaño activo y lo elegido bajo él, en UN solo estado. Cambiar de tamaño
  // cambia los grupos, los extras y lo que se puede quitar, así que la
  // selección anterior no significa nada bajo el nuevo: se reemplaza entera
  // en el mismo `set`, sin un efecto que la limpie después de pintarla.
  const [camino, setCamino] = useState<Camino>({
    activoId: variantesIniciales[0]?.id ?? inicial.id,
    elegidas: {},
    sueltos: [],
    restas: [],
  });
  const [precio, setPrecio] = useState("");
  const [modalidad, setModalidad] = useState("mesa");

  const { activoId, elegidas, sueltos, restas } = camino;
  const activo =
    [padre, ...variantes].find((n) => n.id === activoId) ?? padre;
  const irA = (id: string) =>
    setCamino({ activoId: id, elegidas: {}, sueltos: [], restas: [] });

  const recargar = useCallback(async () => {
    try {
      const fresco = await catalogoApi.producto(inicial.id);
      setPadre(fresco);
      setVariantes(
        await Promise.all(
          fresco.variantes.map((v) => catalogoApi.producto(v.id)),
        ),
      );
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo releer el producto.");
    }
  }, [inicial.id]);

  const correr = useCallback(
    async (accion: () => Promise<unknown>) => {
      setError("");
      setOcupado(true);
      try {
        await accion();
        await recargar();
      } catch (e) {
        setError(e instanceof ErrorApi ? e.message : "No se pudo guardar el cambio.");
      } finally {
        setOcupado(false);
      }
    },
    [recargar],
  );

  const elegidos = useMemo(
    () => elegidosDelCamino(activo, elegidas, sueltos),
    [activo, elegidas, sueltos],
  );
  const cache = useCacheDeRecetas(
    useMemo(() => recetasDe(activo, elegidos), [activo, elegidos]),
    setError,
  );

  const partes = useMemo(
    () => armarPartes(activo, padre.nombre, elegidos, cache),
    [activo, padre.nombre, elegidos, cache],
  );
  const fusion = useMemo(() => fusionar(partes, restas), [partes, restas]);

  const { empaque, aplica: empaqueAplica, costo: costoEmpaque } =
    resolverEmpaque(activo, empaques, modalidad);
  const costoTotal = fusion.costo + costoEmpaque;

  const enGrupo = (grupo: GrupoOpcion, extraId: string) =>
    setCamino((previo) => elegirEnGrupo(previo, grupo, extraId));

  const alternarSuelto = (id: string) =>
    setCamino((p) => ({ ...p, sueltos: alternar(p.sueltos, id) }));
  const alternarResta = (id: string) =>
    setCamino((p) => ({ ...p, restas: alternar(p.restas, id) }));

  return (
    <div className="flex flex-col gap-4">
      <header>
        <Link
          href={`/catalogo/productos/${padre.id}`}
          className="text-sm text-gray hover:text-primary"
        >
          ← Ficha de {padre.nombre}
        </Link>
        <h1 className="mt-2 font-heading text-xl italic uppercase text-dark">
          {padre.nombre} · Nodos
        </h1>
        <p className="mt-1 max-w-3xl text-xs text-gray">
          El árbol de lo que se puede pedir, en el orden en que el sistema lo
          arma: tamaño → sabor → extras → restas → empaque. Toca los nodos para
          armar un plato y mira a la derecha qué lleva, qué cuesta y qué deja.
          Los gramos de cada receta se editan en{" "}
          <Link href="/catalogo/recetas" className="text-primary hover:underline">
            Catálogo → Recetas
          </Link>
          .
        </p>
      </header>

      {error && (
        <p role="alert" className="text-sm font-semibold text-secondary">
          {error}
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div
          className={`overflow-x-auto rounded-lg border border-gray/20 bg-white p-4 ${
            ocupado ? "opacity-60" : ""
          }`}
        >
          <TierTamanos
            padre={padre}
            variantes={variantes}
            activoId={activoId}
            recetas={recetas}
            unidades={unidades}
            onIrA={irA}
            onCorrer={correr}
          />
          <TiersDeOpciones
            activo={activo}
            recetas={recetas}
            elegidas={elegidas}
            sueltos={sueltos}
            extrasDisponibles={extrasDisponibles}
            onElegirEnGrupo={enGrupo}
            onAlternarSuelto={alternarSuelto}
            onCorrer={correr}
          />
          <Tier
            titulo="Restas"
            ayuda="Lo que el cliente puede pedir sin. No cambia el precio; sí deja de descontarse"
          >
            {fusion.quitables.length === 0 && (
              <p className="text-xs text-gray">
                Elige un tamaño con receta para ver qué se puede quitar.
              </p>
            )}
            {fusion.quitables.map((q) => (
              <Nodo
                key={q.articuloId}
                activo={restas.includes(q.articuloId)}
                variante="resta"
                titulo={`sin ${q.articulo}`}
                onClick={() => alternarResta(q.articuloId)}
              />
            ))}
          </Tier>
          <Tier
            titulo="Empaque"
            ayuda="Se descuenta solo en las modalidades marcadas (RN-EMP-003)"
          >
            <Empaque
              nodo={activo}
              empaques={empaques}
              onGuardar={(cuerpo) =>
                correr(() => catalogoApi.editarProducto(activo.id, cuerpo))
              }
            />
          </Tier>
        </div>

        <PanelVivo
          titulo={tituloDelPlato(activo, padre, partes)}
          fusion={fusion}
          empaque={empaque}
          empaqueAplica={empaqueAplica}
          costoTotal={costoTotal}
          modalidad={modalidad}
          onModalidad={setModalidad}
          precio={precio}
          onPrecio={setPrecio}
          faltantes={faltantesDeGrupos(activo, elegidas)}
        />
      </div>
    </div>
  );
}

/** Producto + tamaños: el tronco del árbol y sus primeras ramas. */
function TierTamanos({
  padre,
  variantes,
  activoId,
  recetas,
  unidades,
  onIrA,
  onCorrer,
}: {
  padre: ProductoDetalle;
  variantes: ProductoDetalle[];
  activoId: string;
  recetas: Receta[];
  unidades: UnidadMedida[];
  onIrA: (id: string) => void;
  onCorrer: (accion: () => Promise<unknown>) => Promise<void>;
}) {
  // Un producto sin tamaños es su propio nodo: "simple" es el árbol de un
  // solo tronco, no otro caso a modelar.
  const ramas: ProductoDetalle[] = variantes.length ? variantes : [padre];
  return (
    <>
      <Tier titulo="Producto">
        <Nodo activo titulo={padre.nombre} pie={padre.id_interno} />
      </Tier>
      <Tier titulo="Tamaño" ayuda="Cada tarjeta es obligatoria en el PDV">
        {ramas.map((v) => (
          <Nodo
            key={v.id}
            activo={activoId === v.id}
            titulo={
              v.id === padre.id ? "Único" : etiquetaCorta(v.nombre, padre.nombre)
            }
            pie={nombreReceta(recetas, v.receta_id)}
            onClick={() => onIrA(v.id)}
            enlaceReceta={v.receta_id}
          />
        ))}
        <NuevoTamano
          padre={padre}
          recetas={recetas}
          unidades={unidades}
          onCorrer={onCorrer}
        />
      </Tier>
    </>
  );
}

/** Los grupos del tamaño activo (el sabor es uno de ellos) y sus extras
 * sueltos. Es la parte del árbol que cambia al moverse de tamaño. */
function TiersDeOpciones({
  activo,
  recetas,
  elegidas,
  sueltos,
  extrasDisponibles,
  onElegirEnGrupo,
  onAlternarSuelto,
  onCorrer,
}: {
  activo: ProductoDetalle;
  recetas: Receta[];
  elegidas: Record<string, string[]>;
  sueltos: string[];
  extrasDisponibles: Producto[];
  onElegirEnGrupo: (grupo: GrupoOpcion, extraId: string) => void;
  onAlternarSuelto: (extraId: string) => void;
  onCorrer: (accion: () => Promise<unknown>) => Promise<void>;
}) {
  const disponibles = sinVincular(extrasDisponibles, activo);
  const quitar = (extraId: string) =>
    onCorrer(() => catalogoApi.desvincularExtra(activo.id, extraId));

  return (
    <>
      {activo.grupos.map((grupo) => (
        <Tier
          key={grupo.id}
          titulo={grupo.nombre}
          ayuda={reglaDeGrupo(grupo)}
          onBorrar={() =>
            onCorrer(() => catalogoApi.borrarGrupo(activo.id, grupo.id))
          }
        >
          {grupo.extras.map((extra) => (
            <Nodo
              key={extra.extra_id}
              activo={(elegidas[grupo.id] ?? []).includes(extra.extra_id)}
              titulo={extra.nombre}
              pie={nombreReceta(recetas, extra.receta_id)}
              onClick={() => onElegirEnGrupo(grupo, extra.extra_id)}
              enlaceReceta={extra.receta_id}
              onQuitar={() => quitar(extra.extra_id)}
            />
          ))}
          <AgregarOpcion
            disponibles={disponibles}
            onElegir={(extraId) =>
              onCorrer(() =>
                catalogoApi.vincularExtra(activo.id, {
                  extra_id: extraId,
                  grupo_id: grupo.id,
                }),
              )
            }
          />
        </Tier>
      ))}

      <Tier
        titulo="Extras sueltos"
        ayuda="Siempre opcionales, sin mínimo que cumplir"
      >
        {activo.extras_sueltos.map((extra) => (
          <Nodo
            key={extra.extra_id}
            activo={sueltos.includes(extra.extra_id)}
            titulo={extra.nombre}
            pie={nombreReceta(recetas, extra.receta_id)}
            onClick={() => onAlternarSuelto(extra.extra_id)}
            enlaceReceta={extra.receta_id}
            onQuitar={() => quitar(extra.extra_id)}
          />
        ))}
        <AgregarOpcion
          disponibles={disponibles}
          onElegir={(extraId) =>
            onCorrer(() =>
              catalogoApi.vincularExtra(activo.id, { extra_id: extraId }),
            )
          }
        />
        <NuevoGrupo
          onCrear={(cuerpo) =>
            onCorrer(() => catalogoApi.crearGrupo(activo.id, cuerpo))
          }
        />
      </Tier>
    </>
  );
}

/** Trae y memoriza las recetas que el camino elegido necesita.
 *
 * Perezoso a propósito: una pizza con 3 tamaños y 8 sabores son 27 recetas y
 * traerlas todas al abrir la pantalla para mostrar una es trabajo tirado.
 * Se piden cuando el nodo entra al plato y quedan cacheadas. */
function useCacheDeRecetas(
  ids: string[],
  onError: (mensaje: string) => void,
): Record<string, RecetaDetalle> {
  const [cache, setCache] = useState<Record<string, RecetaDetalle>>({});
  const clave = ids.join(",");

  useEffect(() => {
    const faltan = clave.split(",").filter((id) => id && !cache[id]);
    if (faltan.length === 0) return;
    let vigente = true;
    Promise.all(faltan.map((id) => catalogoApi.receta(id)))
      .then((traidas) => {
        if (!vigente) return;
        setCache((previo) => ({
          ...previo,
          ...Object.fromEntries(traidas.map((r) => [r.id, r])),
        }));
      })
      .catch((e) =>
        onError(
          e instanceof ErrorApi ? e.message : "No se pudo leer una receta.",
        ),
      );
    return () => {
      vigente = false;
    };
    // `cache` fuera de las dependencias a propósito: entra en el efecto solo
    // para saber qué falta, y listarlo lo re-dispararía con cada llegada.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave, onError]);

  return cache;
}

/** Una fila del árbol, con el conector que la cuelga de la de arriba. */
function Tier({
  titulo,
  ayuda,
  onBorrar,
  children,
}: {
  titulo: string;
  ayuda?: string;
  onBorrar?: () => void;
  children: React.ReactNode;
}) {
  return (
    <section className="pt-6">
      <div className="mb-2 flex items-baseline gap-2">
        <h2 className="font-heading text-xs uppercase tracking-wide text-dark">
          {titulo}
        </h2>
        {ayuda && <span className="text-[11px] text-gray">{ayuda}</span>}
        {onBorrar && (
          <button
            type="button"
            onClick={onBorrar}
            className="text-[11px] text-secondary hover:underline"
            title="Borra el grupo. Sus opciones siguen ofreciéndose, ya sin mínimo"
          >
            borrar grupo
          </button>
        )}
      </div>
      {/* Conectores en CSS, no SVG medido en JS: el árbol es por filas, así
          que un riel sobre la fila y un tick hacia cada nodo dicen lo mismo
          que un cálculo de coordenadas, y siguen cuadrando al cambiar el
          ancho. `w-fit` es lo que hace que el riel termine en el último
          nodo en vez de seguir hasta el borde del panel. */}
      <div className="relative flex w-fit flex-wrap items-stretch gap-2">
        <span
          aria-hidden
          className="pointer-events-none absolute inset-x-14 top-0 h-px bg-gray/30"
        />
        {/* Tronco: baja del tier anterior hasta el arranque del riel. */}
        <span
          aria-hidden
          className="pointer-events-none absolute -top-6 left-14 h-6 w-px bg-gray/30"
        />
        {children}
      </div>
    </section>
  );
}

function Nodo({
  titulo,
  pie,
  activo,
  variante,
  onClick,
  onQuitar,
  enlaceReceta,
}: {
  titulo: string;
  pie?: string | null;
  activo?: boolean;
  variante?: "resta";
  onClick?: () => void;
  onQuitar?: () => void;
  enlaceReceta?: string | null;
}) {
  const base =
    "group relative min-w-28 rounded-lg border px-3 py-2 text-left transition";
  const color = activo
    ? variante === "resta"
      ? "border-secondary bg-secondary/10 text-secondary"
      : "border-primary bg-primary/10 text-dark"
    : "border-gray/30 bg-white text-dark hover:border-primary/60";

  return (
    <div className="relative pt-5">
      {/* Tick que cuelga este nodo del riel de su fila. */}
      <span
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-0 h-5 w-px bg-gray/30"
      />
      <button
        type="button"
        onClick={onClick}
        disabled={!onClick}
        aria-pressed={onClick ? Boolean(activo) : undefined}
        className={`${base} ${color} ${onClick ? "" : "cursor-default"}`}
      >
        <span className="block text-sm font-semibold">{titulo}</span>
        {pie && <span className="mt-0.5 block text-[11px] text-gray">{pie}</span>}
      </button>
      {(onQuitar || enlaceReceta) && (
        <div className="mt-1 flex justify-center gap-2 text-[11px] opacity-0 transition group-hover:opacity-100 focus-within:opacity-100">
          {enlaceReceta && (
            <Link
              href={`/catalogo/recetas/${enlaceReceta}`}
              className="text-primary hover:underline"
            >
              receta
            </Link>
          )}
          {onQuitar && (
            <button
              type="button"
              onClick={onQuitar}
              className="text-secondary hover:underline"
              title="Deja de ofrecerlo en este producto. El extra no se borra"
            >
              quitar
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function AgregarOpcion({
  disponibles,
  onElegir,
}: {
  disponibles: Producto[];
  onElegir: (extraId: string) => void;
}) {
  if (disponibles.length === 0) return null;
  return (
    <div className="relative pt-5">
      <select
        value=""
        aria-label="Agregar opción"
        className="mt-0 min-w-40 border-dashed text-xs"
        onChange={(e) => e.target.value && onElegir(e.target.value)}
      >
        <option value="">+ opción...</option>
        {disponibles.map((p) => (
          <option key={p.id} value={p.id}>
            {p.nombre}
          </option>
        ))}
      </select>
    </div>
  );
}

function NuevoTamano({
  padre,
  recetas,
  unidades,
  onCorrer,
}: {
  padre: ProductoDetalle;
  recetas: Receta[];
  unidades: UnidadMedida[];
  onCorrer: (accion: () => Promise<unknown>) => Promise<void>;
}) {
  const [abierto, setAbierto] = useState(false);
  const [nombre, setNombre] = useState("");
  const [idInterno, setIdInterno] = useState("");
  const [recetaId, setRecetaId] = useState("");

  if (padre.receta_id) {
    return (
      <p className="self-center pt-5 text-[11px] text-gray">
        Tiene receta propia: quítasela en la ficha para venderlo por tamaños.
      </p>
    );
  }

  if (!abierto) {
    return (
      <div className="pt-5">
        <button
          type="button"
          onClick={() => setAbierto(true)}
          className="min-w-28 rounded-lg border border-dashed border-gray/50 px-3 py-2 text-sm text-gray hover:border-primary hover:text-primary"
        >
          + tamaño
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-end gap-2 rounded-lg bg-cream/60 p-2 pt-5">
      <label className="flex flex-col gap-1 text-[11px] font-semibold">
        Tarjeta
        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          onBlur={() => setNombre((n) => aTitulo(n))}
          placeholder="Familiar"
          className="w-28"
        />
      </label>
      <label className="flex flex-col gap-1 text-[11px] font-semibold">
        Código
        <input
          value={idInterno}
          onChange={(e) => setIdInterno(e.target.value.slice(0, 4))}
          placeholder="PZPF"
          className="w-16"
        />
      </label>
      <label className="flex flex-col gap-1 text-[11px] font-semibold">
        Receta
        <select
          value={recetaId}
          onChange={(e) => setRecetaId(e.target.value)}
          className="min-w-40"
        >
          <option value="">Crear una vacía</option>
          {recetas.map((r) => (
            <option key={r.id} value={r.id}>
              {r.nombre}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        disabled={!nombre.trim() || !idInterno}
        className="rounded bg-primary px-3 py-1.5 text-xs font-bold text-white disabled:opacity-50"
        onClick={() =>
          onCorrer(async () => {
            // Sin receta elegida se crea una vacía: la variante no puede
            // existir sin receta y mandar al usuario a otro módulo antes de
            // poder crear el nodo era peor que crearla en blanco.
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
            setAbierto(false);
          })
        }
      >
        Crear
      </button>
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
  const [abierto, setAbierto] = useState(false);
  const [nombre, setNombre] = useState("");
  const [obligatorio, setObligatorio] = useState(true);
  const [unaSola, setUnaSola] = useState(true);

  if (!abierto) {
    return (
      <div className="pt-5">
        <button
          type="button"
          onClick={() => setAbierto(true)}
          className="min-w-28 rounded-lg border border-dashed border-gray/50 px-3 py-2 text-sm text-gray hover:border-primary hover:text-primary"
        >
          + grupo
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-end gap-2 rounded-lg bg-cream/60 p-2 pt-5">
      <label className="flex flex-col gap-1 text-[11px] font-semibold">
        Grupo
        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          onBlur={() => setNombre((n) => aTitulo(n))}
          placeholder="Sabor"
          className="w-32"
        />
      </label>
      <label className="flex items-center gap-1 pb-2 text-[11px] font-semibold">
        <input
          type="checkbox"
          checked={obligatorio}
          onChange={(e) => setObligatorio(e.target.checked)}
        />
        Obligatorio
      </label>
      <label className="flex items-center gap-1 pb-2 text-[11px] font-semibold">
        <input
          type="checkbox"
          checked={unaSola}
          onChange={(e) => setUnaSola(e.target.checked)}
        />
        Una sola
      </label>
      <button
        type="button"
        disabled={!nombre.trim()}
        className="rounded bg-primary px-3 py-1.5 text-xs font-bold text-white disabled:opacity-50"
        onClick={() => {
          // Un grupo de sabores es esto: obligatorio (mínimo 1) y de una
          // sola opción (máximo 1). No hace falta un tipo de grupo aparte.
          onCrear({
            nombre,
            minimo: obligatorio ? 1 : 0,
            maximo: unaSola ? 1 : null,
          });
          setNombre("");
          setAbierto(false);
        }}
      >
        Crear
      </button>
    </div>
  );
}

const MODALIDADES = ["mesa", "takeout", "delivery"];

function Empaque({
  nodo,
  empaques,
  onGuardar,
}: {
  nodo: ProductoDetalle;
  empaques: Articulo[];
  onGuardar: (cuerpo: {
    empaque_id: string | null;
    modalidades_empaque: string[] | null;
  }) => void;
}) {
  const marcadas = nodo.modalidades_empaque ?? [];
  return (
    <div className="relative flex flex-wrap items-center gap-3 pt-5">
      <span
        aria-hidden
        className="pointer-events-none absolute left-14 top-0 h-4 w-px bg-gray/30"
      />
      <select
        value={nodo.empaque_id ?? ""}
        aria-label="Artículo de empaque"
        className="min-w-44 text-xs"
        onChange={(e) =>
          onGuardar({
            empaque_id: e.target.value || null,
            modalidades_empaque: e.target.value ? marcadas : null,
          })
        }
      >
        <option value="">Sin empaque</option>
        {empaques.map((a) => (
          <option key={a.id} value={a.id}>
            {a.nombre}
          </option>
        ))}
      </select>
      {nodo.empaque_id &&
        MODALIDADES.map((m) => (
          <label key={m} className="flex items-center gap-1 text-xs">
            <input
              type="checkbox"
              checked={marcadas.includes(m)}
              onChange={(e) =>
                onGuardar({
                  empaque_id: nodo.empaque_id,
                  modalidades_empaque: e.target.checked
                    ? [...marcadas, m]
                    : marcadas.filter((x) => x !== m),
                })
              }
            />
            {m}
          </label>
        ))}
    </div>
  );
}

/** Lo que resulta del camino elegido: qué lleva, qué cuesta, qué deja. */
function PanelVivo({
  titulo,
  fusion,
  empaque,
  empaqueAplica,
  costoTotal,
  modalidad,
  onModalidad,
  precio,
  onPrecio,
  faltantes,
}: {
  titulo: string;
  fusion: ReturnType<typeof fusionar>;
  empaque: Articulo | null;
  empaqueAplica: boolean;
  costoTotal: number;
  modalidad: string;
  onModalidad: (m: string) => void;
  precio: string;
  onPrecio: (p: string) => void;
  faltantes: string[];
}) {
  const valorPrecio = Number(precio) || 0;
  const { monto, pct } = margen(valorPrecio, costoTotal);

  return (
    <aside className="h-fit rounded-lg border border-gray/20 bg-white p-4 lg:sticky lg:top-4">
      <h2 className="font-heading text-sm italic uppercase text-dark">
        Plato armado
      </h2>
      <p className="mt-0.5 text-xs text-gray">{titulo}</p>

      {faltantes.length > 0 && (
        <p className="mt-2 rounded bg-secondary/10 px-2 py-1 text-[11px] text-secondary">
          Falta elegir: {faltantes.join(", ")}. El PDV no dejaría agregarlo al
          carrito así.
        </p>
      )}

      <table className="mt-3 w-full text-xs">
        <tbody>
          {fusion.lineas.length === 0 && (
            <tr>
              <td className="py-2 text-gray">
                Nada todavía: elige un tamaño con receta.
              </td>
            </tr>
          )}
          {fusion.lineas.map((l) => (
            <tr
              key={l.articuloId}
              className={`border-t border-gray/10 ${
                l.quitado ? "text-gray line-through" : ""
              }`}
            >
              <td className="py-1 pr-2">
                {l.articulo}
                <span className="block text-[10px] text-gray no-underline">
                  {l.origen}
                </span>
              </td>
              <td className="py-1 pr-2 text-right whitespace-nowrap">
                {cantidadCorta(l.cantidad)} {l.unidad}
              </td>
              <td className="py-1 text-right whitespace-nowrap">
                {soles(l.costo)}
              </td>
            </tr>
          ))}
          {empaque && (
            <tr
              className={`border-t border-gray/10 ${
                empaqueAplica ? "" : "text-gray line-through"
              }`}
            >
              <td className="py-1 pr-2">
                {empaque.nombre}
                <span className="block text-[10px] text-gray no-underline">
                  Empaque
                </span>
              </td>
              <td className="py-1 pr-2 text-right">1</td>
              <td className="py-1 text-right whitespace-nowrap">
                {soles(Number(empaque.costo_promedio))}
              </td>
            </tr>
          )}
        </tbody>
      </table>

      <label className="mt-3 flex items-center justify-between gap-2 text-xs">
        Modalidad
        <select
          value={modalidad}
          onChange={(e) => onModalidad(e.target.value)}
          className="text-xs"
        >
          {MODALIDADES.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </label>

      <dl className="mt-3 space-y-1 border-t border-gray/20 pt-3 text-xs">
        <Fila termino="Costo del plato" valor={soles(costoTotal)} fuerte />
        {fusion.costoQuitado > 0 && (
          <Fila
            termino="No se descuenta (restas)"
            valor={soles(fusion.costoQuitado)}
          />
        )}
      </dl>

      <label className="mt-3 flex items-center justify-between gap-2 text-xs font-semibold">
        Precio de venta
        <input
          value={precio}
          onChange={(e) => onPrecio(e.target.value)}
          inputMode="decimal"
          placeholder="S/"
          className="w-24 text-right"
        />
      </label>
      <p className="mt-1 text-[10px] text-gray">
        Se teclea acá: el precio que cobra el PDV sale de la lista vigente de
        la sucursal (RN-PRC-003), no de esta pantalla.
      </p>

      {valorPrecio > 0 && (
        <dl className="mt-2 space-y-1 border-t border-gray/20 pt-2 text-xs">
          <Fila termino="Margen" valor={soles(monto)} fuerte />
          <Fila
            termino="Margen %"
            valor={pct === null ? "—" : `${pct.toFixed(1)} %`}
          />
        </dl>
      )}
    </aside>
  );
}

function Fila({
  termino,
  valor,
  fuerte,
}: {
  termino: string;
  valor: string;
  fuerte?: boolean;
}) {
  return (
    <div className="flex justify-between">
      <dt className="text-gray">{termino}</dt>
      <dd className={fuerte ? "font-bold text-dark" : "text-dark"}>{valor}</dd>
    </div>
  );
}
