"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type EstadoGerencia = { error: string; ok: boolean };

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function mensajeDe(e: unknown, porDefecto: string): string {
  return e instanceof ApiError ? e.message : porDefecto;
}

/** El valor de un parámetro es una magnitud con su unidad (RN-GER-010): un
 * monto lleva divisa, una cantidad lleva unidad de medida, y solo lo
 * adimensional (un porcentaje, un plazo en días) va suelto. El backend
 * rechaza con 422 lo que no cumpla — acá solo se arma la forma. */
function armarValor(formData: FormData): Record<string, unknown> | null {
  const tipo = String(formData.get("tipo_valor") ?? "monto");
  const numero = String(formData.get("valor_numero") ?? "").trim();
  if (tipo === "monto") {
    return { monto: numero, divisa: String(formData.get("divisa") ?? "PEN") };
  }
  if (tipo === "cantidad") {
    return {
      cantidad: numero,
      unidad_medida_id: String(formData.get("unidad_medida_id") ?? ""),
    };
  }
  // Adimensional: la clave la elige quien propone (`dias`, `porcentaje`...).
  const clave = String(formData.get("clave_libre") ?? "").trim();
  if (!clave) return null;
  return { [clave]: numero };
}

export async function proponerParametroAction(
  _previo: EstadoGerencia,
  formData: FormData,
): Promise<EstadoGerencia> {
  const campo = (clave: string) => String(formData.get(clave) ?? "").trim();
  const propuesta = {
    empresa_id: campo("empresa_id"),
    modulo: campo("modulo"),
    codigo: campo("codigo"),
    valor: armarValor(formData),
    motivo: campo("motivo") || undefined,
  };
  if (!propuesta.empresa_id || !propuesta.modulo || !propuesta.codigo) {
    return { error: "Empresa, módulo y código son obligatorios.", ok: false };
  }
  if (propuesta.valor === null) return { error: "Falta el nombre del valor.", ok: false };

  try {
    await apiFetch("/api/v1/parametros", {
      token: await token(),
      metodo: "POST",
      cuerpo: propuesta,
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo proponer el parámetro."), ok: false };
  }
  revalidatePath("/gerencia/parametros");
  return { error: "", ok: true };
}

export async function aprobarParametroAction(
  _previo: EstadoGerencia,
  formData: FormData,
): Promise<EstadoGerencia> {
  const parametroId = String(formData.get("parametro_id") ?? "");
  const modificar = formData.get("modificar") === "on";
  if (!parametroId) return { error: "Falta el parámetro.", ok: false };

  try {
    await apiFetch(`/api/v1/parametros/${parametroId}/aprobar`, {
      token: await token(),
      metodo: "POST",
      // Sin `valor` se aprueba tal cual se propuso; con `valor`, Gerencia lo
      // modifica antes de aprobar (la tercera opción de ADR-014 Addendum).
      cuerpo: { valor: modificar ? armarValor(formData) : null },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo aprobar el parámetro."), ok: false };
  }
  revalidatePath("/gerencia/parametros");
  return { error: "", ok: true };
}

export async function rechazarParametroAction(
  _previo: EstadoGerencia,
  formData: FormData,
): Promise<EstadoGerencia> {
  const parametroId = String(formData.get("parametro_id") ?? "");
  const motivo = String(formData.get("motivo_rechazo") ?? "").trim();
  if (!parametroId || !motivo) {
    return { error: "Rechazar exige decir por qué.", ok: false };
  }

  try {
    await apiFetch(`/api/v1/parametros/${parametroId}/rechazar`, {
      token: await token(),
      metodo: "POST",
      cuerpo: { motivo_rechazo: motivo },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo rechazar el parámetro."), ok: false };
  }
  revalidatePath("/gerencia/parametros");
  return { error: "", ok: true };
}

function leerActa(formData: FormData) {
  const campo = (clave: string) => String(formData.get(clave) ?? "").trim();
  return {
    tipo: campo("tipo"),
    referencia_tipo: campo("referencia_tipo"),
    referencia_id: campo("referencia_id"),
    sustento: campo("sustento"),
    resultado: campo("resultado"),
    fecha: campo("fecha"),
    // `undefined` y no cadena vacía: son opcionales del schema, y "" no es
    // un valor válido para ninguno de los dos.
    condiciones: campo("condiciones") || undefined,
    ejecuta_area: campo("ejecuta_area") || undefined,
  };
}

export async function registrarDecisionAction(
  _previo: EstadoGerencia,
  formData: FormData,
): Promise<EstadoGerencia> {
  const acta = leerActa(formData);
  if (!acta.referencia_id || !acta.sustento) {
    return { error: "Referencia y sustento son obligatorios.", ok: false };
  }
  // El backend responde 409, pero decirlo acá evita el viaje y explica la
  // regla: un acta que no dice qué cumplir no sirve de nada.
  if (acta.resultado === "aprobado_con_condiciones" && !acta.condiciones) {
    return { error: "Aprobar con condiciones exige escribir cuáles.", ok: false };
  }

  try {
    await apiFetch("/api/v1/decisiones-gerenciales", {
      token: await token(),
      metodo: "POST",
      cuerpo: acta,
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo registrar el acta."), ok: false };
  }
  revalidatePath("/gerencia/decisiones");
  return { error: "", ok: true };
}

export async function crearDivisaAction(
  _previo: EstadoGerencia,
  formData: FormData,
): Promise<EstadoGerencia> {
  const codigo = String(formData.get("codigo") ?? "").trim().toUpperCase();
  const nombre = String(formData.get("nombre") ?? "").trim();
  const simbolo = String(formData.get("simbolo") ?? "").trim();
  if (codigo.length !== 3 || !nombre || !simbolo) {
    return { error: "Código ISO de 3 letras, nombre y símbolo.", ok: false };
  }

  try {
    await apiFetch("/api/v1/divisas", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        codigo,
        nombre,
        simbolo,
        decimales: Number(formData.get("decimales") ?? 2),
      },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo crear la divisa."), ok: false };
  }
  revalidatePath("/gerencia/divisas");
  return { error: "", ok: true };
}

export async function editarDivisaAction(
  divisaId: string,
  campos: { nombre?: string; simbolo?: string; decimales?: number; activa?: boolean },
): Promise<EstadoGerencia> {
  try {
    await apiFetch(`/api/v1/divisas/${divisaId}`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: campos,
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo editar la divisa."), ok: false };
  }
  revalidatePath("/gerencia/divisas");
  return { error: "", ok: true };
}

/** Versión de formulario de lo mismo: el toggle de la tabla cambia un campo
 * de un clic, este corrige nombre, símbolo y decimales de una vez. */
export async function guardarDivisaAction(
  _previo: EstadoGerencia,
  formData: FormData,
): Promise<EstadoGerencia> {
  const id = String(formData.get("id") ?? "");
  const nombre = String(formData.get("nombre") ?? "").trim();
  const simbolo = String(formData.get("simbolo") ?? "").trim();
  if (!id) return { error: "Falta la divisa a editar.", ok: false };
  if (!nombre || !simbolo) return { error: "Nombre y símbolo son obligatorios.", ok: false };

  return editarDivisaAction(id, {
    nombre,
    simbolo,
    decimales: Number(formData.get("decimales") ?? 2),
  });
}
