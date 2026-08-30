"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { estadoDeError } from "@/lib/errores";

const RUTA = "/inventario/solicitudes";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function texto(formData: FormData, campo: string): string {
  return String(formData.get(campo) ?? "").trim();
}

/**
 * Lo que las siete acciones tienen igual: traducir el fallo a algo legible y
 * revalidar si salió.
 *
 * Recibe la llamada como función y no la ruta como texto a propósito: cada
 * acción escribe su `apiFetch` con la ruta **literal**, que es lo que lee el
 * escaneo de `lib/contrato.test.ts`. Con la ruta armada acá, estas siete
 * llamadas quedaban invisibles para el chequeo que existe justamente para
 * avisar cuando el backend renombra un endpoint.
 */
async function ejecutar(
  llamar: () => Promise<unknown>,
  siFalla: string,
  rutaRevalidada = RUTA,
): Promise<EstadoFormulario> {
  try {
    await llamar();
  } catch (e) {
    return estadoDeError(e, siFalla);
  }
  revalidatePath(rutaRevalidada);
  return { error: "", ok: true };
}

/**
 * Abre el requerimiento de la jornada del almacén y lleva a él.
 *
 * Es lo que hay detrás del botón. El endpoint crea la lista si no existe —ya
 * cargada con lo que está bajo mínimo— y si existía le suma lo que cayó desde
 * la última vez (RN-INV-023), así que apretarlo dos veces no abre dos listas:
 * abre la misma, más al día.
 *
 * Con éxito redirige, y `redirect()` corta la ejecución: el `EstadoFormulario`
 * que se devuelve es solo para el camino de error.
 */
export async function abrirBorradorAction(
  almacenId: string,
): Promise<EstadoFormulario> {
  if (!almacenId) return { error: "Elige el almacén.", ok: false };
  let id: string;
  try {
    const borrador = await apiFetch<{ id: string }>(
      `/api/v1/inventory/solicitudes/borrador?almacen_id=${almacenId}`,
      { token: await token() },
    );
    id = borrador.id;
  } catch (e) {
    return estadoDeError(e, "No se pudo abrir el requerimiento de la jornada.");
  }
  revalidatePath(RUTA);
  redirect(`${RUTA}/${id}`);
}

/**
 * Suma a la lista de la jornada algo que el stock no pidió (RN-INV-024).
 *
 * El servidor decide si es urgencia mirando el stock del almacén; acá no se
 * manda ninguna marca a propósito, porque un cliente que pudiera declararse
 * urgente vaciaría de sentido la columna que el almacenero mira.
 */
export async function agregarItemAction(
  solicitudId: string,
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const cantidad = texto(formData, "cantidad");
  if (!texto(formData, "sku_id")) return { error: "Elige qué pedir.", ok: false };
  if (!cantidad || Number(cantidad) <= 0) {
    return { error: "La cantidad debe ser mayor que cero.", ok: false };
  }
  return ejecutar(
    async () =>
      apiFetch(`/api/v1/inventory/solicitudes/${solicitudId}/items`, {
        token: await token(),
        metodo: "POST",
        cuerpo: { sku_id: texto(formData, "sku_id"), cantidad },
      }),
    "No se pudo agregar el producto.",
  );
}

export async function cambiarCantidadAction(
  solicitudId: string,
  skuId: string,
  cantidad: string,
): Promise<EstadoFormulario> {
  if (!cantidad || Number(cantidad) <= 0) {
    return { error: "La cantidad debe ser mayor que cero.", ok: false };
  }
  return ejecutar(
    async () =>
      apiFetch(`/api/v1/inventory/solicitudes/${solicitudId}/items/${skuId}`, {
        token: await token(),
        metodo: "PATCH",
        cuerpo: { cantidad },
      }),
    "No se pudo cambiar la cantidad.",
  );
}

export async function quitarItemAction(
  solicitudId: string,
  skuId: string,
): Promise<EstadoFormulario> {
  return ejecutar(
    async () =>
      apiFetch(`/api/v1/inventory/solicitudes/${solicitudId}/items/${skuId}`, {
        token: await token(),
        metodo: "DELETE",
      }),
    "No se pudo quitar el producto.",
  );
}

/** Envía la lista: recién acá deja de ser borrador y espera aprobación. */
export async function enviarSolicitudAction(
  solicitudId: string,
): Promise<EstadoFormulario> {
  return ejecutar(
    async () =>
      apiFetch(`/api/v1/inventory/solicitudes/${solicitudId}/enviar`, {
        token: await token(),
        metodo: "POST",
      }),
    "No se pudo enviar el requerimiento.",
  );
}

/** Descartar el borrador o cancelar un pedido ya enviado: el mismo endpoint,
 * porque cancelar es cancelar (y un borrador no tiene reservas que soltar). */
export async function cancelarSolicitudAction(
  solicitudId: string,
): Promise<EstadoFormulario> {
  return ejecutar(
    async () =>
      apiFetch(`/api/v1/inventory/solicitudes/${solicitudId}/cancelar`, {
        token: await token(),
        metodo: "POST",
      }),
    "No se pudo cancelar.",
  );
}

export async function aprobarSolicitudAction(
  solicitudId: string,
): Promise<EstadoFormulario> {
  return ejecutar(
    async () =>
      apiFetch(`/api/v1/inventory/solicitudes/${solicitudId}/aprobar`, {
        token: await token(),
        metodo: "POST",
        // Sin recortes: se aprueba lo pedido tal cual. Recortar por SKU lo
        // soporta la API desde el slice 4 y todavía no tiene pantalla.
        cuerpo: { aprobadas: [] },
      }),
    "No se pudo aprobar.",
    `${RUTA}/${solicitudId}`,
  );
}

export async function rechazarSolicitudAction(
  solicitudId: string,
): Promise<EstadoFormulario> {
  return ejecutar(
    async () =>
      apiFetch(`/api/v1/inventory/solicitudes/${solicitudId}/rechazar`, {
        token: await token(),
        metodo: "POST",
      }),
    "No se pudo rechazar.",
    `${RUTA}/${solicitudId}`,
  );
}
