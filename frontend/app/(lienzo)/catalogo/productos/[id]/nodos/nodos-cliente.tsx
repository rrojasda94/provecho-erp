"use client";

import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import { useRouter } from "next/navigation";
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
  armarGrafo,
  armarPartes,
  elegidosDelCamino,
  elegirEnGrupo,
  faltantesDeGrupos,
  recetasDelLienzo,
  resolverEmpaque,
  sinVincular,
  tituloDelPlato,
  type Camino,
  type Grafo,
} from "@/lib/lienzo";
import { fusionar, soles } from "@/lib/nodos";

import { Barra } from "./barra";
import { Inspector } from "./inspector";
import { TIPOS_NODO, type DatosNodo } from "./nodo";
import { RecetaDelNodo } from "./receta-nodo";
import { conectar, desconectar } from "./conexiones";

import "@xyflow/react/dist/base.css";

/**
 * Lienzo de nodos del producto comercial (ADR-035).
 *
 * El árbol completo de lo que se puede pedir, en el orden en que el sistema
 * lo arma (RN-PRD-004), pero de izquierda a derecha y sobre un canvas que se
 * navega:
 *
 *     producto → tamaño → combinación (sabor) → extras → restas → empaque → PLATO
 *
 * Cada nodo aporta **su propia receta** y el plato es la suma. Eso no es un
 * modelo nuevo: el tamaño ya era un producto hijo (RN-COM-022) y el sabor ya
 * era una opción de grupo con receta (RN-COM-021/023). Lo que faltaba era
 * verlo junto y poder recorrerlo.
 *
 * **Se edita la estructura, no las cantidades.** Los gramos de cada receta
 * viven en Catálogo → Recetas, con enlace desde cada nodo: el editor de
 * receta en dos pantallas hace pensar que son dos recetas distintas, y ya se
 * reportó una vez (ADR-023 §4).
 *
 * El inspector recalcula en cada click —receta fusionada, costo, margen— sin
 * guardar nada. Es un simulador: lo que se descuenta de verdad lo calcula el
 * servidor al confirmar la venta.
 *
 * Los nodos se pueden arrastrar y **no se guarda dónde quedaron**: el orden
 * lo dicta RN-PRD-004 y mover uno no cambia nada del producto. Cualquier
 * cambio de estructura recoloca todo.
 */
export function LienzoNodos(props: Props) {
  return (
    <ReactFlowProvider>
      <Lienzo {...props} />
    </ReactFlowProvider>
  );
}

type Props = {
  inicial: ProductoDetalle;
  variantesIniciales: ProductoDetalle[];
  recetas: Receta[];
  unidades: UnidadMedida[];
  extrasDisponibles: Producto[];
  empaques: Articulo[];
};

