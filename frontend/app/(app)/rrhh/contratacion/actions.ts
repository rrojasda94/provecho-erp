"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type EstadoRrhh = { error: string; ok: boolean };

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function mensajeDe(e: unknown, porDefecto: string): string {
  return e instanceof ApiError ? e.message : porDefecto;
}

function texto(datos: FormData, campo: string): string {
  return String(datos.get(campo) ?? "").trim();
}

function opcional(datos: FormData, campo: string): string | undefined {
  return texto(datos, campo) || undefined;
}

export async function crearConvocatoriaAction(
  _previo: EstadoRrhh,
  datos: FormData,
): Promise<EstadoRrhh> {
  const puesto = texto(datos, "puesto");
  const motivo = texto(datos, "motivo");
  if (!puesto || !motivo) {
    return { error: "El puesto y el motivo son obligatorios.", ok: false };
  }

  try {
    await apiFetch("/api/v1/rrhh/convocatorias", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        puesto,
        motivo,
        perfil_puesto: opcional(datos, "perfil_puesto"),
        vacantes: Number(datos.get("vacantes") ?? 1),
        remuneracion_min: opcional(datos, "remuneracion_min"),
        remuneracion_max: opcional(datos, "remuneracion_max"),
        fecha_objetivo: opcional(datos, "fecha_objetivo"),
        fecha_limite: opcional(datos, "fecha_limite"),
      },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo crear la convocatoria."), ok: false };
  }
  revalidatePath("/rrhh/contratacion");
  return { error: "", ok: true };
}

/** Publicar exige perfil de puesto (RN-RRHH-013). Se permite adjuntarlo en
 * este mismo paso: obligar a volver a la ficha para escribir una línea es la
 * clase de fricción que termina en un perfil inventado con tal de avanzar. */
export async function publicarConvocatoriaAction(
  _previo: EstadoRrhh,
  datos: FormData,
): Promise<EstadoRrhh> {
  const id = texto(datos, "convocatoria_id");
  const fecha = texto(datos, "fecha_publicacion");
  if (!id || !fecha) return { error: "Falta la fecha de publicación.", ok: false };

  try {
    await apiFetch(`/api/v1/rrhh/convocatorias/${id}/publicar`, {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        fecha_publicacion: fecha,
        perfil_puesto: opcional(datos, "perfil_puesto"),
      },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo publicar la convocatoria."), ok: false };
  }
  revalidatePath("/rrhh/contratacion");
  return { error: "", ok: true };
}

export async function cerrarConvocatoriaAction(
  convocatoriaId: string,
): Promise<EstadoRrhh> {
  try {
    await apiFetch(`/api/v1/rrhh/convocatorias/${convocatoriaId}/cerrar`, {
      token: await token(),
      metodo: "POST",
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo cerrar la convocatoria."), ok: false };
  }
  revalidatePath("/rrhh/contratacion");
  return { error: "", ok: true };
}

/** Avanza **una** columna. El servidor rechaza el salto de etapa; acá no se
 * ofrece siquiera, porque un tablero que deja saltar de "recibido" a
 * "contratado" convierte el historial en una firma sin respaldo. */
export async function avanzarPostulanteAction(
  postulanteId: string,
  estado: string,
): Promise<EstadoRrhh> {
  try {
    await apiFetch(`/api/v1/rrhh/postulantes/${postulanteId}/avanzar`, {
      token: await token(),
      metodo: "POST",
      cuerpo: { estado },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo avanzar al postulante."), ok: false };
  }
  revalidatePath("/rrhh/contratacion");
  return { error: "", ok: true };
}

/** El motivo es obligatorio y no es burocracia: ante un reclamo por
 * discriminación (Ley 26772) el descarte sin motivo registrado es la
 * empresa sin defensa. */
export async function descartarPostulanteAction(
  _previo: EstadoRrhh,
  datos: FormData,
): Promise<EstadoRrhh> {
  const id = texto(datos, "postulante_id");
  const motivo = texto(datos, "motivo");
  if (!motivo) {
    return { error: "El descarte necesita un motivo registrado.", ok: false };
  }

  try {
    await apiFetch(`/api/v1/rrhh/postulantes/${id}/descartar`, {
      token: await token(),
      metodo: "POST",
      cuerpo: { motivo },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo descartar al postulante."), ok: false };
  }
  revalidatePath("/rrhh/contratacion");
  return { error: "", ok: true };
}

/** Contratar es lo que convierte al candidato en persona del grupo: recién
 * acá nacen `persona` y `trabajador` (o se reusa la persona del
 * recontratado, RN-GEN-007). */
export async function contratarPostulanteAction(
  _previo: EstadoRrhh,
  datos: FormData,
): Promise<EstadoRrhh> {
  const id = texto(datos, "postulante_id");
  const cargo = texto(datos, "cargo");
  const area = texto(datos, "area");
  const fechaIngreso = texto(datos, "fecha_ingreso");
  if (!cargo || !area || !fechaIngreso) {
    return { error: "Cargo, área y fecha de ingreso son obligatorios.", ok: false };
  }

  try {
    await apiFetch(`/api/v1/rrhh/postulantes/${id}/contratar`, {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        cargo,
        area,
        tipo_vinculo: texto(datos, "tipo_vinculo") || "planilla",
        fecha_ingreso: fechaIngreso,
        tipo_documento: opcional(datos, "tipo_documento"),
        numero_documento: opcional(datos, "numero_documento"),
        // Lo que quedó en pantalla tras contrastarlo con RENIEC. Vacío = el
        // servidor usa lo que el postulante declaró de sí mismo.
        nombres: opcional(datos, "nombres"),
        apellidos: opcional(datos, "apellidos"),
        remuneracion_base: opcional(datos, "remuneracion_base"),
        // Locación de servicios nunca marca asistencia (RN-PER-002): el
        // servidor lo rechaza, y ofrecerlo acá sería invitar al error.
        registra_asistencia: texto(datos, "tipo_vinculo") !== "locacion_servicios",
        // Sin esto la ficha nacía sin centro de labores y no aparecía en
        // ningún pad de asistencia.
        sucursal_id: opcional(datos, "sucursal_id"),
      },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo contratar al postulante."), ok: false };
  }
  revalidatePath("/rrhh/contratacion");
  return { error: "", ok: true };
}
