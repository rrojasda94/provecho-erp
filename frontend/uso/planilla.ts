import { execFileSync } from "node:child_process";

/**
 * Leer y escribir `.xlsx` desde una prueba de uso, con **openpyxl**.
 *
 * Es la misma librería que usa el backend (`importacion_recetas.py`), y eso
 * es lo que la hace valer como verificación: que la plantilla descargada
 * abra acá significa que abre en el importador y en Excel, no que un lector
 * tolerante de Node consiguió sacarle algo. El bug que motivó todo esto
 * —el proxy decodificando un ZIP como texto UTF-8— produce un archivo que
 * *parece* estar ahí: pesa, se guarda, y recién revienta al abrirlo.
 *
 * El intérprete sale de `e2e/interprete.mjs`, el mismo que prepara la base:
 * en un worktree no hay `.venv` propio y el `python` del PATH no tiene
 * openpyxl. Duplicar esa búsqueda acá sería la segunda copia que envejece.
 */

/** Una planilla como la ve quien la llena: hoja → filas → celdas. */
export type Hojas = Record<string, (string | number)[][]>;

const ESCRIBIR = `
import json, sys
from openpyxl import Workbook

hojas = json.load(sys.stdin)
libro = Workbook()
for indice, (nombre, filas) in enumerate(hojas.items()):
    hoja = libro.active if indice == 0 else libro.create_sheet()
    hoja.title = nombre
    for fila in filas:
        hoja.append(fila)
libro.save(sys.argv[1])
`;

const LEER = `
import json, sys
from openpyxl import load_workbook

libro = load_workbook(sys.argv[1], read_only=True, data_only=True)
primera = next(libro[libro.sheetnames[0]].iter_rows(values_only=True))
print(json.dumps({
    "hojas": libro.sheetnames,
    "primeraFila": ["" if c is None else str(c) for c in primera],
}))
`;

/**
 * `import()` y no un `import` estático: Playwright compila las specs a
 * CommonJS, y un `.mjs` requerido desde ahí se carga **como CJS** —
 * `import.meta` revienta antes del primer `expect`, con un error que habla
 * de `type: module` y no de Playwright. El dinámico lo resuelve Node en
 * tiempo de ejecución, que es cuando ya sabe que el módulo es ESM.
 *
 * Y no una copia de la búsqueda del intérprete: `e2e/interprete.mjs` explica
 * en su cabecera por qué son cuatro pasos, y la copia que se hiciera acá
 * envejecería sola.
 */
const arnes = () => import("../e2e/interprete.mjs");

async function python(codigo: string, archivo: string, entrada?: string): Promise<string> {
  const { RAIZ, interprete } = await arnes();
  return execFileSync(interprete(), ["-c", codigo, archivo], {
    cwd: RAIZ,
    encoding: "utf8",
    input: entrada,
    // Sin esto, en Windows Python escribe el JSON con la codificación de la
    // consola y «Produce el artículo» vuelve con la tilde rota — un fallo
    // que parece del archivo y es del caño.
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
    stdio: ["pipe", "pipe", "inherit"],
  });
}

/** Deja un `.xlsx` de verdad en `archivo`. */
export async function escribirPlanilla(archivo: string, hojas: Hojas): Promise<void> {
  await python(ESCRIBIR, archivo, JSON.stringify(hojas));
}

/**
 * Abre el `.xlsx` y devuelve lo suficiente para afirmar que **es** uno: sus
 * hojas y la cabecera de la primera. Si el archivo está corrupto, openpyxl
 * levanta y `execFileSync` propaga — que es el resultado que se busca.
 */
export async function leerPlanilla(
  archivo: string,
): Promise<{ hojas: string[]; primeraFila: string[] }> {
  return JSON.parse(await python(LEER, archivo));
}