function Lienzo({
  inicial,
  variantesIniciales,
  recetas,
  unidades,
  extrasDisponibles,
  empaques,
}: Props) {
  const router = useRouter();
  const [padre, setPadre] = useState(inicial);
  const [variantes, setVariantes] = useState(variantesIniciales);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [plegado, setPlegado] = useState(false);

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
  // Qué nodo se está inspeccionando. Es distinto de "qué nodo está en el
  // plato": tocar un sabor lo mete al plato Y abre su receta, que es lo que
  // uno quiere al estar armando la carta.
  const [seleccion, setSeleccion] = useState<DatosNodo | null>(null);
  const [verEditor, setVerEditor] = useState(false);

  const activo =
    [padre, ...variantes].find((n) => n.id === camino.activoId) ?? padre;

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
        // `recargar` reelee el producto, pero la lista de recetas la trae el
        // server component: sin esto, un tamaño o una opción recién creados
        // muestran "receta" en el pie en vez del nombre de la suya, hasta
        // que alguien recargue la página a mano.
        router.refresh();
      } catch (e) {
        setError(e instanceof ErrorApi ? e.message : "No se pudo guardar el cambio.");
      } finally {
        setOcupado(false);
      }
    },
    [recargar, router],
  );

  const elegidos = useMemo(
    () => elegidosDelCamino(activo, camino.elegidas, camino.sueltos),
    [activo, camino.elegidas, camino.sueltos],
  );
  const inspeccionada = seleccion?.recetaId ?? null;
  const idsDeRecetas = useMemo(
    () => recetasDelLienzo(activo, elegidos, inspeccionada),
    [activo, elegidos, inspeccionada],
  );
  const [cache, setCache] = useCacheDeRecetas(idsDeRecetas, setError);

  const partes = useMemo(
    () => armarPartes(activo, padre.nombre, elegidos, cache),
    [activo, padre.nombre, elegidos, cache],
  );
  const fusion = useMemo(
    () => fusionar(partes, camino.restas),
    [partes, camino.restas],
  );

  const { empaque, aplica: empaqueAplica, costo: costoEmpaque } =
    resolverEmpaque(activo, empaques, modalidad);
  const costoTotal = fusion.costo + costoEmpaque;

  const acciones = useMemo(
    () => ({
      irA: (id: string) =>
        setCamino({ activoId: id, elegidas: {}, sueltos: [], restas: [] }),
      enGrupo: (grupo: GrupoOpcion, extraId: string) =>
        setCamino((previo) => elegirEnGrupo(previo, grupo, extraId)),
      suelto: (id: string) =>
        setCamino((p) => ({ ...p, sueltos: alternar(p.sueltos, id) })),
      resta: (id: string) =>
        setCamino((p) => ({ ...p, restas: alternar(p.restas, id) })),
      quitarExtra: (extraId: string) =>
        correr(() => catalogoApi.desvincularExtra(activo.id, extraId)),
      borrarGrupo: (grupoId: string) =>
        correr(() => catalogoApi.borrarGrupo(activo.id, grupoId)),
    }),
    [activo.id, correr],
  );

  const disponibles = useMemo(
    () => sinVincular(extrasDisponibles, activo),
    [extrasDisponibles, activo],
  );

  const grafo = useMemo(
    () =>
      armarGrafo({
        padre,
        variantes,
        activo,
        camino,
        recetas,
        quitables: fusion.quitables,
        empaques,
        modalidad,
        disponibles,
      }),
    [padre, variantes, activo, camino, recetas, fusion.quitables, empaques,
     modalidad, disponibles],
  );

  const { nodos, aristas } = useMemo(
    () => aReactFlow(grafo, activo, acciones, soles(costoTotal)),
    [grafo, activo, acciones, costoTotal],
  );

  return (
    <div className="lienzo">
      <Barra
        padre={padre}
        activo={activo}
        recetas={recetas}
        unidades={unidades}
        extrasDisponibles={extrasDisponibles}
        empaques={empaques}
        error={error}
        onCorrer={correr}
      />

      <Canvas
        nodos={nodos}
        aristas={aristas}
        ocupado={ocupado}
        onSeleccion={(d) => {
          setSeleccion(d);
          if (d?.recetaId) setVerEditor(true);
        }}
        onConectar={(desde, hasta) =>
          correr(() => conectar(activo.id, desde, hasta))
        }
        onDesconectar={(desde, hasta) =>
          correr(() => desconectar(activo.id, desde, hasta))
        }
      />

      <Inspector
        titulo={tituloDelPlato(activo, padre, partes)}
        fusion={fusion}
        empaque={empaque}
        empaqueAplica={empaqueAplica}
        costoTotal={costoTotal}
        modalidad={modalidad}
        onModalidad={setModalidad}
        precio={precio}
        onPrecio={setPrecio}
        faltantes={faltantesDeGrupos(activo, camino.elegidas)}
        plegado={plegado}
        onPlegar={() => setPlegado((p) => !p)}
        nodoTitulo={seleccion?.titulo ?? null}
        verEditor={verEditor}
        onVerEditor={setVerEditor}
        editor={
          <EditorDeNodo
            seleccion={seleccion}
            cache={cache}
            articulos={empaques}
            onActualizada={setCache}
            onError={setError}
          />
        }
      />
    </div>
  );
}

/** La receta del nodo inspeccionado. Devuelve `null` sin nodo: el inspector
 * usa eso para no mostrar la pestaña. */
function EditorDeNodo({
  seleccion,
  cache,
  articulos,
  onActualizada,
  onError,
}: {
  seleccion: DatosNodo | null;
  cache: Record<string, RecetaDetalle>;
  articulos: Articulo[];
  onActualizada: React.Dispatch<
    React.SetStateAction<Record<string, RecetaDetalle>>
  >;
  onError: (mensaje: string) => void;
}) {
  if (!seleccion) return null;
  return (
    <RecetaDelNodo
      titulo={seleccion.titulo}
      receta={seleccion.recetaId ? (cache[seleccion.recetaId] ?? null) : null}
      articulos={articulos}
      onActualizada={(r) => onActualizada((p) => ({ ...p, [r.id]: r }))}
      onError={onError}
    />
  );
}

