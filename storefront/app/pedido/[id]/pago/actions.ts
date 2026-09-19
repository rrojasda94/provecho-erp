"use server";

import { API_INTERNAL_URL, apiFetch } from "@/lib/api";

type PedidoParaPago = { pago_simulado: boolean; pago_id_externo: string | null };

/**
 * Manda a la API el resultado de un pago **de prueba** (sin credenciales
 * reales de Izipay), como lo haría la pasarela por webhook. El id del intento
 * se lee del pedido en el servidor —el navegador no lo elige—, y la API solo
 * acepta este camino fuera de producción.
 */
export async function simularPago(
  pedidoId: string,
  token: string,
  resultado: "aprobado" | "rechazado",
): Promise<{ ok: boolean; error?: string }> {
  const pedido = await apiFetch<PedidoParaPago>(
    `/api/v1/storefront/publico/pedidos/${pedidoId}?token=${encodeURIComponent(token)}`,
    { revalidate: 0 },
  );
  if (!pedido?.pago_simulado || !pedido.pago_id_externo) {
    return { ok: false, error: "Este pedido no admite pago de prueba." };
  }
  try {
    const respuesta = await fetch(`${API_INTERNAL_URL}/api/v1/storefront/webhooks/izipay`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Izipay-Fake": resultado },
      body: JSON.stringify({ id_externo: pedido.pago_id_externo }),
      cache: "no-store",
    });
    return respuesta.ok ? { ok: true } : { ok: false, error: "No se pudo registrar el pago." };
  } catch {
    return { ok: false, error: "No se pudo registrar el pago." };
  }
}
