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

type ItemDevolucionForm = { sku_id: string; cantidad: string };

/** Filas paralelas (`sku_id[]`, `cantidad[]`), mismo patrón que el traslado
 * directo: una línea con SKU vacío o cantidad ≤ 0 se descarta en vez de
 * rechazar el envío entero — es la fila que alguien agregó y no llegó a
 * llenar. */
function items(formData: FormData): ItemDevolucionForm[] {
  const skus = formData.getAll("sku_id").map(String);
  const cantidades = formData.getAll("cantidad").map(String);
  return skus
    .map((sku_id, i) => ({ sku_id, cantidad: cantidades[i] ?? "" }))
    .filter((it) => it.sku_id && Number(it.cantidad) > 0);
}

/** Qué falta antes de mandar. El servidor valida igual; acá se evita el
 * viaje y un 409 que el usuario lee como "algo salió mal" en vez de "te
 * falta elegir". */
function faltante(formData: FormData): string {
  if (!texto(formData, "almacen_id")) return "Elige el almacén.";
  if (items(formData).length === 0) {
    return "Agrega al menos un artículo con cantidad.";
  }
  if (texto(formData, "origen") === "cliente" && !texto(formData, "destino")) {
    return "Una devolución de cliente necesita destino: qué se hace con lo que volvió.";
  }
  return "";
}

/**
 * Registra una devolución (RN-INV-019/020).
 *
 * Vuelven varios artículos juntos —lo típico cuando se rechaza un pedido
 * completo— y la API los acepta desde el primer día; el formulario mandaba
 * uno solo.
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
        items: items(formData),
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

/**
 * Emite la guía de la devolución a proveedor.
 *
 * Solo la devolución `a proveedor` sale del almacén por la vía pública; la
 * de cliente entra y no la necesita. Idempotente por devolución, igual que
 * la del traslado: pedirla dos veces devuelve la misma.
 */
export async function emitirGuiaDevolucionAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const devolucionId = texto(formData, "devolucion_id");
  if (!devolucionId) return { error: "Falta la devolución.", ok: false };

  try {
    await apiFetch(`/api/v1/inventory/devoluciones/${devolucionId}/guia-remision`, {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        lugar_destino: texto(formData, "lugar_destino"),
        chofer_nombres: texto(formData, "chofer_nombres"),
        chofer_apellidos: texto(formData, "chofer_apellidos"),
        chofer_num_doc: texto(formData, "chofer_num_doc"),
        chofer_licencia: texto(formData, "chofer_licencia"),
        vehiculo_placa: texto(formData, "vehiculo_placa"),
        peso_bruto_kg: texto(formData, "peso_bruto_kg"),
        fecha_inicio_traslado: texto(formData, "fecha_inicio_traslado") || null,
        observacion: texto(formData, "observacion") || null,
      },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo emitir la guía.");
  }
  revalidatePath(RUTA);
  return { error: "", ok: true };
}
