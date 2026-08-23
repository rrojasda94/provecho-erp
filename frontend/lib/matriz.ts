/**
 * El recetario en grilla: insumos en las filas, recetas en las columnas
 * (ADR-057).
 *
 * Todo lo de acá es **puro**: arma el rectángulo, entiende lo que se pega
 * desde Excel y calcula qué cambió. Nada consulta ni guarda — eso lo hace la
 * pantalla, y así el pegado y el diff se prueban sin montar un navegador.
 *
 * **La identidad de una celda es `(receta, insumo, condición)`**, no un id de
 * línea. Es lo que permite pegar un rectángulo desde Excel, que no trae ids:
 * el servidor resuelve solo si esa celda es un alta, una edición o un
 * borrado.
 */

export type CeldaServidor = {
  item_id: string;
  receta_id: string;
  articulo_id: string;
  cantidad: string;
  expresion: string | null;
  merma_pct: string;
  unidad_medida_id: string | null;
  unidad: string;
  decimales: number;
  aplica_valores: string[];
  orden: number;
};

export type RecetaColumna = {
  id: string;
  nombre: string;
  rendimiento_cantidad: string;
  rendimiento_unidad_medida_id: string;
  es_kit: boolean;
};

export type InsumoFila = {
  articulo_id: string;
  nombre: string;
  unidad_medida_id: string;
  unidad: string;
  decimales: number;
  costo_promedio: string;
};

export type Grilla = {
  recetas: RecetaColumna[];
  insumos: InsumoFila[];
  celdas: CeldaServidor[];
};

/** Lo que se ve y se edita en un cruce. `texto` es lo tecleado — una
 * operación o un número—, no el resultado. */
export type Celda = {
  texto: string;
  unidadMedidaId: string | null;
  unidad: string;
  decimales: number;
  aplicaValores: string[];
  sucia: boolean;
};

export type Modelo = {
  recetas: RecetaColumna[];
  insumos: InsumoFila[];
  celdas: Map<string, Celda>;
};

/** La clave de una celda. La condición va ordenada: es un conjunto, y el
 * orden en que se listan sus valores no hace a la celda. */
export function clave(
  recetaId: string,
  articuloId: string,
  aplicaValores: string[] = [],
): string {
  return [recetaId, articuloId, [...aplicaValores].sort().join("+")].join("|");
}

/**
 * Del rectángulo que devuelve el servidor al modelo que edita la pantalla.
 *
 * Se muestra `expresion` y no `cantidad` cuando la hay: quien escribió
 * "450/3" quiere volver a ver la división, no 150 (RN-COM-024).
 */
export function armar(grilla: Grilla): Modelo {
  const celdas = new Map<string, Celda>();
  for (const c of grilla.celdas) {
    celdas.set(clave(c.receta_id, c.articulo_id, c.aplica_valores), {
      texto: c.expresion ?? recortar(c.cantidad, c.decimales),
      unidadMedidaId: c.unidad_medida_id,
      unidad: c.unidad,
      decimales: c.decimales,
      aplicaValores: c.aplica_valores,
      sucia: false,
    });
  }
  return { recetas: grilla.recetas, insumos: grilla.insumos, celdas };
}

/** "0.1500" con 3 decimales es "0.15": los ceros de la derecha son ruido de
 * la columna `Numeric`, no precisión que alguien tecleó. */
export function recortar(cantidad: string, decimales: number): string {
  const numero = Number(cantidad);
  if (!Number.isFinite(numero)) return cantidad;
  if (numero === 0) return "";
  return String(Number(numero.toFixed(decimales)));
}

/** Escribe una celda. Devuelve un modelo nuevo — el estado de React no se
 * muta en el lugar. */
export function escribir(
  modelo: Modelo,
  recetaId: string,
  insumo: InsumoFila,
  texto: string,
  aplicaValores: string[] = [],
): Modelo {
  const k = clave(recetaId, insumo.articulo_id, aplicaValores);
  const anterior = modelo.celdas.get(k);
  const celdas = new Map(modelo.celdas);
  celdas.set(k, {
    texto,
    unidadMedidaId: anterior?.unidadMedidaId ?? null,
    unidad: anterior?.unidad ?? insumo.unidad,
    decimales: anterior?.decimales ?? insumo.decimales,
    aplicaValores,
    sucia: true,
  });
  return { ...modelo, celdas };
}

