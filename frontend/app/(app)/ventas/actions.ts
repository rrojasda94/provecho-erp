"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type EstadoVenta = { error: string; ok: boolean };

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function mensajeDe(e: unknown, porDefecto: string): string {
  return e instanceof ApiError ? e.message : porDefecto;
}

export async function anularVentaAction(ventaId: string): Promise<EstadoVenta> {
  try {
    await apiFetch(`/api/v1/sales/ventas/${ventaId}/anular`, {
      token: await token(),
      metodo: "POST",
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo anular la venta."), ok: false };
  }
  revalidatePath("/ventas");
  return { error: "", ok: true };
}

export type LineaVenta = {
  id: string;
  nombre: string;
  cantidad: string;
  precio_unitario: string;
  grupo_cobro: number;
};

/** Las líneas se piden al abrir el diálogo, no al pintar la jornada: solo
 * hacen falta para acreditar y traerlas por cada venta del día sería un
 * viaje por fila para algo que casi nunca se usa. */
export async function lineasDeVentaAction(ventaId: string): Promise<LineaVenta[]> {
  try {
    return await apiFetch<LineaVenta[]>(`/api/v1/sales/ventas/${ventaId}/items`, {
      token: await token(),
    });
  } catch {
    return [];
  }
}

export async function emitirNotaCreditoAction(
  _previo: EstadoVenta,
  formData: FormData,
): Promise<EstadoVenta> {
  const comprobanteId = String(formData.get("comprobante_id") ?? "");
  const motivo = String(formData.get("motivo") ?? "");
  const parcial = formData.get("alcance") === "parcial";
  if (!comprobanteId || !motivo) return { error: "Falta el motivo.", ok: false };

  // Las cantidades viajan como filas paralelas; solo entran las > 0, así
  // que dejar una línea en cero equivale a no devolverla.
  const ids = formData.getAll("linea_id").map(String);
  const cantidades = formData.getAll("linea_cantidad").map(String);
  const detalle = ids
    .map((id, i) => ({ venta_item_id: id, cantidad: cantidades[i] ?? "0" }))
    .filter((d) => Number(d.cantidad) > 0);
  if (parcial && detalle.length === 0) {
    return { error: "Una nota parcial necesita al menos una línea.", ok: false };
  }

  try {
    await apiFetch(`/api/v1/sales/comprobantes/${comprobanteId}/nota-credito`, {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        motivo,
        detalle: parcial ? detalle : undefined,
        repone_stock: formData.get("repone_stock") === "on",
      },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo emitir la nota de crédito."), ok: false };
  }
  revalidatePath("/ventas");
  return { error: "", ok: true };
}

export async function reintentarComprobanteAction(
  comprobanteId: string,
): Promise<EstadoVenta> {
  try {
    await apiFetch(`/api/v1/sales/comprobantes/${comprobanteId}/reintentar`, {
      token: await token(),
      metodo: "POST",
    });
  } catch (e) {
    // 502 = SUNAT/Factiliza rechazó de nuevo. El intento ya quedó contado en
    // el comprobante, así que la pantalla se recarga igual para mostrarlo.
    revalidatePath("/ventas");
    return { error: mensajeDe(e, "El comprobante volvió a fallar."), ok: false };
  }
  revalidatePath("/ventas");
  return { error: "", ok: true };
}

// --- Mesas del salón (RN-MDC-004/005/006) ------------------------------------
/** El número no se manda nunca: lo asigna el backend (siguiente disponible).
 * `pos_x`/`pos_y` sí, cuando la mesa nace desde una celda elegida en el
 * plano — si no se pasan, el backend elige la primera celda libre. */
export async function crearMesaAction(
  _previo: EstadoVenta,
  formData: FormData,
): Promise<EstadoVenta> {
  const sucursalId = String(formData.get("sucursal_id") ?? "").trim();
  if (!sucursalId) {
    return { error: "Elige la sucursal del salón.", ok: false };
  }
  const zona = String(formData.get("zona") ?? "").trim();
  const capacidad = String(formData.get("capacidad") ?? "").trim();
  try {
    await apiFetch("/api/v1/sales/mesas", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        sucursal_id: sucursalId,
        zona: zona || null,
        capacidad: capacidad ? Number(capacidad) : null,
      },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo crear la mesa."), ok: false };
  }
  revalidatePath("/ventas/mesas");
  return { error: "", ok: true };
}

export async function guardarMesaAction(
  _previo: EstadoVenta,
  formData: FormData,
): Promise<EstadoVenta> {
  const mesaId = String(formData.get("id") ?? "").trim();
  if (!mesaId) {
    return { error: "Falta el identificador de la mesa.", ok: false };
  }
  const zona = String(formData.get("zona") ?? "").trim();
  const capacidad = String(formData.get("capacidad") ?? "").trim();
  try {
    await apiFetch(`/api/v1/sales/mesas/${mesaId}`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: { zona: zona || null, capacidad: capacidad ? Number(capacidad) : null },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo guardar la mesa."), ok: false };
  }
  revalidatePath("/ventas/mesas");
  return { error: "", ok: true };
}

/** Arrastrar una mesa a otra celda del plano — sin pasar por el diálogo de
 * edición, así que va suelta y no como parte de `guardarMesaAction`. */
export async function moverMesaAction(
  mesaId: string,
  posX: number,
  posY: number,
): Promise<EstadoVenta> {
  try {
    await apiFetch(`/api/v1/sales/mesas/${mesaId}`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: { pos_x: posX, pos_y: posY },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo mover la mesa."), ok: false };
  }
  revalidatePath("/ventas/mesas");
  return { error: "", ok: true };
}

/** Solo retira la mesa de número más alto (RN-MDC-006); el backend es quien
 * decide si borra la fila o la desactiva según tenga ventas. */
export async function eliminarMesaAction(mesaId: string): Promise<EstadoVenta> {
  try {
    await apiFetch(`/api/v1/sales/mesas/${mesaId}`, {
      token: await token(),
      metodo: "DELETE",
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo quitar la mesa."), ok: false };
  }
  revalidatePath("/ventas/mesas");
  return { error: "", ok: true };
}

// --- Promociones condicionales (ADR-076) -------------------------------------
/** Lo que el formulario manda para cada tipo, ya en la forma que la API
 * espera. Vive acá y no en el cliente porque es traducción de contrato: el
 * formulario pregunta en el idioma del negocio ("lleva 2, paga 1") y el
 * servidor guarda `condicion`/`beneficio`. */
function armarRegla(formData: FormData): { condicion: object; beneficio: object } {
  const numero = (campo: string) => {
    const crudo = String(formData.get(campo) ?? "").trim();
    return crudo === "" ? null : Number(crudo);
  };
  // Un valor por campo repetido, no una cadena con comas: el desplegable de
  // búsqueda manda un `<input type="hidden">` por cada opción elegida. Es el
  // mismo trato que ya tienen las líneas de una orden de compra.
  const lista = (campo: string) =>
    formData.getAll(campo).map((x) => String(x).trim()).filter(Boolean);

  const productos = lista("producto_ids");
  const categorias = lista("categoria_ids");
  const alcance = { producto_ids: productos, categoria_ids: categorias };

  switch (String(formData.get("tipo"))) {
    case "nxm":
      return {
        condicion: { ...alcance, lleva: numero("lleva") },
        beneficio: { libera: numero("libera"), descuento_pct: numero("descuento_pct") },
      };
    case "cantidad":
      return {
        condicion: { ...alcance, minimo: numero("minimo") },
        beneficio: { descuento_pct: numero("descuento_pct") },
      };
    case "combo":
      return {
        condicion: { producto_ids: productos },
        beneficio: {
          precio_fijo: numero("precio_fijo"),
          gratis_producto_id: String(formData.get("gratis_producto_id") ?? "") || null,
        },
      };
    default:
      return {
        condicion: { ...alcance, minimo: numero("minimo") ?? 0 },
        beneficio: { descuento_pct: numero("descuento_pct") },
      };
  }
}

export async function crearPromocionAction(
  _previo: EstadoVenta,
  formData: FormData,
): Promise<EstadoVenta> {
  const nombre = String(formData.get("nombre") ?? "").trim();
  if (!nombre) return { error: "La promoción necesita un nombre.", ok: false };
  const texto = (campo: string) => String(formData.get(campo) ?? "").trim() || null;
  const dias = formData.getAll("dias_semana").map((d) => Number(d));

  try {
    await apiFetch("/api/v1/sales/promociones", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        nombre,
        tipo: String(formData.get("tipo") ?? "nxm"),
        ...armarRegla(formData),
        desde: texto("desde"),
        hasta: texto("hasta"),
        dias_semana: dias.length ? dias : null,
        hora_desde: texto("hora_desde"),
        hora_hasta: texto("hora_hasta"),
        sucursal_id: texto("sucursal_id"),
        modalidades: formData.getAll("modalidades").map(String),
        prioridad: Number(formData.get("prioridad") ?? 0),
        acumulable: formData.get("acumulable") === "on",
      },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo crear la promoción."), ok: false };
  }
  revalidatePath("/ventas/promociones");
  return { error: "", ok: true };
}

export async function terminarPromocionAction(
  promocionId: string,
): Promise<EstadoVenta> {
  try {
    await apiFetch(`/api/v1/sales/promociones/${promocionId}/terminar`, {
      token: await token(),
      metodo: "POST",
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo terminar la promoción."), ok: false };
  }
  revalidatePath("/ventas/promociones");
  return { error: "", ok: true };
}
