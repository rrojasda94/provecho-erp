/**
 * El grafo del lienzo de nodos: qué nodo existe, dónde va y qué lo conecta.
 *
 * Todo acá es **puro**: no habla con la API, no sabe de React ni de
 * `@xyflow/react`, y por eso se prueba solo (`lienzo.test.ts`). El
 * componente se limita a pintar lo que esta función devuelve.
 *
 * El orden de las columnas **es** RN-PRD-004 leído de izquierda a derecha:
 *
 *     producto → tamaño → combinación (sabor) → extras → restas → empaque → plato
 *
 * Hasta ahora esa regla vivía implícita en el orden vertical de unas filas
 * de `<div>`. En un lienzo se vuelve la espina visible de la pantalla, y el
 * nodo terminal **plato** hace literal la tesis de ADR-035: cada tramo
 * aporta su receta y el plato es la suma.
 *
 * `frontend/lib/nodos.ts` sigue siendo el dueño de la matemática del costo;
 * este archivo solo decide geometría y conexiones.
 */

import type {
  Articulo,
  ExtraDeProducto,
  GrupoOpcion,
  Producto,
  ProductoDetalle,
  Receta,
  RecetaDetalle,
} from "@/lib/catalogo";
import type { ParteDeReceta } from "@/lib/nodos";

// --- El camino: qué nodos están elegidos y qué receta aporta cada uno -------
/** Tamaño activo + lo elegido bajo él. Un solo estado porque cambian juntos:
 * la selección de un tamaño no significa nada bajo otro. */
export type Camino = {
  activoId: string;
  /** `grupo_id` → ids de las opciones elegidas en ese grupo. */
  elegidas: Record<string, string[]>;
  sueltos: string[];
  /** `articulo_id` de lo que el plato NO lleva. */
  restas: string[];
};

/** Un nodo elegido, ya resuelto contra la ficha: el extra y de qué grupo
 * salió (o ninguno, si es suelto). */
export type Elegido = { extra: ExtraDeProducto; grupo: GrupoOpcion | null };

export function elegidosDelCamino(
  activo: ProductoDetalle,
  elegidas: Record<string, string[]>,
  sueltos: string[],
): Elegido[] {
  const salida: Elegido[] = [];
  for (const grupo of activo.grupos) {
    for (const id of elegidas[grupo.id] ?? []) {
      const extra = grupo.extras.find((e) => e.extra_id === id);
      if (extra) salida.push({ extra, grupo });
    }
  }
  for (const id of sueltos) {
    const extra = activo.extras_sueltos.find((e) => e.extra_id === id);
    if (extra) salida.push({ extra, grupo: null });
  }
  return salida;
}

export function recetasDe(
  activo: ProductoDetalle,
  elegidos: Elegido[],
): string[] {
  const ids = [activo.receta_id, ...elegidos.map((e) => e.extra.receta_id)];
  return [...new Set(ids.filter((id): id is string => Boolean(id)))];
}

/** Las recetas que el lienzo necesita traer: las del plato que se está
 * armando, más la del nodo que se está inspeccionando —que puede no estar en
 * el plato, porque se abre para editarla, no para sumarla—. */
export function recetasDelLienzo(
  activo: ProductoDetalle,
  elegidos: Elegido[],
  inspeccionada: string | null,
): string[] {
  const ids = recetasDe(activo, elegidos);
  return inspeccionada && !ids.includes(inspeccionada)
    ? [...ids, inspeccionada]
    : ids;
}

export function armarPartes(
  activo: ProductoDetalle,
  nombrePadre: string,
  elegidos: Elegido[],
  cache: Record<string, RecetaDetalle>,
): ParteDeReceta[] {
  const receta = (id: string | null) => (id ? cache[id] ?? null : null);
  return [
    {
      titulo: etiquetaCorta(activo.nombre, nombrePadre),
      tipo: "tamano",
      receta: receta(activo.receta_id),
    },
    ...elegidos.map(({ extra, grupo }) => ({
      titulo: extra.nombre,
      // Un grupo obligatorio es la combinación (el sabor); uno opcional son
      // extras. La diferencia es el mínimo, no una columna aparte.
      tipo: (esCombinacion(grupo) ? "sabor" : "extra") as ParteDeReceta["tipo"],
      receta: receta(extra.receta_id),
    })),
  ];
}

