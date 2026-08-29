/**
 * Lógica pura del tablero de reportes: formateo, CSV y reordenamiento.
 *
 * Aparte de `lib/reportes.ts` por lo mismo que `kds-avance.ts` está aparte
 * de `kds.ts`: acá no se importa nada del bundler ni del navegador, así que
 * `node --test` puede cargar el archivo tal cual y probarlo sin montar React
 * ni simular un DOM. Lo que toca `Blob`/`document` se queda del otro lado.
 */

export type TipoColumna =
  | "texto"
  | "numero"
  | "dinero"
  | "cantidad"
  | "fecha"
  // El id de la entidad de la fila. No se dibuja como celda: es el ancla del
  // enlace de la fila (ADR-036).
  | "id";
export type Visual = "tabla" | "barras" | "lineas" | "pie" | "area";

export type Columna = {
  clave: string;
  titulo: string;
  tipo: TipoColumna;
  /** Tipo de entidad al que apunta esta columna, si es un id. */
  enlace?: string;
};

export type Fila = Record<string, string | number | null>;

export type Datos = {
  codigo: string;
  desde: string;
  hasta: string;
  columnas: Columna[];
  filas: Fila[];
};

const FORMATO_NUMERO = new Intl.NumberFormat("es-PE", { maximumFractionDigits: 3 });
const FORMATO_DINERO = new Intl.NumberFormat("es-PE", {
  style: "currency",
  currency: "PEN",
});

/** El backend manda los montos como texto exacto para no perder centavos en
 * un float. Se convierte a número solo acá, al mostrarlo. */
export function formatear(valor: string | number | null, tipo: TipoColumna): string {
  if (valor === null || valor === "") return "—";
  if (tipo === "texto") return String(valor);
  if (tipo === "fecha") {
    // `2026-08-04` sin hora: `new Date` lo interpretaría como UTC y en Perú
    // mostraría el día anterior.
    const [a, m, d] = String(valor).split("-");
    return d ? `${d}/${m}/${a}` : String(valor);
  }
  const n = Number(valor);
  if (Number.isNaN(n)) return String(valor);
  return tipo === "dinero" ? FORMATO_DINERO.format(n) : FORMATO_NUMERO.format(n);
}

export function aNumero(valor: string | number | null): number {
  const n = Number(valor ?? 0);
  return Number.isNaN(n) ? 0 : n;
}

/** Mueve el elemento `desde` a la posición `hasta`, devolviendo un array
 * nuevo. Índices fuera de rango dejan la lista intacta en vez de romperla:
 * el llamador los saca de un `findIndex` que puede devolver -1. */
export function reordenar<T>(items: T[], desde: number, hasta: number): T[] {
  if (desde === hasta || desde < 0 || hasta < 0) return items;
  if (desde >= items.length || hasta >= items.length) return items;
  const copia = [...items];
  const [movido] = copia.splice(desde, 1);
  copia.splice(hasta, 0, movido);
  return copia;
}

/** Escapa un campo según RFC 4180: se entrecomilla si trae separador,
 * comillas o salto de línea, y las comillas internas se duplican. Sin esto
 * una razón social con coma parte la fila en dos columnas. */
function campoCsv(valor: unknown): string {
  const texto = valor === null || valor === undefined ? "" : String(valor);
  return /[",\n\r]/.test(texto) ? `"${texto.replaceAll('"', '""')}"` : texto;
}

/**
 * CSV del reporte tal como está en pantalla.
 *
 * Se arma en el cliente y no en la API porque los datos ya están acá: un
 * endpoint nuevo repetiría la consulta, el RBAC y el rango para producir
 * exactamente las filas que el navegador ya tiene. Lo que se exporta es lo
 * que se ve — si contabilidad necesita más filas, sube `limite` (tope 500,
 * que es un límite de seguridad, no de la UI).
 *
 * Los montos salen **crudos** (`1234.50`), no formateados: `S/ 1,234.50` no
 * lo suma ninguna hoja de cálculo.
 */
export function aCsv(columnas: Columna[], filas: Fila[]): string {
  const cabecera = columnas.map((c) => campoCsv(c.titulo)).join(",");
  const cuerpo = filas.map((f) =>
    columnas.map((c) => campoCsv(f[c.clave])).join(","),
  );
  return [cabecera, ...cuerpo].join("\r\n");
}

/** Las pocas letras acentuadas que aparecen en el título de un reporte.
 * Más simple que normalizar en NFD y borrar marcas combinantes, y no
 * depende de cómo quede codificado este archivo. */
const ACENTOS: Record<string, string> = {
  "á": "a",
  "é": "e",
  "í": "i",
  "ó": "o",
  "ú": "u",
  "ü": "u",
  "ñ": "n",
};

/** `Ventas por día` + rango → `ventas-por-dia_2026-07-06_2026-08-04.csv` */
export function nombreArchivo(titulo: string, datos: Datos): string {
  let base = titulo.toLowerCase();
  for (const [acentuada, plana] of Object.entries(ACENTOS)) {
    base = base.replaceAll(acentuada, plana);
  }
  // Todo lo demas que no sea alfanumerico (espacios, signos, y cualquier
  // otra letra no ASCII que se cuele) colapsa en guiones.
  base = base.replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return `${base}_${datos.desde}_${datos.hasta}.csv`;
}
