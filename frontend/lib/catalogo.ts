/**
 * Ficha de producto comercial y recetas, vista desde el navegador.
 *
 * La pantalla edita producto, variantes, grupos de extras y recetas en la
 * misma vista, así que cada acción es una llamada suelta contra la API por
 * el proxy — no una Server Action por campo. Los endpoints de receta
 * devuelven la receta completa después de cada cambio: así la pantalla no
 * mantiene su propia copia del estado y no puede quedar desincronizada de
 * lo que el servidor calculó (el redondeo por UdM se decide allá).
 */

import { pedir } from "@/lib/proxy";

// --- Tipos del contrato -----------------------------------------------------
export type UnidadMedida = {
  id: string;
  categoria_udm_id: string;
  nombre: string;
  ratio: string;
  decimales: number;
};

export type Articulo = {
  id: string;
  id_interno: string;
  nombre: string;
  unidad_medida_id: string;
  tipo: string;
  categoria_id: string | null;
  costo_promedio: string;
  archivado: boolean;
  controla_lote: boolean;
};

export type Categoria = { id: string; nombre: string; frecuencia_conteo: string | null };

/**
 * Qué puede ser un artículo. `articulo.tipo` es texto libre a propósito en
 * la base (se agregan tipos sin migración), pero la pantalla ofrece los que
 * el modelo de datos documenta: tipear "insummo" una vez y el reporte queda
 * partido en dos para siempre.
 */
export const TIPOS_ARTICULO = [
  { valor: "insumo", etiqueta: "Insumo (se compra y se consume)" },
  { valor: "subreceta", etiqueta: "Subreceta (se produce en cocina)" },
  { valor: "mercaderia", etiqueta: "Mercadería (se compra y se revende)" },
  { valor: "empaque", etiqueta: "Empaque" },
  { valor: "suministro", etiqueta: "Suministro (limpieza, oficina)" },
  { valor: "repuesto", etiqueta: "Repuesto" },
] as const;

export type RecetaItem = {
  id: string;
  articulo_id: string;
  articulo_nombre: string;
  unidad_medida_id: string;
  unidad_medida_nombre: string;
  decimales: number;
  cantidad: string;
  expresion: string | null;
  merma_pct: string;
  costo_unitario: string;
  costo_linea: string;
};

export type Receta = {
  id: string;
  nombre: string;
  rendimiento_cantidad: string;
  rendimiento_unidad_medida_id: string;
  rendimiento_unidad_medida_nombre: string | null;
  articulo_id: string | null;
  flexible: boolean;
  criterio_ajuste: string | null;
};

export type RecetaDetalle = Receta & {
  items: RecetaItem[];
  costo_total: string;
};

export type Marca = { id: string; nombre: string; tipo: string };

export type Producto = {
  id: string;
  id_interno: string;
  marca_id: string;
  nombre: string;
  categoria_id: string | null;
  receta_id: string | null;
  producto_padre_id: string | null;
  orden: number;
  activo: boolean;
  es_extra: boolean;
  empaque_id: string | null;
  modalidades_empaque: string[] | null;
};

export type ExtraDeProducto = {
  extra_id: string;
  nombre: string;
  receta_id: string | null;
  maximo: number | null;
};

export type GrupoOpcion = {
  id: string;
  nombre: string;
  minimo: number;
  maximo: number | null;
  orden: number;
  extras: ExtraDeProducto[];
};

export type ProductoDetalle = Producto & {
  variantes: Producto[];
  grupos: GrupoOpcion[];
  extras_sueltos: ExtraDeProducto[];
};

