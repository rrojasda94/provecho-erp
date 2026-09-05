/**
 * El cuadre de un asiento contable (RN-CTB-001), contado en centavos.
 *
 * `0.1 + 0.2 !== 0.3` en binario, y el asiento se comparaba así en los dos
 * lados: la pantalla dejaba «Registrar» deshabilitado sin decir por qué —el
 * panel mostraba «Diferencia: 0.00»— y la Server Action rechazaba con «no
 * cuadra» un asiento que cuadra. La plata no se suma en flotante: se pasa a
 * la unidad indivisible —el centavo— y ahí la igualdad es exacta.
 *
 * Sin imports, como `lib/errores.ts` y por lo mismo: lo usan el cliente y el
 * servidor, y `node --test` lo corre sin arrastrar nada de Next.
 */

export type LineaCuadre = { tipo: string; monto: string | number };

/**
 * Centavos de un importe tecleado.
 *
 * Un valor ilegible cuenta cero en vez de contagiar `NaN` al total: el campo
 * ya es `required` y `type="number"`, así que lo único que llega acá vacío es
 * una línea a medio escribir, y con `NaN` el panel de cuadre entero decía
 * «NaN» mientras se tipeaba.
 *
 * ponytail: `Math.round` sobre el flotante y no un parseo decimal del texto.
 * Techo conocido: un importe con más de dos decimales exactos a mitad de
 * centavo (`10.555`) redondea según cómo cayó el binario. Los inputs son
 * `step="0.01"`, así que hoy no llega; el día que llegue, es parsear la
 * cadena por la coma decimal, no bajarle la tolerancia a la comparación.
 */
export function aCentavos(monto: string | number): number {
  const n = Number(monto);
  return Number.isFinite(n) ? Math.round(n * 100) : 0;
}

/**
 * Debe, haber y si cuadran. Los dos totales vuelven en soles —es lo que la
 * pantalla muestra— pero se compararon en centavos.
 *
 * `debe > 0` es parte de la regla, no una defensa: un asiento de puros ceros
 * cuadra aritméticamente y no documenta nada.
 */
export function cuadreDe(lineas: LineaCuadre[]): {
  debe: number;
  haber: number;
  cuadra: boolean;
} {
  const suma = (tipo: string) =>
    lineas
      .filter((l) => l.tipo === tipo)
      .reduce((total, l) => total + aCentavos(l.monto), 0);
  const debe = suma("debe");
  const haber = suma("haber");
  return { debe: debe / 100, haber: haber / 100, cuadra: debe > 0 && debe === haber };
}
