/**
 * Tablero de reportes (ADR-024).
 *
 * El catálogo lo manda el backend: qué reportes existen, con qué columnas,
 * qué visualizaciones admite cada uno y si el filtro de sucursales aplica.
 * El frontend no tiene una lista propia que mantener en paralelo — si un
 * reporte no llega en el catálogo es porque el usuario no puede verlo, y no
 * hay que decidir nada acá.
 */

import { pedir } from "@/lib/cliente-api";
import type { Columna, Datos, Visual } from "./reportes-datos";



export type Reporte = {
  codigo: string;
  nombre: string;
  descripcion: string;
  visual: Visual;
  visuales: Visual[];
  etiqueta: string;
  valor: string;
  filtra_sucursal: boolean;
  columnas: Columna[];
};

export type Catalogo = { reportes: Reporte[]; rangos: Record<string, string> };



export type Filtros = {
  preset: string;
  desde: string | null;
  hasta: string | null;
  sucursal_ids: string[];
  limite: number;
};

export type Tarjeta = {
  codigo: string;
  titulo: string | null;
  visual: Visual;
  /** Columnas del grid que ocupa (1-4). */
  ancho: number;
  alto: "chico" | "mediano" | "grande";
};

/** La tarjeta con una identidad estable en el cliente. Sin esto, la clave
 * de React sería la posición y reordenar remontaría el componente: cada
 * arrastre volvería a pedir los datos de todas las tarjetas movidas. No se
 * persiste — el orden ya lo da el índice en el array guardado. */
export type TarjetaViva = Tarjeta & { uid: string };

export type Tablero = {
  id: string;
  nombre: string;
  predeterminado: boolean;
  tarjetas: Tarjeta[];
  filtros: Filtros;
  rol_id: string | null;
  propio: boolean;
  compartido_por: string | null;
};

export type Sucursal = { id: string; nombre: string; estado: string };

export type Rol = { id: string; nombre: string };

export function conUid(tarjetas: Tarjeta[]): TarjetaViva[] {
  return tarjetas.map((t) => ({ ...t, uid: crypto.randomUUID() }));
}

export function sinUid(tarjetas: TarjetaViva[]): Tarjeta[] {
  return tarjetas.map(({ uid: _uid, ...resto }) => resto);
}


export const FILTROS_INICIALES: Filtros = {
  preset: "mes_actual",
  desde: null,
  hasta: null,
  sucursal_ids: [],
  limite: 50,
};

export const ALTURAS: Record<Tarjeta["alto"], string> = {
  chico: "h-48",
  mediano: "h-72",
  grande: "h-96",
};

/** Tailwind necesita las clases completas en el código para poder verlas al
 * compilar: `col-span-${n}` se purga y la tarjeta sale sin ancho. */
export const ANCHOS: Record<number, string> = {
  1: "lg:col-span-1",
  2: "lg:col-span-2",
  3: "lg:col-span-3",
  4: "lg:col-span-4",
};

/**
 * Caché de respuestas por (reporte + filtros), con vida corta.
 *
 * El caso que resuelve es concreto: volver a un rango que ya se miró (o
 * repetir una tarjeta que otra ya pidió con los mismos filtros) no tiene
 * por qué golpear la API de nuevo. Vive en memoria del módulo y muere con
 * la pestaña — un reporte es una foto, no un dato que se edite acá, así
 * que no hay nada que invalidar más que el paso del tiempo.
 *
 * ponytail: 30 s y un tope de 50 entradas. Si algún día hace falta caché
 * de verdad (compartida entre usuarios, con invalidación por evento), va
 * del lado del servidor con Redis, no acá.
 */
const VIDA_CACHE_MS = 30_000;
const MAX_CACHE = 50;
const cache = new Map<string, { en: number; datos: Datos }>();

export function limpiarCache(): void {
  cache.clear();
}

export async function datosDeReporte(
  codigo: string,
  filtros: Filtros,
): Promise<Datos> {
  const clave = `${codigo}|${JSON.stringify(filtros)}`;
  const guardado = cache.get(clave);
  if (guardado && Date.now() - guardado.en < VIDA_CACHE_MS) {
    return guardado.datos;
  }
  const datos = await pedir<Datos>(`/reportes/${codigo}/datos`, {
    metodo: "POST",
    cuerpo: filtros,
  });
  // Map conserva el orden de inserción: la primera clave es la más vieja.
  if (cache.size >= MAX_CACHE) {
    const masVieja = cache.keys().next().value;
    if (masVieja !== undefined) cache.delete(masVieja);
  }
  cache.set(clave, { en: Date.now(), datos });
  return datos;
}

export function listarTableros(): Promise<Tablero[]> {
  return pedir<Tablero[]>("/tableros");
}

export function listarRolesParaCompartir(): Promise<Rol[]> {
  return pedir<Rol[]>("/tableros/roles");
}

export function guardarTablero(
  cuerpo: {
    nombre: string;
    predeterminado: boolean;
    tarjetas: Tarjeta[];
    filtros: Filtros;
    rol_id: string | null;
  },
  id?: string,
): Promise<Tablero> {
  return pedir<Tablero>(id ? `/tableros/${id}` : "/tableros", {
    metodo: id ? "PATCH" : "POST",
    cuerpo,
  });
}

export function borrarTablero(id: string): Promise<void> {
  return pedir<void>(`/tableros/${id}`, { metodo: "DELETE" });
}

export {
  aCsv,
  aNumero,
  formatear,
  nombreArchivo,
  reordenar,
  type Columna,
  type Datos,
  type Fila,
  type TipoColumna,
  type Visual,
} from "./reportes-datos";

export function descargarCsv(nombre: string, contenido: string): void {
  // El BOM es lo que hace que Excel abra el archivo como UTF-8; sin el,
  // "Lacteos" llega como mojibake.
  const blob = new Blob(["\ufeff" + contenido], {
    type: "text/csv;charset=utf-8;",
  });
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombre;
  enlace.click();
  URL.revokeObjectURL(url);
}
