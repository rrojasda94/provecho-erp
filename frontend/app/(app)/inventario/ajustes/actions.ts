"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

const RUTA = "/inventario/ajustes";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function texto(formData: FormData, campo: string): string {
  return String(formData.get(campo) ?? "").trim();
}

function mensajeDe(e: unknown, porDefecto: string): string {
  return e instanceof ApiError ? e.message : porDefecto;
}

/** Los únicos dos motivos con signo positivo (`rules.signo_ajuste_valido`):
 * `faltante`/`merma` son siempre una salida, así que no tienen lugar en una
 * entrada de stock. */
const MOTIVOS_ENTRADA = new Set(["sobrante", "error_registro"]);

function faltante(formData: FormData): string {
  const cantidad = texto(formData, "cantidad");
  if (!texto(formData, "almacen_id")) return "Elige el almacén.";
  if (!texto(formData, "sku_id")) return "Elige qué artículo entra.";
  if (!cantidad || Number(cantidad) <= 0) {
    return "La cantidad debe ser mayor que cero.";
  }
  if (!MOTIVOS_ENTRADA.has(texto(formData, "motivo"))) {
    return "Motivo inválido para una entrada.";
  }
  return "";
}

/**
 * Registra una entrada de stock manual como ajuste `pendiente`
 * (RN-INV-004/006/016): la aprueba otro usuario, nunca quien la solicita.
 *
 * No es un tipo de movimiento aparte — es el mismo `POST /ajustes` que ya
 * existía, con formulario. Un endpoint de escritura directa hubiera evitado
 * la segregación de funciones que ese ajuste exige.
 */
export async function registrarEntradaStockAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const problema = faltante(formData);
  if (problema) return { error: problema, ok: false };

  try {
    await apiFetch("/api/v1/inventory/ajustes", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        almacen_id: texto(formData, "almacen_id"),
        sku_id: texto(formData, "sku_id"),
        cantidad: texto(formData, "cantidad"),
        motivo: texto(formData, "motivo"),
        lote_codigo: texto(formData, "lote_codigo") || null,
        fecha_vencimiento: texto(formData, "fecha_vencimiento") || null,
        fecha_elaboracion: texto(formData, "fecha_elaboracion") || null,
        condicion_almacenamiento: texto(formData, "condicion_almacenamiento") || null,
      },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo registrar la entrada."), ok: false };
  }
  revalidatePath(RUTA);
  return { error: "", ok: true };
}
