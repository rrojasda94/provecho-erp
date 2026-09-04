"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

const RUTA = "/inventario/stock";

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

/**
 * Declara qué artículos maneja un almacén, con su saldo de partida.
 *
 * Es el arranque que no existía: la fila de `stock` nacía sola con el primer
 * movimiento, así que un almacén nuevo se veía vacío en todas partes —stock,
 * conteo, requerimiento de la jornada— y no había ninguna acción para salir
 * de ese cero.
 *
 * La cantidad es opcional a propósito: declarar el artículo en cero ya sirve
 * para que aparezca y se pueda contar, que es como se carga un inventario de
 * verdad (contando, no tecleando saldos).
 */
export async function declararArticulosAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const almacenId = texto(formData, "almacen_id");
  const skuIds = formData.getAll("sku_ids").map(String).filter(Boolean);
  if (!almacenId) return { error: "Elige el almacén.", ok: false };
  if (skuIds.length === 0) return { error: "Elige al menos un artículo.", ok: false };

  const cantidad = texto(formData, "cantidad_inicial");
  if (cantidad && Number(cantidad) < 0) {
    return { error: "La cantidad inicial no puede ser negativa.", ok: false };
  }
  const minimo = texto(formData, "stock_minimo");

  try {
    await apiFetch(`/api/v1/inventory/almacenes/${almacenId}/articulos`, {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        // La misma cantidad y el mismo mínimo para todo lo elegido: declarar
        // veinte artículos de una es el caso real al abrir un almacén, y
        // pedir un número por fila ahí es una planilla, no un formulario.
        articulos: skuIds.map((sku_id) => ({
          sku_id,
          cantidad_inicial: cantidad || null,
          stock_minimo: minimo || null,
        })),
      },
    });
  } catch (e) {
    return {
      error: mensajeDe(e, "No se pudieron agregar los artículos."),
      ok: false,
    };
  }
  revalidatePath(RUTA);
  return { error: "", ok: true };
}