/** Un grupo obligatorio **es** la combinación (el sabor). No hace falta un
 * `tipo` de grupo en la base: `minimo >= 1` ya lo dice, y una tercera forma
 * de decir lo mismo termina diciendo algo distinto (ADR-035 §5). */
export function esCombinacion(grupo: GrupoOpcion | null): boolean {
  return (grupo?.minimo ?? 0) >= 1;
}

/** El empaque del nodo y si esta modalidad lo consume (RN-EMP-003). No va
 * por `fusionar`: el empaque no es una receta, es una unidad por plato. */
export function resolverEmpaque(
  nodo: ProductoDetalle,
  empaques: Articulo[],
  modalidad: string,
): { empaque: Articulo | null; aplica: boolean; costo: number } {
  const empaque = empaques.find((a) => a.id === nodo.empaque_id) ?? null;
  const aplica =
    empaque !== null && (nodo.modalidades_empaque ?? []).includes(modalidad);
  return {
    empaque,
    aplica,
    costo: aplica ? Number(empaque.costo_promedio) : 0,
  };
}

// --- Geometría del grafo ----------------------------------------------------
/** Medidas del lienzo en unidades de mundo. Son constantes y **las mismas**
 * que el CSS recibe como variables: medir los nodos en el DOM para colocarlos
 * obliga a un ciclo layout→medición→layout que se ve como un salto. */
export const MEDIDAS = {
  anchoNodo: 200,
  altoNodo: 76,
  altoChip: 44,
  separacionColumna: 250,
  separacionFila: 24,
  /** Restas: son una por insumo y pueden ser muchas; se apilan en
   * subcolumnas para que la fila no se vuelva un muro vertical. */
  porColumna: 7,
};

export type TipoNodo =
  | "producto"
  | "tamano"
  | "grupo"
  | "opcion"
  | "disponible"
  | "empaque"
  | "resta"
  | "plato";

export type NodoLienzo = {
  id: string;
  tipo: TipoNodo;
  x: number;
  y: number;
  datos: {
    titulo: string;
    pie?: string;
    /** Está dentro del plato que se está armando. */
    activo: boolean;
    /** Nombre accesible cuando el texto visible no alcanza: el chip de una
     * resta dice "Orégano" y el lector de pantalla tiene que oír "sin
     * Orégano", que es lo que el plato realmente pide. */
    aria?: string;
    /** Id del producto/artículo real detrás del nodo, para las acciones. */
    refId?: string;
    recetaId?: string | null;
    grupoId?: string | null;
    columna: string;
  };
};

export type AristaLienzo = {
  id: string;
  desde: string;
  hasta: string;
  /** `camino` = el plato pasa por acá; `posible` = existe pero no se eligió;
   * `resta` = quita algo; `inactiva` = configurado pero no aplica hoy. */
  clase: "camino" | "posible" | "resta" | "inactiva";
};

export type Grafo = { nodos: NodoLienzo[]; aristas: AristaLienzo[] };

/** Centra verticalmente una columna y la envuelve en subcolumnas al pasar de
 * `porColumna`. Devuelve la posición de cada índice. */
export function apilarColumna(
  cuantos: number,
  x: number,
  alto: number,
  porColumna = MEDIDAS.porColumna,
): { x: number; y: number }[] {
  const paso = alto + MEDIDAS.separacionFila;
  return Array.from({ length: cuantos }, (_, i) => {
    const sub = Math.floor(i / porColumna);
    const enSub = i % porColumna;
    const deEsta = Math.min(cuantos - sub * porColumna, porColumna);
    return {
      x: x + sub * (MEDIDAS.anchoNodo + MEDIDAS.separacionFila),
      y: (enSub - (deEsta - 1) / 2) * paso,
    };
  });
}

const columnaX = (indice: number) => indice * MEDIDAS.separacionColumna;

/** Cuántos lugares de columna ocupa una lista que se envuelve. Sin esto, una
 * columna de 18 chips se parte en tres y se monta encima de la siguiente:
 * la envoltura ensancha la columna y el índice tiene que enterarse. */
export function subcolumnas(cuantos: number, porColumna = MEDIDAS.porColumna): number {
  return Math.max(1, Math.ceil(cuantos / porColumna));
}

