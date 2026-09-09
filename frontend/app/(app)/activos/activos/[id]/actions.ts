"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function texto(formData: FormData, campo: string): string {
  return String(formData.get(campo) ?? "").trim();
}

async function ejecutar(
  activoId: string,
  fn: () => Promise<unknown>,
  mensajeError: string,
): Promise<EstadoFormulario> {
  try {
    await fn();
  } catch (e) {
    return { error: e instanceof ApiError ? e.message : mensajeError, ok: false };
  }
  revalidatePath(`/activos/activos/${activoId}`);
  return { error: "", ok: true };
}

export async function darBajaActivoAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const activoId = texto(formData, "activo_id");
  const motivo = texto(formData, "motivo");
  if (!motivo) return { error: "El motivo es obligatorio.", ok: false };
  return ejecutar(
    activoId,
    async () =>
      apiFetch(`/api/v1/assets/activos/${activoId}/baja`, {
        token: await token(),
        metodo: "POST",
        cuerpo: { motivo },
      }),
    "No se pudo dar de baja el activo.",
  );
}

export async function registrarLecturaAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const activoId = texto(formData, "activo_id");
  const km = texto(formData, "km");
  const fecha = texto(formData, "fecha");
  if (!km || !fecha) return { error: "Kilometraje y fecha son obligatorios.", ok: false };
  return ejecutar(
    activoId,
    async () =>
      apiFetch(`/api/v1/assets/activos/${activoId}/lecturas-odometro`, {
        token: await token(),
        metodo: "POST",
        cuerpo: { km: Number(km), fecha, nota: texto(formData, "nota") || undefined },
      }),
    "No se pudo registrar el kilometraje.",
  );
}

export async function registrarCargaAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const activoId = texto(formData, "activo_id");
  const comprobanteId = texto(formData, "comprobante_id");
  const fecha = texto(formData, "fecha");
  const galones = texto(formData, "galones");
  const monto = texto(formData, "monto");
  const km = texto(formData, "km_odometro");
  if (!comprobanteId || !fecha || !galones || !monto || !km) {
    return { error: "Todos los campos son obligatorios.", ok: false };
  }
  return ejecutar(
    activoId,
    async () =>
      apiFetch(`/api/v1/assets/activos/${activoId}/cargas-combustible`, {
        token: await token(),
        metodo: "POST",
        cuerpo: {
          comprobante_id: comprobanteId,
          fecha,
          galones,
          monto,
          km_odometro: Number(km),
          tipo_combustible: texto(formData, "tipo_combustible") || undefined,
        },
      }),
    "No se pudo registrar la carga de combustible.",
  );
}

export async function crearPlanAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const activoId = texto(formData, "activo_id");
  const nombre = texto(formData, "nombre");
  const cadaDias = texto(formData, "cada_dias");
  const cadaKm = texto(formData, "cada_km");
  const diasAviso = texto(formData, "dias_aviso");
  const kmAviso = texto(formData, "km_aviso");
  if (!nombre) return { error: "El nombre es obligatorio.", ok: false };
  if (!cadaDias && !cadaKm) {
    return { error: "Indica una frecuencia: por días y/o por kilometraje.", ok: false };
  }
  return ejecutar(
    activoId,
    async () =>
      apiFetch("/api/v1/assets/planes", {
        token: await token(),
        metodo: "POST",
        cuerpo: {
          activo_id: activoId,
          nombre,
          descripcion: texto(formData, "descripcion") || undefined,
          cada_dias: cadaDias ? Number(cadaDias) : undefined,
          cada_km: cadaKm ? Number(cadaKm) : undefined,
          dias_aviso: diasAviso ? Number(diasAviso) : undefined,
          km_aviso: kmAviso ? Number(kmAviso) : undefined,
        },
      }),
    "No se pudo crear el plan de mantenimiento.",
  );
}

export async function crearOrdenAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const activoId = texto(formData, "activo_id");
  const tipo = String(formData.get("tipo") ?? "programado");
  const motivoAdelanto = texto(formData, "motivo_adelanto");
  if (tipo === "adelantado" && !motivoAdelanto) {
    return { error: "Un adelanto requiere el motivo.", ok: false };
  }
  return ejecutar(
    activoId,
    async () =>
      apiFetch("/api/v1/assets/ordenes-mantenimiento", {
        token: await token(),
        metodo: "POST",
        cuerpo: {
          activo_id: activoId,
          tipo,
          plan_id: texto(formData, "plan_id") || undefined,
          motivo_adelanto: tipo === "adelantado" ? motivoAdelanto : undefined,
          descripcion: texto(formData, "descripcion") || undefined,
        },
      }),
    "No se pudo crear la orden de mantenimiento.",
  );
}

