"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { API_INTERNAL_URL, apiFetch } from "@/lib/api";
import { COOKIE_REFRESH, COOKIE_TOKEN } from "@/lib/auth";
import type { Paleta, TamanoFuente, Tema } from "@/lib/sesion";

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

/** Guarda tema, tamaño de letra o paleta en el perfil — no en el navegador
 * (docs/product/ui-ux.md): en un local la misma tablet la usan tres turnos y
 * la misma persona salta de la caja a la oficina. `revalidatePath("/", "layout")`
 * es lo que hace que el cambio se vea sin recargar: los atributos viven en
 * `<html>`, que lo pinta el layout raíz. */
export async function guardarPreferenciaAction(
  cambio:
    | { tema: Tema }
    | { tamano_fuente: TamanoFuente }
    | { paleta: Paleta },
) {
  const store = await cookies();
  const token = store.get(COOKIE_TOKEN)?.value;
  if (!token) redirect("/login");

  await apiFetch("/api/v1/users/me/preferencias", {
    token,
    metodo: "PATCH",
    cuerpo: cambio,
  });
  revalidatePath("/", "layout");
}