function nodoProducto(padre: ProductoDetalle): NodoLienzo {
  return {
    id: "producto",
    tipo: "producto",
    x: columnaX(0),
    y: 0,
    datos: {
      titulo: padre.nombre,
      pie: padre.id_interno,
      activo: true,
      refId: padre.id,
      columna: "Producto",
    },
  };
}

function columnaTamanos(
  ramas: ProductoDetalle[],
  padre: ProductoDetalle,
  camino: Camino,
  recetas: Receta[],
): Grafo {
  const posiciones = apilarColumna(ramas.length, columnaX(1), MEDIDAS.altoNodo);
  const nodos = ramas.map((v, i) => ({
    id: `tamano:${v.id}`,
    tipo: "tamano" as const,
    ...posiciones[i],
    datos: {
      titulo:
        v.id === padre.id ? "Único" : etiquetaCorta(v.nombre, padre.nombre),
      pie: nombreReceta(recetas, v.receta_id),
      activo: v.id === camino.activoId,
      refId: v.id,
      recetaId: v.receta_id,
      columna: "Tamaño",
    },
  }));
  return {
    nodos,
    aristas: nodos.map((n) => ({
      id: `producto→${n.id}`,
      desde: "producto",
      hasta: n.id,
      clase: n.datos.activo ? ("camino" as const) : ("posible" as const),
    })),
  };
}

/**
 * Una columna de opciones, encabezada por **el nodo del grupo**.
 *
 * El grupo es un nodo y no un rótulo porque es el destino de una conexión:
 * arrastrar un extra disponible hasta él es lo que lo cuelga *en ese grupo*
 * (`vincular_extra` con `grupo_id`). Sin nodo de grupo, colgar algo en
 * "Sabor" y colgarlo suelto serían el mismo gesto.
 */
function columnaDeOpciones(
  extras: ExtraDeProducto[],
  grupo: GrupoOpcion | null,
  indice: number,
  activo: ProductoDetalle,
  camino: Camino,
  recetas: Receta[],
): Grafo {
  const elegidas = grupo ? (camino.elegidas[grupo.id] ?? []) : camino.sueltos;
  const cabeza = grupo ? `grupo:${grupo.id}` : `tamano:${activo.id}`;
  const posiciones = apilarColumna(
    extras.length,
    columnaX(indice),
    MEDIDAS.altoNodo,
  );
  const nodos: NodoLienzo[] = extras.map((e, i) => ({
    id: `opcion:${grupo?.id ?? "sueltos"}:${e.extra_id}`,
    tipo: "opcion" as const,
    ...posiciones[i],
    datos: {
      titulo: e.nombre,
      pie: nombreReceta(recetas, e.receta_id),
      activo: elegidas.includes(e.extra_id),
      refId: e.extra_id,
      recetaId: e.receta_id,
      grupoId: grupo?.id ?? null,
      columna: grupo?.nombre ?? "Extras",
    },
  }));
  const aristas: AristaLienzo[] = nodos.map((n) => ({
    id: `${cabeza}→${n.id}`,
    desde: cabeza,
    hasta: n.id,
    clase: n.datos.activo ? ("camino" as const) : ("posible" as const),
  }));

  if (grupo) {
    // El nodo del grupo se apoya arriba de su columna, no en el centro: así
    // se lee como cabecera y no como una opción más.
    const arriba = Math.min(...posiciones.map((p) => p.y), 0);
    nodos.push({
      id: `grupo:${grupo.id}`,
      tipo: "grupo",
      x: columnaX(indice),
      y: arriba - (MEDIDAS.altoNodo + MEDIDAS.separacionFila),
      datos: {
        titulo: grupo.nombre,
        pie: reglaDeGrupo(grupo),
        activo: (camino.elegidas[grupo.id] ?? []).length >= grupo.minimo,
        refId: grupo.id,
        grupoId: grupo.id,
        columna: "Grupo",
      },
    });
    aristas.push({
      id: `tamano:${activo.id}→grupo:${grupo.id}`,
      desde: `tamano:${activo.id}`,
      hasta: `grupo:${grupo.id}`,
      clase: "posible",
    });
  }
  return { nodos, aristas };
}

/**
 * Los extras que existen y este producto todavía NO ofrece.
 *
 * Están en el lienzo justamente para poder conectarlos: se arrastra de un
 * grupo (o del tamaño, para dejarlo suelto) hasta uno de estos y eso lo
 * cuelga. Es la versión de "agregar un nodo y cablearlo" que el dominio
 * admite — la topología entre tamaño, sabor y plato la sigue dictando
 * RN-PRD-004 y no se cablea a mano.
 */