/**
 * El canvas propiamente dicho.
 *
 * `useNodesState` mantiene lo que el usuario arrastró; el efecto lo reemplaza
 * cuando el grafo cambia. Por eso mover un nodo dura hasta el próximo cambio
 * de estructura: es la consecuencia aceptada de no persistir posiciones
 * (ADR-035).
 *
 * `fitView` corre al montar y a pedido, nunca en cada cambio: reencuadrar
 * mientras alguien está tocando nodos les mueve el objetivo debajo del dedo.
 */
function Canvas({
  nodos,
  aristas,
  ocupado,
  onSeleccion,
  onConectar,
  onDesconectar,
}: {
  nodos: Node[];
  aristas: Edge[];
  ocupado: boolean;
  onSeleccion: (d: DatosNodo | null) => void;
  onConectar: (desde: string, hasta: string) => void;
  onDesconectar: (desde: string, hasta: string) => void;
}) {
  const [pintados, setPintados, onNodesChange] = useNodesState(nodos);
  const { fitView, getZoom } = useReactFlow();

  useEffect(() => {
    setPintados(nodos);
  }, [nodos, setPintados]);

  // El foco manda la vista, pero **solo si el nodo quedó fuera de cuadro**:
  // en un lienzo con zoom, tabular a algo invisible deja al teclado operando
  // a ciegas. Recentrar en cada foco sería peor —el grafo saltaría con cada
  // Tab—, y por eso tampoco se acerca: conserva el zoom actual.
  const alFoco = useCallback(
    (e: React.FocusEvent<HTMLDivElement>) => {
      const caja = e.currentTarget.getBoundingClientRect();
      const nodo = e.target.closest<HTMLElement>(".react-flow__node");
      if (!nodo) return;
      const suya = nodo.getBoundingClientRect();
      const dentro =
        suya.left >= caja.left &&
        suya.right <= caja.right &&
        suya.top >= caja.top &&
        suya.bottom <= caja.bottom;
      if (dentro) return;
      const zoom = getZoom();
      fitView({
        nodes: [{ id: nodo.dataset.id as string }],
        duration: 200,
        maxZoom: zoom,
        minZoom: zoom,
      });
    },
    [fitView, getZoom],
  );

  return (
    <div
      className="lienzo-canvas"
      style={{ opacity: ocupado ? 0.6 : 1 }}
      onFocus={alFoco}
    >
      <ReactFlow
        nodes={pintados}
        edges={aristas}
        onNodesChange={onNodesChange}
        nodeTypes={TIPOS_NODO}
        colorMode="dark"
        fitView
        // Sin tope de acercamiento el encuadre inicial deja el texto de los
        // nodos ilegible en un grafo chico; con tope, un grafo grande entra
        // igual porque `fitView` solo aleja.
        fitViewOptions={{ padding: 0.14, maxZoom: 1 }}
        minZoom={0.25}
        maxZoom={1.75}
        // Se cablea, pero solo lo que el dominio admite: `conexiones.ts`
        // rechaza cualquier par que no sea colgar un extra, y lo dice.
        nodesConnectable
        onConnect={(c) => onConectar(c.source, c.target)}
        // `Supr` además de `Backspace` (el default): en una caja con teclado
        // numérico `Supr` es la tecla que se busca para borrar.
        deleteKeyCode={["Delete", "Backspace"]}
        onEdgesDelete={(ids) =>
          ids.forEach((e) => onDesconectar(e.source, e.target))
        }
        // `onNodeClick` y no `onSelectionChange`: la selección de react-flow
        // vive DENTRO de cada nodo del array, y este lienzo reemplaza el
        // array entero cada vez que cambia el camino — la marca se perdía en
        // el mismo click que la ponía.
        onNodeClick={(_, n) => onSeleccion(n.data as DatosNodo)}
        onPaneClick={() => onSeleccion(null)}
        proOptions={{ hideAttribution: false }}
      >
        <Background variant={BackgroundVariant.Dots} gap={22} size={1} />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable />
      </ReactFlow>
    </div>
  );
}

type Acciones = {
  irA: (id: string) => void;
  enGrupo: (grupo: GrupoOpcion, extraId: string) => void;
  suelto: (id: string) => void;
  resta: (id: string) => void;
  quitarExtra: (extraId: string) => void;
  borrarGrupo: (grupoId: string) => void;
};

