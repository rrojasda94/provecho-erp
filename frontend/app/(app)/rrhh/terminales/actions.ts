"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

const RUTA = "/rrhh/terminales";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

/** El código sale una sola vez, igual que el token de un agente: si se
 * pierde no se vuelve a mostrar, se crea otro terminal. */
export type EstadoTerminal = {
  error: string;
  ok: boolean;
  codigo?: string;
  terminalNombre?: string;
};

export async function crearTerminalAction(
  _previo: EstadoTerminal,
  formData: FormData,
): Promise<EstadoTerminal> {
  const sucursalId = String(formData.get("sucursal_id") ?? "").trim();
  const nombre = String(formData.get("nombre") ?? "").trim();
  if (!sucursalId) return { error: "Elegir la sucursal.", ok: false };
  if (!nombre) return { error: "El nombre del terminal es obligatorio.", ok: false };

  try {
    const { terminal, codigo } = await apiFetch<{
      terminal: { nombre: string };
      codigo: string;
    }>("/api/v1/rrhh/terminales", {
      token: await token(),
      metodo: "POST",
      cuerpo: { sucursal_id: sucursalId, nombre },
    });
    revalidatePath(RUTA);
    return { error: "", ok: true, codigo, terminalNombre: terminal.nombre };
  } catch (e) {
    const mensaje = e instanceof ApiError ? e.message : "No se pudo crear el terminal.";
    return { error: mensaje, ok: false };
  }
}

export async function revocarTerminalAction(terminalId: string): Promise<void> {
  await apiFetch(`/api/v1/rrhh/terminales/${terminalId}`, {
    token: await token(),
    metodo: "DELETE",
  });
  revalidatePath(RUTA);
}
