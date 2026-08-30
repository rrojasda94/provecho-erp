"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { estadoDeError } from "@/lib/errores";

const RUTA = "/inventario/devoluciones";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function texto(formData: FormData, campo: string): string {
  return String(formData.get(campo) ?? "").trim();
}

/** Qué falta antes de mandar. El servidor valida igual; acá se evita el
 * viaje y un 409 que el usuario lee como "algo salió mal" en vez de "te
 * falta elegir". */
function faltante(formData: FormData): string {
  const cantidad = texto(formData, "cantidad");
  if (!texto(formData, "almacen_id")) return "Elige el almacén.";
  if (!texto(formData, "sku_id")) return "Elige qué se devuelve.";
  if (!cantidad || Number(cantidad) <= 0) {
    return "La cantidad debe ser mayor que cero.";
  }
  if (texto(formData, "origen") === "cliente" && !texto(formData, "destino")) {
    return "Una devolución de cliente necesita destino: qué se hace con lo que volvió.";
  }
  return "";
}

/**
 * Registra una devolución (RN-INV-019/020).
 *
 * Una sola línea por ahora: es el caso real —vuelve un producto, se decide
 * qué hacer con él— y un formulario multilínea sin necesidad probada sería
 * complejidad por adelantado. La API acepta varias desde el primer día, así
 * que ampliarlo es solo pantalla.
 */
export async function registrarDevolucionAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const problema = faltante(formData);
  if (problema) return { error: problema, ok: false };

  const origen = texto(formData, "origen");
  try {
    await apiFetch("/api/v1/inventory/devoluciones", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        almacen_id: texto(formData, "almacen_id"),
        origen,
        motivo: texto(formData, "motivo"),
        // Una devolución a proveedor NO lleva destino: la mercadería se va.
        destino: origen === "cliente" ? texto(formData, "destino") : null,
        observacion: texto(formData, "observacion") || null,
        items: [
          {
            sku_id: texto(formData, "sku_id"),
            cantidad: texto(formData, "cantidad"),
            lote_id: texto(formData, "lote_id") || null,
          },
        ],
      },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo registrar la devolución.");
  }
  revalidatePath(RUTA);
  return { error: "", ok: true };
}

/** Anular repone lo que la devolución movió, con movimientos contrarios: no
 * borra la fila, porque que alguien se equivocó también es parte del rastro. */
export async function anularDevolucionAction(
  devolucionId: string,
): Promise<EstadoFormulario> {
  try {
    await apiFetch(`/api/v1/inventory/devoluciones/${devolucionId}/anular`, {
      token: await token(),
      metodo: "POST",
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo anular la devolución.");
  }
  revalidatePath(RUTA);
  return { error: "", ok: true };
}