/** El "quitar" de cada nodo, o nada si ese tipo no se retira. Lo que se
 * retira no es lo mismo en cada uno: la opción se **desvincula** (el extra
 * sigue existiendo con su receta y su precio) y el grupo se **borra**,
 * soltando sus opciones, que pasan a ofrecerse sin mínimo. */
function alQuitar(
  nodo: Grafo["nodos"][number],
  acc: Acciones,
): Pick<DatosNodo, "onQuitar" | "quitarAria"> {
  const ref = nodo.datos.refId;
  if (!ref) return {};
  if (nodo.tipo === "opcion") {
    return {
      onQuitar: () => acc.quitarExtra(ref),
      quitarAria: "Deja de ofrecerlo en este producto. El extra no se borra",
    };
  }
  if (nodo.tipo === "grupo") {
    return {
      onQuitar: () => acc.borrarGrupo(ref),
      quitarAria: "Borra el grupo. Sus opciones siguen ofreciéndose, ya sin mínimo",
    };
  }
  return {};
}

/** Qué hace un click sobre cada tipo de nodo. Tabla en vez de cadena de
 * ternarios: la complejidad de una búsqueda en `Record` es 1. */
function alTocar(
  nodo: Grafo["nodos"][number],
  activo: ProductoDetalle,
  acc: Acciones,
): (() => void) | undefined {
  const ref = nodo.datos.refId;
  if (!ref) return undefined;
  if (nodo.tipo === "tamano") return () => acc.irA(ref);
  if (nodo.tipo === "resta") return () => acc.resta(ref);
  if (nodo.tipo !== "opcion") return undefined;
  const grupo = activo.grupos.find((g) => g.id === nodo.datos.grupoId);
  return grupo ? () => acc.enGrupo(grupo, ref) : () => acc.suelto(ref);
}

/** Traduce el grafo puro a lo que espera react-flow. Vive acá y no en
 * `lib/lienzo.ts` porque las acciones son del componente; la geometría y las
 * conexiones ya vinieron resueltas y probadas. */
function aReactFlow(
  grafo: Grafo,
  activo: ProductoDetalle,
  acc: Acciones,
  total: string,
): { nodos: Node[]; aristas: Edge[] } {
  const nodos: Node[] = grafo.nodos.map((n) => ({
    id: n.id,
    type: n.tipo,
    position: { x: n.x, y: n.y },
    className: n.datos.activo ? "activo-rf" : undefined,
    // El nodo se retira con su acción "quitar", que llama a la API. Borrarlo
    // con `Supr` solo lo sacaría del dibujo y volvería en el próximo
    // refresco: un fantasma que hace dudar de si se guardó algo.
    deletable: false,
    data: {
      ...n.datos,
      total,
      onToggle: alTocar(n, activo, acc),
      ...alQuitar(n, acc),
    } satisfies DatosNodo,
  }));
  const aristas: Edge[] = grafo.aristas.map((a) => ({
    id: a.id,
    source: a.desde,
    target: a.hasta,
    className: a.clase,
    // Solo lo que está en el plato se anima: animar todo es ruido, y con
    // `prefers-reduced-motion` la hoja de estilo lo apaga.
    animated: a.clase === "camino",
    // Se corta lo que se puede desvincular y nada más. El resto del árbol lo
    // dicta RN-PRD-004: dejarlo borrable sería ofrecer un gesto cuyo único
    // desenlace es un mensaje de error.
    deletable: a.hasta.startsWith("opcion:"),
  }));
  return { nodos, aristas };
}

/** Trae y memoriza las recetas que el camino elegido necesita.
 *
 * Perezoso a propósito: una pizza con 3 tamaños y 8 sabores son 27 recetas y
 * traerlas todas al abrir la pantalla para mostrar una es trabajo tirado. Se
 * piden cuando el nodo entra al plato y quedan cacheadas. */
function useCacheDeRecetas(
  ids: string[],
  onError: (mensaje: string) => void,
): [
  Record<string, RecetaDetalle>,
  React.Dispatch<React.SetStateAction<Record<string, RecetaDetalle>>>,
] {
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

  // Se devuelve el `set` porque editar una receta desde un nodo la actualiza
  // en el acto: el endpoint responde la receta completa, así que refrescar el
  // cache con eso evita una segunda vuelta a la red.
  return [cache, setCache];
}
