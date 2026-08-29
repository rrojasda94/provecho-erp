"use server";

import { cookies } from "next/headers";

import { COOKIE_TERMINAL } from "@/lib/auth";

// Mismo criterio que `COOKIE_SECURE` en `login/actions.ts`: la demo portable
// se sirve por http sin TLS, y una cookie `Secure` ahí se descarta en
// silencio.
const ES_PRODUCCION = process.env.COOKIE_SECURE
  ? process.env.COOKIE_SECURE === "true"
  : process.env.NODE_ENV === "production";
// Un año: enrolar es un gesto de admin sobre una tablet fija, no algo que
// deba repetirse seguido — a diferencia del token de sesión, que expira en
// minutos.
const DIAS_TERMINAL = 365;

/** Guarda el secreto que devolvió `POST /asistencia/terminal/enrolar` en la
 * cookie httpOnly del terminal (ADR-079). Aparte de `loginAction` porque
 * activa un dispositivo, no una persona: la sesión de la cuenta de
 * servicio y el secreto del terminal viven en cookies distintas y con
 * vigencias distintas. */
export async function guardarTerminalAction(secreto: string): Promise<void> {
  const store = await cookies();
  store.set(COOKIE_TERMINAL, secreto, {
    httpOnly: true,
    secure: ES_PRODUCCION,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * DIAS_TERMINAL,
  });
}
