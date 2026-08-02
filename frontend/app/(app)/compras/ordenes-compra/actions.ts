"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type EstadoOrdenCompra = { error: string; ok: boolean };

type ItemForm = { articuloId: string; cantidad: string; costoUnitario: string };

function leerItems(formData: FormData): ItemForm[] {
  const articulos = formData.getAll("articulo_id[]").map(String);
  const cantidades = formData.getAll("cantidad[]").map(String);
  const costos = formData.getAll("costo_unitario[]").map(String);
  return articulos.map((articuloId, i) => ({
    articuloId,
    cantidad: cantidades[i] ?? "",
    costoUnitario: costos[i] ?? "",
  }));
}

function validar(
  proveedorId: string,
  almacenId: string,
  items: ItemForm[],
): string | null {
  if (!proveedorId) return "Elegir un proveedor.";
  if (!almacenId) return "Elegir el almacén de destino.";
  const validos = items.filter((it) => it.articuloId && it.cantidad && it.costoUnitario);
  if (validos.length === 0) return "Agregar al menos un ítem con artículo, cantidad y costo.";
  if (validos.some((it) => Number(it.cantidad) <= 0)) return "La cantidad debe ser mayor a 0.";
  return null;
}

export async function crearOrdenCompraAction(
  _previo: EstadoOrdenCompra,
  formData: FormData,
): Promise<EstadoOrdenCompra> {
  const store = await cookies();
  const token = store.get(COOKIE_TOKEN)?.value;
  if (!token) redirect("/login");

  const proveedorId = String(formData.get("proveedor_id") ?? "");
  const almacenId = String(formData.get("almacen_destino_id") ?? "");
  const items = leerItems(formData).filter(
    (it) => it.articuloId && it.cantidad && it.costoUnitario,
  );

  const errorValidacion = validar(proveedorId, almacenId, items);
  if (errorValidacion) return { error: errorValidacion, ok: false };

  try {
    await apiFetch("/api/v1/purchases/ordenes-compra", {
      token,
      metodo: "POST",
      cuerpo: {
        proveedor_id: proveedorId,
        almacen_destino_id: almacenId,
        // Client-generada: el backend la usa para no duplicar la OC si el
        // POST se reintenta (doble clic, red inestable).
        idempotency_key: crypto.randomUUID(),
        items: items.map((it) => ({
          articulo_id: it.articuloId,
          cantidad: it.cantidad,
          costo_unitario: it.costoUnitario,
        })),
      },
    });
  } catch (e) {
    const mensaje = e instanceof ApiError ? e.message : "No se pudo crear la orden de compra.";
    return { error: mensaje, ok: false };
  }

  revalidatePath("/compras/ordenes-compra");
  return { error: "", ok: true };
}
