/**
 * Filtro de permisos en el cliente/servidor de Next — puramente UX (grid del
 * home, sidebar). Nunca es la autorización real: esa la hace la API en cada
 * request (`require_permission`, deny por defecto). Un guard server-side por
 * `layout.tsx` de módulo repite el mismo chequeo antes de renderizar
 * cualquier dato, así que entrar por URL directa sin el permiso no filtra
 * nada (F2.7/F2.28, ADR-013).
 */

import type { Modulo } from "./modulos.ts";

const COMODIN = "*";

/** ¿El usuario tiene algún permiso que empiece con `prefijo` (ej. "inventory.")? */
export function tieneAccesoModulo(permisos: string[], prefijo: string): boolean {
  return permisos.includes(COMODIN) || permisos.some((p) => p.startsWith(prefijo));
}

/** ¿Tiene exactamente ese permiso? Para gates puntuales (un botón, una acción). */
export function tienePermiso(permisos: string[], codigo: string): boolean {
  return permisos.includes(COMODIN) || permisos.includes(codigo);
}

/**
 * ¿Le corresponde este módulo? Un `permiso` exacto en la definición manda
 * sobre el prefijo: es la diferencia entre "trabaja en el área" y "le toca
 * administrar esto". Sin esta distinción, un cajero (`sales.crear`) entraba
 * al Catálogo por tener un permiso del área.
 */
export function puedeVerModulo(permisos: string[], modulo: Modulo): boolean {
  return modulo.permiso
    ? tienePermiso(permisos, modulo.permiso)
    : tieneAccesoModulo(permisos, modulo.prefijoPermiso);
}

/**
 * ¿Es la cuenta de administración? Misma condición que `_solo_superusuario`
 * aplica en el backend: comodín **y** sin empresa asignada. Es lo que
 * distingue "administra su empresa" de "funda empresas", y decide si la
 * pantalla ofrece esas acciones o no — ofrecerlas a un admin de empresa
 * sería prometer un 403.
 *
 * Sigue siendo UX: la autorización real la hace la API en cada request.
 */
export function esCuentaDeAdministracion(usuario: {
  permisos: string[];
  empresa_id: string | null;
}): boolean {
  return usuario.permisos.includes(COMODIN) && usuario.empresa_id === null;
}
