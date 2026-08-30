"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { estadoDeError } from "@/lib/errores";

export type EstadoAsiento = { error: string; ok: boolean };

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

type Linea = { cuenta_contable_id: string; tipo: string; monto: number };

/** Las líneas viajan como filas paralelas del formulario (`cuenta[]`,
 * `tipo[]`, `monto[]`) — mismo patrón que los ítems de una orden de compra. */
function leerLineas(formData: FormData): Linea[] {
  const cuentas = formData.getAll("cuenta_contable_id").map(String);
  const tipos = formData.getAll("tipo").map(String);
  const montos = formData.getAll("monto").map(String);
  return cuentas
    .map((cuenta, i) => ({
      cuenta_contable_id: cuenta,
      tipo: tipos[i] ?? "debe",
      monto: Number(montos[i] ?? 0),
    }))
    .filter((l) => l.cuenta_contable_id && l.monto > 0);
}

function suma(lineas: Linea[], tipo: string): number {
  return lineas.filter((l) => l.tipo === tipo).reduce((t, l) => t + l.monto, 0);
}

export async function crearAsientoAction(
  _previo: EstadoAsiento,
  formData: FormData,
): Promise<EstadoAsiento> {
  const fecha = String(formData.get("fecha") ?? "");
  const glosa = String(formData.get("glosa") ?? "").trim();
  const lineas = leerLineas(formData);

  if (!fecha) return { error: "Falta la fecha.", ok: false };
  if (!glosa) return { error: "Falta la glosa: un asiento sin glosa no se audita.", ok: false };
  if (lineas.length < 2) return { error: "Un asiento lleva al menos dos líneas.", ok: false };
  // RN-CTB-001. El backend lo vuelve a validar; acá se evita el viaje y se
  // dice exactamente cuánto falta.
  const debe = suma(lineas, "debe");
  const haber = suma(lineas, "haber");
  if (debe !== haber) {
    return {
      error: `El asiento no cuadra: debe ${debe.toFixed(2)} vs. haber ${haber.toFixed(2)}.`,
      ok: false,
    };
  }

  try {
    await apiFetch("/api/v1/accounting/asientos", {
      token: await token(),
      metodo: "POST",
      cuerpo: { fecha, glosa, lineas },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo registrar el asiento.");
  }

  revalidatePath("/contabilidad");
  return { error: "", ok: true };
}

export async function anularAsientoAction(asientoId: string): Promise<EstadoAsiento> {
  try {
    await apiFetch(`/api/v1/accounting/asientos/${asientoId}/anular`, {
      token: await token(),
      metodo: "POST",
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo anular el asiento.");
  }
  revalidatePath("/contabilidad");
  return { error: "", ok: true };
}

export async function crearCuentaAction(
  _previo: EstadoAsiento,
  formData: FormData,
): Promise<EstadoAsiento> {
  const codigo = String(formData.get("codigo") ?? "").trim();
  const nombre = String(formData.get("nombre") ?? "").trim();
  const tipo = String(formData.get("tipo") ?? "");
  const cuentaPadre = String(formData.get("cuenta_padre_id") ?? "");
  if (!codigo || !nombre) return { error: "Código y nombre son obligatorios.", ok: false };

  try {
    await apiFetch("/api/v1/accounting/cuentas-contables", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        codigo,
        nombre,
        tipo,
        cuenta_padre_id: cuentaPadre || undefined,
      },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo crear la cuenta.");
  }
  revalidatePath("/contabilidad/plan-cuentas");
  return { error: "", ok: true };
}

/** Corrección de una cuenta contable.
 *
 * El código y el tipo no se ofrecen: los asientos ya registrados apuntan a
 * esta cuenta y el tipo decide su naturaleza (deudora/acreedora), o sea el
 * signo con el que se leyó todo lo que ya se asentó. Una cuenta mal creada
 * se desactiva y se crea la correcta. */
export async function editarCuentaAction(
  _previo: EstadoAsiento,
  formData: FormData,
): Promise<EstadoAsiento> {
  const id = String(formData.get("id") ?? "");
  const nombre = String(formData.get("nombre") ?? "").trim();
  if (!id) return { error: "Falta la cuenta a editar.", ok: false };
  if (!nombre) return { error: "El nombre es obligatorio.", ok: false };

  try {
    await apiFetch(`/api/v1/accounting/cuentas-contables/${id}`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: { nombre, activa: formData.get("activa") === "on" },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo guardar la cuenta.");
  }
  revalidatePath("/contabilidad/plan-cuentas");
  return { error: "", ok: true };
}

export async function abrirPeriodoAction(
  _previo: EstadoAsiento,
  formData: FormData,
): Promise<EstadoAsiento> {
  const anio = Number(formData.get("anio") ?? 0);
  const mes = Number(formData.get("mes") ?? 0);
  if (!anio || !mes) return { error: "Elegir año y mes.", ok: false };

  try {
    await apiFetch("/api/v1/accounting/periodos", {
      token: await token(),
      metodo: "POST",
      cuerpo: { anio, mes },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo abrir el periodo.");
  }
  revalidatePath("/contabilidad/periodos");
  return { error: "", ok: true };
}

export async function cerrarPeriodoAction(periodoId: string): Promise<EstadoAsiento> {
  try {
    await apiFetch(`/api/v1/accounting/periodos/${periodoId}/cerrar`, {
      token: await token(),
      metodo: "POST",
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo cerrar el periodo.");
  }
  revalidatePath("/contabilidad/periodos");
  return { error: "", ok: true };
}

export async function ejecutarPagoAction(
  _previo: EstadoAsiento,
  formData: FormData,
): Promise<EstadoAsiento> {
  const movimientoId = String(formData.get("movimiento_id") ?? "");
  const medioPago = String(formData.get("medio_pago") ?? "").trim();
  const constancia = String(formData.get("constancia") ?? "").trim();
  if (!movimientoId || !medioPago) return { error: "Falta el medio de pago.", ok: false };

  try {
    await apiFetch(`/api/v1/accounting/pagos-proveedor/${movimientoId}/ejecutar`, {
      token: await token(),
      metodo: "POST",
      cuerpo: { medio_pago: medioPago, constancia: constancia || undefined },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo ejecutar el pago.");
  }
  revalidatePath("/contabilidad/pagos");
  return { error: "", ok: true };
}

export async function rechazarPagoAction(movimientoId: string): Promise<EstadoAsiento> {
  try {
    await apiFetch(`/api/v1/accounting/pagos-proveedor/${movimientoId}/rechazar`, {
      token: await token(),
      metodo: "POST",
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo rechazar el pago.");
  }
  revalidatePath("/contabilidad/pagos");
  return { error: "", ok: true };
}

/** Siembra el Plan Contable General Empresarial en la empresa del usuario.
 * Idempotente: el botón se puede apretar dos veces sin duplicar nada. */
export async function importarPcgeAction(): Promise<EstadoAsiento> {
  try {
    await apiFetch("/api/v1/accounting/cuentas-contables/pcge", {
      token: await token(),
      metodo: "POST",
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo importar el plan contable.");
  }
  revalidatePath("/contabilidad/plan-cuentas");
  return { error: "", ok: true };
}
