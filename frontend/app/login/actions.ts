"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_REFRESH, COOKIE_TOKEN } from "@/lib/auth";
import {
  MAX_AGE_ACCESS,
  MAX_AGE_REFRESH,
  opcionesCookie,
} from "@/lib/sesion-refresh";

type TokenPair = { access_token: string; refresh_token: string; token_type: string };

/**
 * Por qué el estado del login no es solo un texto (ADR-050).
 *
 * El servidor distingue tres negativas y hasta acá llegaban todas iguales,
 * porque la acción devolvía `e.message` sin mirar el status: "PIN
 * equivocado" (401), "cuenta bloqueada quince minutos" (423) y "demasiados
 * intentos desde esta IP" (429). Quien las recibe necesita cosas distintas
 * —volver a teclear, esperar, o llamar a un supervisor— y con un solo texto
 * genérico las tres terminan en el mismo lugar: probar de nuevo hasta
 * bloquear la cuenta.
 *
 * El `motivo` viaja aparte del texto para que la pantalla pueda distinguir
 * sin leer copy (y para que una prueba pueda afirmarlo sin atarse a la
 * redacción).
 */
export type MotivoLogin =
  | ""
  /** Falta el usuario o el PIN no tiene seis dígitos: no se llamó a la API. */
  | "incompleto"
  | "credenciales"
  | "bloqueo"
  | "limite"
  | "servidor";

export type EstadoLogin = { error: string; motivo: MotivoLogin };


// Los del lockout del servidor (`src/modules/users/domain/rules.py`:
// MAX_INTENTOS_FALLIDOS / DURACION_BLOQUEO). Se repiten acá para poder
// decirle a la persona cuánto va a esperar; el que decide sigue siendo el
// servidor. **No hay contador de intentos en el cliente**: el estado real
// vive allá y un contador local mentiría en cuanto alguien abra otra
// pestaña.
const INTENTOS_ANTES_DEL_BLOQUEO = 5;
const MINUTOS_DE_BLOQUEO = 15;

const LARGO_PIN = 6;

/**
 * Único destino post-login que no es el home (ADR-083 Fase B): la mitad del
 * SSO del BI que quedó cortada por no tener sesión de Provecho todavía. Se
 * valida por regex exacta —no basta con no ser absoluta— porque `next` sale
 * de la URL y un valor cualquiera ahí sería la puerta a un open redirect: el
 * login es la pantalla que menos puede darse ese lujo.
 */
const SIGUIENTE_PERMITIDO = /^\/oauth\/authorize(\?[^\s]*)?$/;

/** Cuánto falta, dicho como se dice en voz alta y no en segundos. */
function espera(segundos: number | undefined): string {
  if (!segundos) return "un momento";
  if (segundos <= 90) return "un minuto";
  return `${Math.ceil(segundos / 60)} minutos`;
}

function comoError(e: ApiError): EstadoLogin {
  if (e.status === 401) {
    return {
      error:
        "Usuario o PIN incorrectos. Después de " +
        `${INTENTOS_ANTES_DEL_BLOQUEO} intentos seguidos la cuenta se bloquea.`,
      motivo: "credenciales",
    };
  }
  if (e.status === 423) {
    return {
      error:
        `Cuenta bloqueada por ${INTENTOS_ANTES_DEL_BLOQUEO} intentos fallidos. ` +
        `Vuelve a intentar en ${MINUTOS_DE_BLOQUEO} minutos, o pide a un ` +
        "supervisor que reinicie tu PIN.",
      motivo: "bloqueo",
    };
  }
  if (e.status === 429) {
    return {
      error:
        `Demasiados intentos desde este equipo. Espera ${espera(e.reintentarEn)} ` +
        "y vuelve a intentar.",
      motivo: "limite",
    };
  }
  // Cualquier otra cosa se muestra tal como la contó el servidor: inventarle
  // un texto amable a un fallo desconocido lo vuelve indiagnosticable.
  return { error: e.message, motivo: "servidor" };
}

export async function loginAction(
  _previo: EstadoLogin,
  formData: FormData,
): Promise<EstadoLogin> {
  const username = String(formData.get("username") ?? "").trim();
  const pin = String(formData.get("pin") ?? "").trim();

  if (!username) {
    return { error: "Escribe tu usuario.", motivo: "incompleto" };
  }
  // Se corta acá y no en el servidor a propósito: un PIN corto sería un 401
  // y **gastaría uno de los cinco intentos** que bloquean la cuenta. Con el
  // pinpad esto se puede dar sin querer —el botón envía lo que haya— y
  // bloquear a alguien por haber tocado "Ingresar" de más sería nuestro.
  if (pin.length !== LARGO_PIN) {
    return { error: `El PIN son ${LARGO_PIN} dígitos.`, motivo: "incompleto" };
  }

  let tokens: TokenPair;
  try {
    tokens = await apiFetch<TokenPair>("/api/v1/auth/login", {
      metodo: "POST",
      cuerpo: { username, pin },
    });
  } catch (e) {
    if (e instanceof ApiError) {
      return comoError(e);
    }
    return {
      error: "No se pudo conectar con el servidor. Intenta de nuevo.",
      motivo: "servidor",
    };
  }

  const store = await cookies();
  // Las mismas opciones que usa la renovación del middleware (ADR-073):
  // dos juegos distintos dejarían dos cookies del mismo nombre y la sesión
  // volvería a caducar a los quince minutos aunque se esté renovando.
  store.set(COOKIE_TOKEN, tokens.access_token, opcionesCookie(MAX_AGE_ACCESS));
  store.set(
    COOKIE_REFRESH,
    tokens.refresh_token,
    opcionesCookie(MAX_AGE_REFRESH),
  );

  const siguiente = String(formData.get("next") ?? "");
  if (SIGUIENTE_PERMITIDO.test(siguiente)) redirect(siguiente);

  // Home de apps (F2.6a, ADR-013), no el dashboard directo — el usuario
  // elige el módulo, el dashboard es una app más del grid.
  redirect("/");
}
