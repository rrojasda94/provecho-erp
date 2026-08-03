"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type EstadoProveedor = { error: string; ok: boolean };

type DatosProveedor = {
  tipo: string;
  personaId: string;
  razonSocial: string;
  ruc: string;
  condicionPago: string;
  plazoDias: string;
};

function leerFormulario(formData: FormData): DatosProveedor {
  return {
    tipo: String(formData.get("tipo") ?? "juridico"),
    personaId: String(formData.get("persona_id") ?? ""),
    razonSocial: String(formData.get("razon_social") ?? "").trim(),
    ruc: String(formData.get("ruc") ?? "").trim(),
    condicionPago: String(formData.get("condicion_pago") ?? "contado"),
    plazoDias: String(formData.get("plazo_dias_credito") ?? "").trim(),
  };
}

function validar(datos: DatosProveedor): string | null {
  if (datos.tipo === "natural") {
    if (!datos.personaId) return "Elegir la persona.";
  } else {
    if (!datos.razonSocial || !datos.ruc) return "Razón social y RUC son obligatorios.";
    if (datos.ruc.length !== 11) return "El RUC debe tener 11 dígitos.";
  }
  if (datos.condicionPago === "credito" && !datos.plazoDias) {
    return "Crédito exige un plazo de días.";
  }
  return null;
}

export async function crearProveedorAction(
  _previo: EstadoProveedor,
  formData: FormData,
): Promise<EstadoProveedor> {
  const store = await cookies();
  const token = store.get(COOKIE_TOKEN)?.value;
  if (!token) redirect("/login");

  const datos = leerFormulario(formData);
  const errorValidacion = validar(datos);
  if (errorValidacion) return { error: errorValidacion, ok: false };

  try {
    await apiFetch("/api/v1/purchases/proveedores", {
      token,
      metodo: "POST",
      cuerpo: {
        tipo: datos.tipo,
        persona_id: datos.tipo === "natural" ? datos.personaId : undefined,
        razon_social: datos.tipo === "juridico" ? datos.razonSocial : undefined,
        ruc: datos.tipo === "juridico" ? datos.ruc : undefined,
        condicion_pago: datos.condicionPago,
        plazo_dias_credito:
          datos.condicionPago === "credito" ? Number(datos.plazoDias) : undefined,
      },
    });
  } catch (e) {
    const mensaje = e instanceof ApiError ? e.message : "No se pudo crear el proveedor.";
    return { error: mensaje, ok: false };
  }

  revalidatePath("/compras/proveedores");
  return { error: "", ok: true };
}
