"use server";

import { cookies } from "next/headers";

import { ApiError, apiAuth } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type ItemCheckout = { producto_comercial_id: string; cantidad: number };

export type DatosCheckout = {
  modalidad: "delivery" | "takeout";
  sucursal_id?: string;
  items: ItemCheckout[];
  nombre_contacto: string;
  telefono_contacto: string;
  email_contacto?: string;
  direccion_entrega?: string;
  ubicacion_lat?: string;
  ubicacion_lng?: string;
  medio_pago: "efectivo" | "izipay";
  numero_documento?: string;
  nombre_o_razon_social?: string;
};

export type PedidoResultado = {
  id: string;
  estado: "pendiente" | "confirmado" | "fallido";
  numero_orden: number | null;
  fallo_motivo: string | null;
  modalidad: string;
  sucursal_id: string | null;
  medio_pago: string;
  total_estimado: string;
  costo_delivery_estimado: string | null;
  eta_min: number | null;
  eta_max: number | null;
  token_acceso: string | null;
};

export type ResultadoCheckout = { ok: true; pedido: PedidoResultado } | { ok: false; error: string };

async function token(): Promise<string | undefined> {
  const store = await cookies();
  return store.get(COOKIE_TOKEN)?.value;
}

/** Invitado o logueado: sin token el checkout igual funciona (RN-WEB-012),
 * con token la API vincula el pedido a la cuenta. */
export async function confirmarPedido(datos: DatosCheckout): Promise<ResultadoCheckout> {
  try {
    const pedido = await apiAuth<PedidoResultado>("/api/v1/storefront/publico/pedidos", {
      token: await token(),
      metodo: "POST",
      cuerpo: { ...datos, idempotency_key: crypto.randomUUID() },
    });
    return { ok: true, pedido };
  } catch (e) {
    return {
      ok: false,
      error: e instanceof ApiError ? e.message : "No se pudo confirmar el pedido.",
    };
  }
}

export type Cotizacion = {
  sucursal_id: string;
  eta_min: number;
  eta_max: number;
  costo_delivery: string | null;
  distancia_km: string | null;
};

export async function cotizarPedido(datos: {
  modalidad: string;
  sucursal_id?: string;
  ubicacion_lat?: string;
  ubicacion_lng?: string;
  // Lo que hay en el carrito: el estimado depende de qué se pide.
  items?: { producto_comercial_id: string; cantidad: number }[];
}): Promise<Cotizacion | null> {
  try {
    return await apiAuth<Cotizacion>("/api/v1/storefront/publico/pedidos/cotizar", {
      metodo: "POST",
      cuerpo: datos,
    });
  } catch {
    return null;
  }
}