export type CeldaAGuardar = {
  receta_id: string;
  articulo_id: string;
  expresion: string;
  unidad_medida_id: string | null;
  aplica_valores: string[];
};

/**
 * Qué mandar al servidor: **solo lo que se tocó**.
 *
 * Mandar la grilla entera sería más simple y reescribiría cuarenta líneas
 * que nadie editó, con su `updated_at` y su rastro de auditoría. Y con dos
 * personas en la pantalla, la última en guardar pisaría el trabajo de la
 * otra aunque hubieran tocado celdas distintas.
 */
export function cambios(modelo: Modelo): CeldaAGuardar[] {
  const salida: CeldaAGuardar[] = [];
  for (const [k, celda] of modelo.celdas) {
    if (!celda.sucia) continue;
    const [recetaId, articuloId] = k.split("|");
    salida.push({
      receta_id: recetaId,
      articulo_id: articuloId,
      expresion: celda.texto.trim(),
      unidad_medida_id: celda.unidadMedidaId,
      aplica_valores: celda.aplicaValores,
    });
  }
  return salida;
}

export function haySinGuardar(modelo: Modelo): boolean {
  for (const celda of modelo.celdas.values()) if (celda.sucia) return true;
  return false;
}

/**
 * Lo que el portapapeles trae al copiar un rectángulo de Excel: filas
 * separadas por salto de línea, columnas por tabulador.
 *
 * Excel manda `\r\n` en Windows y `\n` en Mac, y una celda vacía es un
 * tabulador pegado a otro — que acá significa "vaciar", no "no tocar". La
 * última línea suele venir vacía y se descarta.
 */
export function leerPegado(texto: string): string[][] {
  const lineas = texto.replace(/\r\n?/g, "\n").split("\n");
  while (lineas.length > 1 && lineas[lineas.length - 1] === "") lineas.pop();
  return lineas.map((linea) => linea.split("\t"));
}

/**
 * Vuelca un rectángulo pegado a partir de la celda donde está el cursor.
 *
 * Lo que se sale de la grilla se **descarta en silencio**: pegar cinco filas
 * cuando quedan tres es un accidente común, y crecer la grilla sola sería
 * inventar recetas que nadie pidió.
 */
export function pegar(
  modelo: Modelo,
  desdeFila: number,
  desdeColumna: number,
  bloque: string[][],
): Modelo {
  let siguiente = modelo;
  bloque.forEach((fila, i) => {
    const insumo = modelo.insumos[desdeFila + i];
    if (!insumo) return;
    fila.forEach((valor, j) => {
      const receta = modelo.recetas[desdeColumna + j];
      if (!receta) return;
      siguiente = escribir(siguiente, receta.id, insumo, valor.trim());
    });
  });
  return siguiente;
}

/** Lo que se copia al portapapeles desde la grilla, en el mismo formato que
 * Excel entiende. Ida y vuelta con `leerPegado`. */
export function copiar(modelo: Modelo): string {
  return modelo.insumos
    .map((insumo) =>
      modelo.recetas
        .map(
          (receta) =>
            modelo.celdas.get(clave(receta.id, insumo.articulo_id))?.texto ?? "",
        )
        .join("\t"),
    )
    .join("\n");
}

/** Cuánto aporta cada receta en dinero, con lo que hay en pantalla. Es una
 * vista previa: el costo que vale lo calcula el servidor con `Decimal`. */
export function costo(
  modelo: Modelo,
  recetaId: string,
  evaluar: (texto: string) => number | null,
): number {
  let total = 0;
  for (const insumo of modelo.insumos) {
    const celda = modelo.celdas.get(clave(recetaId, insumo.articulo_id));
    if (!celda) continue;
    const cantidad = evaluar(celda.texto);
    if (cantidad === null) continue;
    total += cantidad * Number(insumo.costo_promedio);
  }
  return total;
}
