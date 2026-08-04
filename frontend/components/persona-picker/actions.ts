"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type PersonaBusqueda = {
  id: string;
  nombres: string;
  apellidos: string;
  numero_documento: string | null;
};

/** Typeahead de `/personas/buscar` (RN-GEN-007, party model) — nunca la
 * ficha completa, y abierto a `personas.leer` (no exige `users.gestionar`).
 * Falla en silencio hacia una lista vacía: es un buscador incidental dentro
 * de otro formulario, no una pantalla con su propio estado de error. */
export async function buscarPersonasAction(q: string): Promise<PersonaBusqueda[]> {
  const store = await cookies();
  const token = store.get(COOKIE_TOKEN)?.value;
  if (!token) redirect("/login");

  try {
    return await apiFetch<PersonaBusqueda[]>(
      `/api/v1/personas/buscar?q=${encodeURIComponent(q)}`,
      { token },
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) redirect("/login");
    return [];
  }
}