function columnaDisponibles(
  disponibles: { id: string; nombre: string }[],
  indice: number,
): Grafo {
  const posiciones = apilarColumna(
    disponibles.length,
    columnaX(indice),
    MEDIDAS.altoChip,
  );
  return {
    nodos: disponibles.map((d, i) => ({
      id: `disponible:${d.id}`,
      tipo: "disponible" as const,
      ...posiciones[i],
      datos: {
        titulo: d.nombre,
        aria: `${d.nombre} — sin vincular`,
        activo: false,
        refId: d.id,
        columna: "Disponibles",
      },
    })),
    aristas: [],
  };
}

function columnaRestas(
  quitables: { articuloId: string; articulo: string }[],
  indice: number,
  camino: Camino,
): Grafo {
  const posiciones = apilarColumna(
    quitables.length,
    columnaX(indice),
    MEDIDAS.altoChip,
  );
  const nodos = quitables.map((q, i) => ({
    id: `resta:${q.articuloId}`,
    tipo: "resta" as const,
    ...posiciones[i],
    datos: {
      titulo: q.articulo,
      aria: `sin ${q.articulo}`,
      activo: camino.restas.includes(q.articuloId),
      refId: q.articuloId,
      columna: "Restas",
    },
  }));
  // Solo las restas ACTIVAS llegan al plato: una resta no elegida no le quita
  // nada, y dibujar su arista igual llenaría el lienzo de líneas sin efecto.
  return {
    nodos,
    aristas: nodos
      .filter((n) => n.datos.activo)
      .map((n) => ({
        id: `${n.id}→plato`,
        desde: n.id,
        hasta: "plato",
        clase: "resta" as const,
      })),
  };
}

function nodoEmpaque(
  activo: ProductoDetalle,
  empaques: Articulo[],
  modalidad: string,
  indice: number,
): Grafo {
  const { empaque, aplica } = resolverEmpaque(activo, empaques, modalidad);
  const nodo: NodoLienzo = {
    id: "empaque",
    tipo: "empaque",
    x: columnaX(indice),
    y: 0,
    datos: {
      titulo: empaque?.nombre ?? "Sin empaque",
      // La modalidad decide si se consume (RN-EMP-003). Decirlo en el nodo
      // ahorra la nota al pie que nadie lee.
      pie: empaque ? (aplica ? modalidad : `no en ${modalidad}`) : undefined,
      activo: aplica,
      refId: empaque?.id,
      columna: "Empaque",
    },
  };
  return {
    nodos: [nodo],
    aristas: empaque
      ? [
          {
            id: "empaque→plato",
            desde: "empaque",
            hasta: "plato",
            clase: aplica ? "camino" : "inactiva",
          },
        ]
      : [],
  };
}

/**
 * El grafo entero del producto para el camino elegido.
 *
 * Partido por columna a propósito: `complexity: 10` es error en este repo, y
 * un solo constructor con todos los casos lo pasa sin esfuerzo. Acá arriba
 * queda una concatenación plana que se lee como el enunciado de RN-PRD-004.
 */
