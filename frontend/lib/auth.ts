/**
 * Sesión del PDV/dashboard vía JWT en cookie httpOnly. El decode acá NUNCA
 * verifica la firma — leer un claim (empresa_id) para armar la siguiente
 * llamada no es una decisión de autorización; esa la toma siempre la API
 * (que sí valida la firma y el permiso en cada request). Si alguien
 * manipulara el token, la API lo rechaza igual.
 */

export const COOKIE_TOKEN = "provecho_token";
export const COOKIE_REFRESH = "provecho_refresh";
/** El secreto del terminal enrolado (ADR-073) — nada que ver con la sesión
 * de la cuenta de servicio del pad. httpOnly igual que el token: el
 * JavaScript de la página nunca lo ve. */
export const COOKIE_TERMINAL = "provecho_terminal";

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
