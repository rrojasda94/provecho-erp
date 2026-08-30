"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { estadoDeError } from "@/lib/errores";

export type EstadoCaja = { error: string; ok: boolean };

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

/**
 * Cambia el PIN de alguien por una elevación acotada a un permiso.
 *
 * Corre en el servidor, no en el navegador: el PIN llega por el `FormData`
 * de la Server Action y muere acá — nunca queda en el JavaScript de la
 * página ni en el historial de red del cliente.
 */
async function elevar(
  formData: FormData,
  permiso: string,
): Promise<{ autorizacion: string } | { error: string }> {
  const username = String(formData.get("username") ?? "").trim();
  const pin = String(formData.get("pin") ?? "");
  if (!username || !pin) {
    return { error: "Hace falta el usuario y el PIN de quien autoriza." };
  }
  try {
    return await apiFetch<{ autorizacion: string }>("/api/v1/auth/autorizar", {
      token: await token(),
      metodo: "POST",
      cuerpo: { username, pin, permiso },
    });
  } catch (e) {
    return { error: estadoDeError(e, "PIN incorrecto o sin permiso para autorizar.").error };
  }
}

/** Avanza la cadena de custodia; quien **recibe** firma con su PIN
 * (RN-MDP-002). El estado siguiente lo elige la pantalla, pero el servidor
 * es el que decide si esa transición existe. */
export async function entregarCustodiaAction(
  _previo: EstadoCaja,
  formData: FormData,
): Promise<EstadoCaja> {
  const custodiaId = String(formData.get("custodia_id") ?? "");
  const estadoSiguiente = String(formData.get("estado_siguiente") ?? "");
  if (!custodiaId || !estadoSiguiente) {
    return { error: "Falta indicar la custodia y a dónde pasa.", ok: false };
  }

  const elevacion = await elevar(formData, "accounting.caja_relevar");
  if ("error" in elevacion) return { error: elevacion.error, ok: false };

  try {
    await apiFetch(`/api/v1/accounting/cajas/custodias/${custodiaId}/entregar`, {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        estado_siguiente: estadoSiguiente,
        autorizacion: elevacion.autorizacion,
      },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo registrar la entrega.");
  }
  revalidatePath("/contabilidad/caja");
  return { error: "", ok: true };
}

/** Reabre un cierre para recontar (RN-MDP-005). El motivo es obligatorio
 * porque es lo único que queda como explicación del faltante. */
export async function reabrirCierreAction(
  _previo: EstadoCaja,
  formData: FormData,
): Promise<EstadoCaja> {
  const cierreId = String(formData.get("cierre_id") ?? "");
  const motivo = String(formData.get("motivo") ?? "").trim();
  if (!cierreId) return { error: "Falta el cierre.", ok: false };
  if (motivo.length < 5) {
    return { error: "El motivo de la reapertura tiene que explicar algo.", ok: false };
  }

  const elevacion = await elevar(formData, "accounting.caja_reabrir");
  if ("error" in elevacion) return { error: elevacion.error, ok: false };

  try {
    await apiFetch(`/api/v1/accounting/cajas/cierres/${cierreId}/reabrir`, {
      token: await token(),
      metodo: "POST",
      cuerpo: { motivo, autorizacion: elevacion.autorizacion },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo reabrir el cierre.");
  }
  revalidatePath("/contabilidad/caja");
  return { error: "", ok: true };
}

/** Alta de un terminal de tarjeta. Sin sucursal es el de emergencia del
 * pool de contabilidad (RN-POS-009). */
export async function registrarPosAction(
  _previo: EstadoCaja,
  formData: FormData,
): Promise<EstadoCaja> {
  const serie = String(formData.get("serie") ?? "").trim();
  const codigoComercio = String(formData.get("codigo_comercio") ?? "").trim();
  const operador = String(formData.get("operador") ?? "").trim();
  const sucursalId = String(formData.get("sucursal_id") ?? "");
  if (!serie || !codigoComercio) {
    return { error: "La serie y el código de comercio son obligatorios.", ok: false };
  }

  try {
    await apiFetch("/api/v1/accounting/pos-tarjeta", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        serie,
        codigo_comercio: codigoComercio,
        operador: operador || undefined,
        sucursal_id: sucursalId || null,
        es_emergencia: !sucursalId,
      },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo registrar el terminal.");
  }
  revalidatePath("/contabilidad/caja");
  return { error: "", ok: true };
}

export async function cambiarEstadoPosAction(
  posId: string,
  estado: string,
): Promise<EstadoCaja> {
  try {
    await apiFetch(`/api/v1/accounting/pos-tarjeta/${posId}`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: { estado },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo cambiar el estado del terminal.");
  }
  revalidatePath("/contabilidad/caja");
  return { error: "", ok: true };
}
