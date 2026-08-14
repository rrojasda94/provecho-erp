import { MODULOS } from "./modulos.ts";
import { SUBMENUS } from "./navegacion.ts";

/**
 * El rastro de una pantalla: Inicio / Módulo / Sección / lo que se está viendo.
 *
 * Se **deriva** de la ruta contra los mismos dos registros que alimentan el
 * home, el sidebar y la paleta (`MODULOS` y `SUBMENUS`). Escribirlo a mano en
 * cada ficha era lo que había: nueve `← Sección` cableados uno por uno, que
 * además siempre subían al listado aunque uno viniera de otro lado.
 *
 * Función pura y sin React a propósito: lo que hay que poder probar es la
 * resolución de la ruta, no el dibujo.
 */

export type Miga = { label: string; href: string };

/** La sección cuyo `href` es el prefijo más largo de la ruta. El más largo y
 * no el primero que coincida: `/contabilidad` es prefijo de
 * `/contabilidad/caja`, y con el primero toda pantalla de contabilidad diría
 * "Asientos". */
function seccionDe(clave: string, pathname: string): Miga | null {
  const candidatas = (SUBMENUS[clave] ?? []).filter(
    (s) => pathname === s.href || pathname.startsWith(`${s.href}/`),
  );
  if (candidatas.length === 0) return null;
  const mejor = candidatas.reduce((a, b) => (b.href.length > a.href.length ? b : a));
  return { label: mejor.label, href: mejor.href };
}

/**
 * @param pathname ruta actual (`usePathname()`).
 * @param hoja qué se está viendo, cuando la ruta no alcanza para nombrarlo
 *   (un id no es un nombre). Sin `hoja`, el rastro termina en la sección.
 */
/** El primer tramo de la ruta: `/inventario/lotes/x` → `inventario`. */
function raiz(ruta: string): string {
  return ruta.split("/")[1] ?? "";
}

export function rastroDe(pathname: string, hoja?: string): Miga[] {
  const migas: Miga[] = [{ label: "Inicio", href: "/" }];
  // Por el primer tramo y no por `m.href`: el `href` de un módulo es su
  // **primera pantalla** (`/inventario/articulos`), así que comparar contra él
  // dejaba fuera a todo lo demás del módulo — `/inventario/lotes` no empieza
  // con `/inventario/articulos`.
  const modulo = MODULOS.find((m) => raiz(m.href) === raiz(pathname) && raiz(pathname) !== "");
  if (!modulo) return hoja ? [...migas, { label: hoja, href: pathname }] : migas;

  migas.push({ label: modulo.nombre, href: modulo.href });
  const seccion = seccionDe(modulo.clave, pathname);
  // Una sección que apunta a la misma ruta que su módulo no se repite: el
  // sidebar de `contabilidad` arranca en "Asientos", que **es** `/contabilidad`.
  if (seccion && seccion.href !== modulo.href) migas.push(seccion);
  if (hoja) migas.push({ label: hoja, href: pathname });
  return migas;
}

/** A dónde lleva el `←` cuando no hay historial propio al que volver: el
 * nivel de arriba, que es lo que hacían los `← Sección` de antes. */
export function padreDe(migas: Miga[]): string {
  return migas.length > 1 ? migas[migas.length - 2].href : "/";
}
