/**
 * Sesión del PDV/dashboard vía JWT en cookie httpOnly. El decode acá NUNCA
 * verifica la firma — leer un claim (empresa_id) para armar la siguiente
 * llamada no es una decisión de autorización; esa la toma siempre la API
 * (que sí valida la firma y el permiso en cada request). Si alguien
 * manipulara el token, la API lo rechaza igual.
 */

// Definidos en `sesion-refresh` y reexportados desde ahí para no partir
// el nombre de la cookie en dos archivos: el middleware que renueva la
// sesión corre en el runtime Edge y no puede importar este módulo, que
// usa `Buffer`.
export { COOKIE_REFRESH, COOKIE_TOKEN } from "@/lib/sesion-refresh";

export type ClaimsJwt = {
  sub: string;
  tipo: string;
  roles: string[];
  sucursales: string[];
  empresa_id: string | null;
  exp: number;
};

export function decodificarClaims(token: string): ClaimsJwt | null {
  try {
    const payload = token.split(".")[1];
    const json = Buffer.from(payload, "base64url").toString("utf-8");
    return JSON.parse(json) as ClaimsJwt;
  } catch {
    return null;
  }
}