export async function iniciarOrdenAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const ordenId = texto(formData, "orden_id");
  return ejecutar(
    texto(formData, "activo_id"),
    async () =>
      apiFetch(`/api/v1/assets/ordenes-mantenimiento/${ordenId}/iniciar`, {
        token: await token(),
        metodo: "POST",
      }),
    "No se pudo iniciar la orden.",
  );
}

export async function realizarOrdenAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const ordenId = texto(formData, "orden_id");
  const fecha = texto(formData, "fecha_realizada");
  const kmAlRealizar = texto(formData, "km_al_realizar");
  const almacenId = texto(formData, "almacen_id");
  const repuestoArticuloId = texto(formData, "repuesto_articulo_id");
  const repuestoCantidad = texto(formData, "repuesto_cantidad");
  if (!fecha) return { error: "La fecha de realización es obligatoria.", ok: false };
  if (repuestoArticuloId && !almacenId) {
    return { error: "Registrar un repuesto requiere el almacén de salida.", ok: false };
  }
  return ejecutar(
    texto(formData, "activo_id"),
    async () =>
      apiFetch(`/api/v1/assets/ordenes-mantenimiento/${ordenId}/realizar`, {
        token: await token(),
        metodo: "POST",
        cuerpo: {
          fecha_realizada: fecha,
          km_al_realizar: kmAlRealizar ? Number(kmAlRealizar) : undefined,
          resultado: texto(formData, "resultado") || undefined,
          costo: texto(formData, "costo") || undefined,
          almacen_id: almacenId || undefined,
          repuestos: repuestoArticuloId
            ? [{ articulo_id: repuestoArticuloId, cantidad: repuestoCantidad || "1" }]
            : undefined,
        },
      }),
    "No se pudo registrar el mantenimiento realizado.",
  );
}

export async function agregarRepuestoCompatibleAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const activoId = texto(formData, "activo_id");
  const articuloId = texto(formData, "articulo_id");
  if (!articuloId) return { error: "El artículo es obligatorio.", ok: false };
  return ejecutar(
    activoId,
    async () =>
      apiFetch(`/api/v1/assets/activos/${activoId}/repuestos-compatibles`, {
        token: await token(),
        metodo: "POST",
        cuerpo: { articulo_id: articuloId, notas: texto(formData, "notas") || undefined },
      }),
    "No se pudo agregar el repuesto compatible.",
  );
}

export async function quitarRepuestoCompatibleAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const activoId = texto(formData, "activo_id");
  const repuestoId = texto(formData, "repuesto_id");
  return ejecutar(
    activoId,
    async () =>
      apiFetch(`/api/v1/assets/activos/${activoId}/repuestos-compatibles/${repuestoId}`, {
        token: await token(),
        metodo: "DELETE",
      }),
    "No se pudo quitar el repuesto compatible.",
  );
}

export async function cancelarOrdenAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const ordenId = texto(formData, "orden_id");
  const motivo = texto(formData, "motivo");
  if (!motivo) return { error: "El motivo es obligatorio.", ok: false };
  return ejecutar(
    texto(formData, "activo_id"),
    async () =>
      apiFetch(`/api/v1/assets/ordenes-mantenimiento/${ordenId}/cancelar`, {
        token: await token(),
        metodo: "POST",
        cuerpo: { motivo },
      }),
    "No se pudo cancelar la orden.",
  );
}

export async function crearDocumentoAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const activoId = texto(formData, "activo_id");
  const tipoDocumento = texto(formData, "tipo_documento");
  const fechaVencimiento = texto(formData, "fecha_vencimiento");
  if (!tipoDocumento || !fechaVencimiento) {
    return { error: "Tipo de documento y fecha de vencimiento son obligatorios.", ok: false };
  }
  return ejecutar(
    activoId,
    async () =>
      apiFetch("/api/v1/assets/documentos", {
        token: await token(),
        metodo: "POST",
        cuerpo: {
          sujeto_tipo: "activo",
          sujeto_id: activoId,
          tipo_documento: tipoDocumento,
          fecha_vencimiento: fechaVencimiento,
          numero: texto(formData, "numero") || undefined,
          emisor: texto(formData, "emisor") || undefined,
        },
      }),
    "No se pudo crear el documento.",
  );
}

export async function renovarDocumentoAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const documentoId = texto(formData, "documento_id");
  const fechaVencimiento = texto(formData, "fecha_vencimiento");
  if (!fechaVencimiento) return { error: "La nueva fecha de vencimiento es obligatoria.", ok: false };
  return ejecutar(
    texto(formData, "activo_id"),
    async () =>
      apiFetch(`/api/v1/assets/documentos/${documentoId}/renovar`, {
        token: await token(),
        metodo: "POST",
        cuerpo: {
          fecha_vencimiento: fechaVencimiento,
          numero: texto(formData, "numero") || undefined,
        },
      }),
    "No se pudo renovar el documento.",
  );
}
