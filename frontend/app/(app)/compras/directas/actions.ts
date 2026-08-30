"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

import {
  cuerpoDeFactura,
  faltaEnLaFactura,
  type CuerpoFactura,
} from "@/lib/factura-proveedor";

import type { EstadoOrdenCompra } from "../ordenes-compra/actions";

/**
 * Compra directa (ADR-082): el gasto ya incurrido que llega con la factura en
 * la mano, sin OC previa.
 *
 * `POST /purchases/compras-directas` existe y está probado desde 2026-08-29 y
 * ninguna pantalla lo llamaba, así que «crear una compra con una factura»
 * seguía sin poder hacerse aunque el backend ya lo soportara.
 *
 * Termina redirigiendo a la ficha de la OC que crea: el resultado es una
 * `orden_compra` con `origen="directa"` ya recibida y conforme, y esa ficha
 * es el único lugar donde vive el documento. Duplicar su vista acá serían dos
 * pantallas que se desincronizan.
 */
/** Lo comprado, línea por línea. Una fila sin artículo o sin cantidad es una
 * fila que el usuario agregó y no llenó: se descarta. */
function leerCompra(formData: FormData) {
  const articulos = formData.getAll("articulo_id[]").map(String);
  const cantidades = formData.getAll("cantidad[]").map(String);
  const costos = formData.getAll("costo_unitario[]").map(String);
  return articulos
    .map((articulo_id, i) => ({
      articulo_id,
      cantidad: cantidades[i] ?? "",
      costo_unitario: costos[i] ?? "",
    }))
    .filter((it) => it.articulo_id && Number(it.cantidad) > 0 && it.costo_unitario);
}

/** Lo que impide mandar la compra, en el orden en que se llena el
 * formulario. `null` = está completa. */
function queFalta(
  proveedorId: string,
  almacenId: string,
  cuantosItems: number,
  comprobante: CuerpoFactura,
): string | null {
  if (!proveedorId) return "Elegir un proveedor.";
  if (!almacenId) return "Elegir el almacén de destino.";
  if (cuantosItems === 0) {
    return "Agregar al menos un ítem con artículo, cantidad y costo.";
  }
  return faltaEnLaFactura(comprobante);
}

export async function crearCompraDirectaAction(
  _previo: EstadoOrdenCompra,
  formData: FormData,
): Promise<EstadoOrdenCompra> {
  const store = await cookies();
  const token = store.get(COOKIE_TOKEN)?.value;
  if (!token) redirect("/login");

  const proveedorId = String(formData.get("proveedor_id") ?? "");
  const almacenId = String(formData.get("almacen_destino_id") ?? "");
  const items = leerCompra(formData);
  const comprobante = cuerpoDeFactura(formData, crypto.randomUUID());

  const falta = queFalta(proveedorId, almacenId, items.length, comprobante);
  if (falta) return { error: falta, ok: false };

  let ordenId: string;
  try {
    const creado = await apiFetch<{ compra_id: string | null }>(
      "/api/v1/purchases/compras-directas",
      {
        token,
        metodo: "POST",
        cuerpo: {
          proveedor_id: proveedorId,
          almacen_destino_id: almacenId,
          idempotency_key: crypto.randomUUID(),
          items,
          comprobante,
        },
      },
    );
    ordenId = creado.compra_id ?? "";
  } catch (e) {
    const mensaje =
      e instanceof ApiError ? e.message : "No se pudo registrar la compra directa.";
    return { error: mensaje, ok: false };
  }

  revalidatePath("/compras/ordenes-compra");
  revalidatePath("/compras/facturas");
  // `redirect` levanta: lo que sigue no se ejecuta, y por eso va fuera del
  // `try` — dentro, el `catch` lo tomaría como un fallo de la API.
  redirect(ordenId ? `/compras/ordenes-compra/${ordenId}` : "/compras/ordenes-compra");
}
