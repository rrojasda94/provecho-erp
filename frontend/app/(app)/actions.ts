"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { API_INTERNAL_URL } from "@/lib/api";
import { COOKIE_REFRESH, COOKIE_TOKEN } from "@/lib/auth";

/** Logout compartido por todo el shell — un solo botón, en la barra
 * superior, no uno por pantalla (antes vivía duplicado en cada página). */
export async function logoutAction() {
  const store = await cookies();
  const refresh = store.get(COOKIE_REFRESH)?.value;
  if (refresh) {
    try {
      // Logout es idempotente en la API; un fallo de red acá no debe
      // impedir borrar la cookie local — el usuario tiene que poder salir
      // aunque la API esté caída.
      await fetch(`${API_INTERNAL_URL}/api/v1/auth/logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
    } catch {
      // Sin conexión: se limpia la cookie igual, ver comentario arriba.
    }
  }
  store.delete(COOKIE_TOKEN);
  store.delete(COOKIE_REFRESH);
  redirect("/login");
}
