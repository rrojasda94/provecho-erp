/**
 * Ficha de producto comercial y recetas, vista desde el navegador.
 *
 * La pantalla edita producto, presentaciones y grupos de extras en la misma
 * vista, así que cada acción es una llamada suelta contra la API por el
 * proxy — no una Server Action por campo. Los endpoints de receta
 * devuelven la receta completa después de cada cambio: así la pantalla no
 * mantiene su propia copia del estado y no puede quedar desincronizada de
 * lo que el servidor calculó (el redondeo por UdM se decide allá).
 */

import { type Pagina } from "@/lib/api";
import { pedir, subir } from "@/lib/cliente-api";

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

/** Categoría del artículo que una receta produce — el filtro del listado
 * solo alcanza a las subrecetas, porque un producto de venta no produce
 * artículo del que sacar categoría (RN-COM-030). */
export type Categoria = { id: string; nombre: string };

// --- Carga masiva de recetas (RN-COM-031) ---
export type IngredienteRevisado = {
  fila: number;
  insumo: string;
  /** `null` = el catálogo no lo reconoció. La pantalla lo resuelve —eligiendo
   * uno, creándolo, o dejándolo así para omitir la línea— y el servidor
   * salta las que sigan en `null`. */
  articulo_id: string | null;
  cantidad: string;
  merma_pct: string;
  problemas: string[];
};

export type RecetaRevisada = {
  fila: number;
  nombre: string;
  rendimiento: string;
  unidad: string;
  unidad_medida_id: string | null;
  produce: string | null;
  articulo_producido_id: string | null;
  ingredientes: IngredienteRevisado[];
  problemas: string[];
};

export type OmitidaImport = { nombre: string; motivo: string };

export type RevisionImportacion = {
  recetas: RecetaRevisada[];
  insumos_desconocidos: string[];
  /** Ingredientes que nombran una receta que la otra hoja no declara: el
   * error de tipeo más común del formato. */
  ingredientes_sin_receta: string[];
  listas: number;
  con_problema: number;
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

/** La plantilla se baja con un `<a download>`, no con `fetch`: el navegador
 * tiene que guardar el archivo, y pasarlo por JS obligaría a construir un
 * Blob y una URL temporal para lograr lo mismo. Por eso es una ruta y no una
 * operación de `catalogoApi`. */
export const RUTA_PLANTILLA_RECETAS =
  "/api/proxy/api/v1/inventory/recetas/plantilla";

// --- Operaciones ------------------------------------------------------------
export const catalogoApi = {
  unidadesMedida: () => pedir<UnidadMedida[]>("/inventory/unidades-medida"),
  // Listado paginado (ADR-026): la carta del PDV no lo usa, sí el
  // editor de recetas, que pide la primera página.
  articulos: async () =>
    (await pedir<Pagina<Articulo>>("/inventory/articulos")).items,

  /** Alta rápida de un insumo desde el diálogo de importación: el archivo
   * nombró algo que el catálogo no tiene y crearlo ahí evita perder el
   * trabajo de resolver las otras cincuenta filas (RN-COM-031). */
  crearArticulo: (cuerpo: {
    id_interno: string;
    nombre: string;
    unidad_medida_id: string;
    tipo: string;
    categoria_id?: string | null;
  }) => pedir<Articulo>("/inventory/articulos", { metodo: "POST", cuerpo }),

  validarImportacion: (archivo: File) =>
    subir<RevisionImportacion>("/inventory/recetas/importar/validar", archivo),

  /** Manda **solo lo que el contrato declara**: la revisión trae además
   * `fila`, `unidad`, `produce` y `problemas`, que son para mostrar en
   * pantalla y no significan nada del otro lado. */
  importarRecetas: (recetas: RecetaRevisada[]) =>
    pedir<{ creadas: { id: string; nombre: string }[]; omitidas: OmitidaImport[] }>(
      "/inventory/recetas/importar",
      {
        metodo: "POST",
        cuerpo: {
          recetas: recetas.map((r) => ({
            nombre: r.nombre,
            rendimiento: r.rendimiento,
            unidad_medida_id: r.unidad_medida_id,
            articulo_producido_id: r.articulo_producido_id,
            ingredientes: r.ingredientes.map((i) => ({
              insumo: i.insumo,
              articulo_id: i.articulo_id,
              cantidad: i.cantidad,
              merma_pct: i.merma_pct,
            })),
          })),
        },
      },
    ),

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
      /** Artículo de empaque y en qué modalidades se descuenta (RN-EMP-003). */
      empaque_id: string | null;
      modalidades_empaque: string[] | null;
    }>,
  ) => pedir<Producto>(`/sales/productos/${id}`, { metodo: "PATCH", cuerpo }),

  eliminarProducto: (id: string) =>
    pedir<void>(`/sales/productos/${id}`, { metodo: "DELETE" }),

  crearGrupo: (
    productoId: string,
    cuerpo: { nombre: string; minimo: number; maximo: number | null; orden?: number },
  ) => pedir<GrupoOpcion>(`/sales/productos/${productoId}/grupos`, { metodo: "POST", cuerpo }),

  borrarGrupo: (productoId: string, grupoId: string) =>
    pedir<void>(`/sales/productos/${productoId}/grupos/${grupoId}`, {
      metodo: "DELETE",
    }),

  vincularExtra: (
    productoId: string,
    cuerpo: { extra_id: string; maximo?: number | null; grupo_id?: string | null },
  ) => pedir<unknown>(`/sales/productos/${productoId}/extras`, { metodo: "POST", cuerpo }),

  /** Deja de ofrecer el extra en este producto. El extra sobrevive: es un
   * producto comercial con su propia receta y su propio precio. */
  desvincularExtra: (productoId: string, extraId: string) =>
    pedir<void>(`/sales/productos/${productoId}/extras/${extraId}`, {
      metodo: "DELETE",
    }),

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
