"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type EstadoTurno = EstadoFormulario;

const RUTA = "/rrhh/turnos";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function texto(formData: FormData, campo: string): string {
  return String(formData.get(campo) ?? "").trim();
}

/** `<input type="time">` manda `HH:MM`; la API espera `HH:MM:SS`. */
function hora(formData: FormData, campo: string): string {
  const valor = texto(formData, campo);
  return valor.length === 5 ? `${valor}:00` : valor;
}

type Campos = {
  nombre: string;
  hora_inicio: string;
  hora_fin: string;
  hora_limite_salida: string;
  tolerancia_min: number;
};

/** Lo que el servidor revalida igual: acá solo evita el viaje. */
function leerCampos(formData: FormData): Campos | string {
  const nombre = texto(formData, "nombre");
  const horaInicio = hora(formData, "hora_inicio");
  const horaFin = hora(formData, "hora_fin");
  const horaLimite = hora(formData, "hora_limite_salida");
  const tolerancia = Number(texto(formData, "tolerancia_min") || "5");

  if (!nombre) return "El nombre del turno es obligatorio.";
  if (!horaInicio || !horaFin || !horaLimite) return "Faltan las horas del turno.";
  if (!Number.isInteger(tolerancia) || tolerancia < 0 || tolerancia > 120) {
    return "La tolerancia va de 0 a 120 minutos.";
  }
  return {
    nombre,
    hora_inicio: horaInicio,
    hora_fin: horaFin,
    hora_limite_salida: horaLimite,
    tolerancia_min: tolerancia,
  };
}

/** Alta y edición en una sola acción: con `id` es PATCH, sin él POST. La
 * sucursal solo se elige al crear — mudar un turno de local dejaría las
 * marcaciones ya medidas contra un horario de otro sitio. */
export async function guardarTurnoAction(
  _previo: EstadoTurno,
  formData: FormData,
): Promise<EstadoTurno> {
  const id = texto(formData, "id");
  const cuerpo = leerCampos(formData);
  if (typeof cuerpo === "string") return { error: cuerpo, ok: false };

  try {
    if (id) {
      await apiFetch(`/api/v1/rrhh/turnos/${id}`, {
        token: await token(),
        metodo: "PATCH",
        cuerpo: { ...cuerpo, activo: formData.get("activo") === "on" },
      });
    } else {
      const sucursalId = texto(formData, "sucursal_id");
      if (!sucursalId) return { error: "Elegir la sucursal.", ok: false };
      await apiFetch("/api/v1/rrhh/turnos", {
        token: await token(),
        metodo: "POST",
        cuerpo: { ...cuerpo, sucursal_id: sucursalId },
      });
    }
  } catch (e) {
    const mensaje = e instanceof ApiError ? e.message : "No se pudo guardar el turno.";
    return { error: mensaje, ok: false };
  }

  revalidatePath(RUTA);
  return { error: "", ok: true };
}
