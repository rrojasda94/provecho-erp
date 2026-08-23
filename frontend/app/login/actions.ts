"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_REFRESH, COOKIE_TOKEN } from "@/lib/auth";

type TokenPair = { access_token: string; refresh_token: string; token_type: string };

export type EstadoLogin = { error: string };

// `secure` sigue a NODE_ENV salvo que se diga lo contrario. El override
// existe para la demo portable, que se sirve por http sin TLS: desde otra
// máquina de la red (`http://192.168.x.x:3000`, la tablet del local) el
// navegador descarta una cookie `Secure` y el login falla **en silencio** —
// devuelve al formulario sin error. En `localhost` no se nota, porque los
// navegadores lo tratan como contexto seguro.
const ES_PRODUCCION = process.env.COOKIE_SECURE
  ? process.env.COOKIE_SECURE === "true"
  : process.env.NODE_ENV === "production";
// Mismos plazos que el backend (access_token_minutes / refresh_token_days,
// settings.py) — la cookie no debe sobrevivir más que el token que guarda.
const MINUTOS_ACCESS = 15;
const DIAS_REFRESH = 7;

export async function loginAction(
  _previo: EstadoLogin,
  formData: FormData,
): Promise<EstadoLogin> {
  const username = String(formData.get("username") ?? "").trim();
  const pin = String(formData.get("pin") ?? "").trim();

  if (!username || !pin) {
    return { error: "Usuario y PIN son obligatorios." };
  }

  let tokens: TokenPair;
  try {
    tokens = await apiFetch<TokenPair>("/api/v1/auth/login", {
      metodo: "POST",
      cuerpo: { username, pin },
    });
  } catch (e) {
    if (e instanceof ApiError) {
      return { error: e.message };
    }
    return { error: "No se pudo conectar con el servidor. Intentar de nuevo." };
  }

  const store = await cookies();
  store.set(COOKIE_TOKEN, tokens.access_token, {
    httpOnly: true,
    secure: ES_PRODUCCION,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * MINUTOS_ACCESS,
  });
  store.set(COOKIE_REFRESH, tokens.refresh_token, {
    httpOnly: true,
    secure: ES_PRODUCCION,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * DIAS_REFRESH,
  });

  // Home de apps (F2.6a, ADR-013), no el dashboard directo — el usuario
  // elige el módulo, el dashboard es una app más del grid.
  redirect("/");
}