export function armarGrafo(params: {
  padre: ProductoDetalle;
  variantes: ProductoDetalle[];
  activo: ProductoDetalle;
  camino: Camino;
  recetas: Receta[];
  quitables: { articuloId: string; articulo: string }[];
  empaques: Articulo[];
  modalidad: string;
  /** Extras que existen y este producto todavía no ofrece. */
  disponibles?: { id: string; nombre: string }[];
}): Grafo {
  const { padre, variantes, activo, camino, recetas, quitables } = params;
  // Un producto sin tamaños es su propio nodo: "simple" es el árbol de un
  // solo tronco, no otro caso a modelar.
  const ramas = variantes.length ? variantes : [padre];

  const partes: Grafo[] = [
    { nodos: [nodoProducto(padre)], aristas: [] },
    columnaTamanos(ramas, padre, camino, recetas),
  ];
  let columna = 2;
  for (const grupo of activo.grupos) {
    partes.push(
      columnaDeOpciones(grupo.extras, grupo, columna, activo, camino, recetas),
    );
    columna += subcolumnas(grupo.extras.length);
  }
  partes.push(
    columnaDeOpciones(
      activo.extras_sueltos,
      null,
      columna,
      activo,
      camino,
      recetas,
    ),
  );
  columna += subcolumnas(activo.extras_sueltos.length);
  const disponibles = params.disponibles ?? [];
  partes.push(columnaDisponibles(disponibles, columna));
  columna += subcolumnas(disponibles.length);
  partes.push(columnaRestas(quitables, columna, camino));
  columna += subcolumnas(quitables.length);
  partes.push(nodoEmpaque(activo, params.empaques, params.modalidad, columna));
  columna += 1;

  const nodos = partes.flatMap((p) => p.nodos);
  const aristas = partes.flatMap((p) => p.aristas);
  nodos.push({
    id: "plato",
    tipo: "plato",
    x: columnaX(columna),
    y: 0,
    datos: { titulo: "Plato", activo: true, columna: "Plato" },
  });
  // El tamaño y cada opción elegida alimentan el plato: es la suma que hace
  // `fusionar`, dibujada.
  for (const n of nodos) {
    const alimenta =
      (n.tipo === "tamano" || n.tipo === "opcion") && n.datos.activo;
    if (alimenta) {
      aristas.push({
        id: `${n.id}→plato`,
        desde: n.id,
        hasta: "plato",
        clase: "camino",
      });
    }
  }
  return { nodos, aristas };
}

// --- Auxiliares -------------------------------------------------------------
export function alternar(lista: string[], id: string): string[] {
  return lista.includes(id) ? lista.filter((x) => x !== id) : [...lista, id];
}

/** "Pizza Peperoni Familiar" dentro de "Pizza Peperoni" → "Familiar". */
export function etiquetaCorta(nombre: string, nombrePadre: string): string {
  return nombre.toLowerCase().startsWith(nombrePadre.toLowerCase())
    ? nombre.slice(nombrePadre.length).trim() || nombre
    : nombre;
}

export function nombreReceta(
  recetas: Receta[],
  recetaId: string | null,
): string {
  if (!recetaId) return "sin receta";
  return recetas.find((r) => r.id === recetaId)?.nombre ?? "receta";
}

export function reglaDeGrupo(grupo: GrupoOpcion): string {
  const minimo = grupo.minimo >= 1 ? `elige ${grupo.minimo}` : "opcional";
  const maximo = grupo.maximo ? `hasta ${grupo.maximo}` : "sin tope";
  return `${minimo} · ${maximo}`;
}

export function sinVincular(
  disponibles: Producto[],
  nodo: ProductoDetalle,
): Producto[] {
  const yaEstan = new Set<string>([
    ...nodo.extras_sueltos.map((e: ExtraDeProducto) => e.extra_id),
    ...nodo.grupos.flatMap((g) => g.extras.map((e) => e.extra_id)),
  ]);
  return disponibles.filter((p) => !yaEstan.has(p.id));
}

/** Los grupos obligatorios que el camino todavía no cumple — la misma regla
 * que el servidor valida al confirmar la venta (RN-COM-023). */
export function faltantesDeGrupos(
  nodo: ProductoDetalle,
  elegidas: Record<string, string[]>,
): string[] {
  return nodo.grupos
    .filter((g) => (elegidas[g.id] ?? []).length < g.minimo)
    .map((g) => g.nombre);
}

export function tituloDelPlato(
  nodo: ProductoDetalle,
  padre: ProductoDetalle,
  partes: ParteDeReceta[],
): string {
  const extras = partes.filter((p) => p.tipo !== "tamano").map((p) => p.titulo);
  const base =
    nodo.id === padre.id
      ? padre.nombre
      : `${padre.nombre} ${etiquetaCorta(nodo.nombre, padre.nombre)}`;
  return extras.length ? `${base} · ${extras.join(", ")}` : base;
}

/** Elegir dentro de un grupo: uno de un solo cupo se comporta como radio.
 * Es el mismo tope que valida el servidor al confirmar (RN-COM-023). */
export function elegirEnGrupo(
  camino: Camino,
  grupo: GrupoOpcion,
  extraId: string,
): Camino {
  const actual = camino.elegidas[grupo.id] ?? [];
  const nuevas =
    grupo.maximo === 1 && !actual.includes(extraId)
      ? [extraId]
      : alternar(actual, extraId);
  return { ...camino, elegidas: { ...camino.elegidas, [grupo.id]: nuevas } };
}