// --- Operaciones ------------------------------------------------------------
export const catalogoApi = {
  unidadesMedida: () => pedir<UnidadMedida[]>("/inventory/unidades-medida"),
  articulos: () => pedir<Articulo[]>("/inventory/articulos"),
  categorias: () => pedir<Categoria[]>("/inventory/categorias"),

  crearArticulo: (cuerpo: {
    id_interno: string;
    nombre: string;
    unidad_medida_id: string;
    tipo: string;
    categoria_id?: string | null;
    costo_promedio?: string;
    controla_lote?: boolean;
  }) => pedir<Articulo>("/inventory/articulos", { metodo: "POST", cuerpo }),

  editarArticulo: (
    id: string,
    cuerpo: Partial<{
      nombre: string;
      tipo: string;
      categoria_id: string;
      costo_promedio: string;
      controla_lote: boolean;
      archivado: boolean;
    }>,
  ) => pedir<Articulo>(`/inventory/articulos/${id}`, { metodo: "PATCH", cuerpo }),

  marcas: () => pedir<Marca[]>("/sales/marcas"),
  productos: () => pedir<Producto[]>("/sales/productos"),
  producto: (id: string) => pedir<ProductoDetalle>(`/sales/productos/${id}`),

  crearProducto: (cuerpo: {
    id_interno: string;
    marca_id: string;
    nombre: string;
    receta_id?: string | null;
    categoria_id?: string | null;
    producto_padre_id?: string | null;
    orden?: number;
    es_extra?: boolean;
  }) => pedir<Producto>("/sales/productos", { metodo: "POST", cuerpo }),

  editarProducto: (
    id: string,
    cuerpo: Partial<{
      nombre: string;
      activo: boolean;
      receta_id: string;
      categoria_id: string;
      orden: number;
      /** Único modo de dejarlo sin receta: `receta_id: null` sería
       * indistinguible de "no lo mandé". */
      quitar_receta: boolean;
    }>,
  ) => pedir<Producto>(`/sales/productos/${id}`, { metodo: "PATCH", cuerpo }),

  eliminarProducto: (id: string) =>
    pedir<void>(`/sales/productos/${id}`, { metodo: "DELETE" }),

  crearGrupo: (
    productoId: string,
    cuerpo: { nombre: string; minimo: number; maximo: number | null; orden?: number },
  ) => pedir<GrupoOpcion>(`/sales/productos/${productoId}/grupos`, { metodo: "POST", cuerpo }),

  vincularExtra: (
    productoId: string,
    cuerpo: { extra_id: string; maximo?: number | null; grupo_id?: string | null },
  ) => pedir<unknown>(`/sales/productos/${productoId}/extras`, { metodo: "POST", cuerpo }),

  recetas: () => pedir<Receta[]>("/inventory/recetas"),
  receta: (id: string) => pedir<RecetaDetalle>(`/inventory/recetas/${id}`),

  crearReceta: (cuerpo: {
    nombre: string;
    rendimiento_cantidad: string;
    rendimiento_unidad_medida_id: string;
  }) => pedir<Receta>("/inventory/recetas", { metodo: "POST", cuerpo }),

  editarReceta: (
    id: string,
    cuerpo: Partial<{
      nombre: string;
      rendimiento_cantidad: string;
      rendimiento_unidad_medida_id: string;
      /** Artículo `subreceta` que esta receta produce. */
      articulo_id: string;
    }>,
  ) => pedir<RecetaDetalle>(`/inventory/recetas/${id}`, { metodo: "PATCH", cuerpo }),

  eliminarReceta: (id: string) =>
    pedir<void>(`/inventory/recetas/${id}`, { metodo: "DELETE" }),

  duplicarReceta: (id: string) =>
    pedir<RecetaDetalle>(`/inventory/recetas/${id}/duplicar`, { metodo: "POST" }),

  escalarReceta: (id: string, factor: string) =>
    pedir<RecetaDetalle>(`/inventory/recetas/${id}/escalar`, {
      metodo: "POST",
      cuerpo: { factor },
    }),

  /** `expresion` viaja cuando el usuario tecleó una operación; el servidor
   * la evalúa y devuelve la cantidad ya redondeada a la UdM del insumo. */
  agregarItem: (
    recetaId: string,
    cuerpo: {
      articulo_id: string;
      cantidad?: string | null;
      expresion?: string | null;
      merma_pct?: string;
    },
  ) => pedir<RecetaDetalle>(`/inventory/recetas/${recetaId}/items`, { metodo: "POST", cuerpo }),

  editarItem: (
    recetaId: string,
    itemId: string,
    cuerpo: { cantidad?: string | null; expresion?: string | null; merma_pct?: string },
  ) =>
    pedir<RecetaDetalle>(`/inventory/recetas/${recetaId}/items/${itemId}`, {
      metodo: "PATCH",
      cuerpo,
    }),

  eliminarItem: (recetaId: string, itemId: string) =>
    pedir<RecetaDetalle>(`/inventory/recetas/${recetaId}/items/${itemId}`, {
      metodo: "DELETE",
    }),
};
