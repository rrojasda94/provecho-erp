"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { estadoDeError, type EstadoFormulario } from "@/lib/errores";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

/** Quién aprueba sale del token, nunca del cuerpo: el aprobador es quien
 * está firmando, y dejarlo elegir a la pantalla sería poder firmar por otro
 * (RN-RRHH-005). */
async function resolver(ruta: string, verbo: string): Promise<EstadoFormulario> {
  try {
    await apiFetch(ruta, { token: await token(), metodo: "POST" });
  } catch (e) {
    return estadoDeError(e, `No se pudo ${verbo} la solicitud.`);
  }
  revalidatePath("/rrhh/permisos");
  return { error: "", ok: true };
}

// Las dos rutas se escriben enteras y no se arman con la decisión de por
// medio: `lib/contrato.test.ts` verifica contra el OpenAPI que toda ruta que
// el frontend nombra exista, y no puede resolver un tramo variable.
export async function aprobarPermisoAction(id: string): Promise<EstadoFormulario> {
  return resolver(`/api/v1/rrhh/solicitudes-permiso/${id}/aprobar`, "aprobar");
}

export async function rechazarPermisoAction(id: string): Promise<EstadoFormulario> {
  return resolver(`/api/v1/rrhh/solicitudes-permiso/${id}/rechazar`, "rechazar");
}

type CamposPermiso = {
  trabajadorId: string;
  tipo: string;
  desde: string;
  hasta: string;
  motivo: string;
};

function leerCampos(formData: FormData): CamposPermiso {
  return {
    trabajadorId: String(formData.get("trabajador_id") ?? ""),
    tipo: String(formData.get("tipo") ?? "").trim(),
    desde: String(formData.get("fecha_desde") ?? ""),
    hasta: String(formData.get("fecha_hasta") ?? ""),
    motivo: String(formData.get("motivo") ?? "").trim(),
  };
}

/** El primer campo que falta, o vacío. Aparte de la acción para que el
 * chequeo no cuente contra su complejidad — el lint la mide por función. */
function queFalta(c: CamposPermiso): string {
  if (!c.trabajadorId) return "Elegí de quién es el permiso.";
  if (!c.tipo) return "Falta el tipo de permiso.";
  if (!c.desde) return "Falta la fecha de inicio.";
  return "";
}

/** El permiso lo carga RRHH o el encargado por el trabajador: el ERP no tiene
 * autoservicio del empleado todavía, así que el solicitante se elige. */
export async function crearPermisoAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const campos = leerCampos(formData);
  const falta = queFalta(campos);
  if (falta) return { error: falta, ok: false };
  const { trabajadorId, tipo, desde, hasta, motivo } = campos;

  try {
    await apiFetch("/api/v1/rrhh/solicitudes-permiso", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        trabajador_id: trabajadorId,
        tipo,
        fecha_desde: desde,
        fecha_hasta: hasta || undefined,
        motivo: motivo || undefined,
      },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo registrar la solicitud.");
  }
  revalidatePath("/rrhh/permisos");
  return { error: "", ok: true };
}
