"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type EstadoOrganizacion = EstadoFormulario;

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
 * Alta y corrección comparten forma en las cinco entidades de organización:
 * el `id` en el formulario decide si es POST sobre la colección o PATCH
 * sobre el recurso. Cinco pares de acciones casi idénticas eran justo el
 * copiar-pegar que este cambio vino a sacar del frontend.
 */
async function guardar(
  coleccion: string,
  ruta: string,
  formData: FormData,
  cuerpo: Record<string, unknown>,
  queEs: string,
): Promise<EstadoOrganizacion> {
  const id = texto(formData, "id");
  try {
    await apiFetch(id ? `${coleccion}/${id}` : coleccion, {
      token: await token(),
      metodo: id ? "PATCH" : "POST",
      cuerpo,
    });
  } catch (e) {
    return { error: mensajeDe(e, `No se pudo guardar ${queEs}.`), ok: false };
  }
  revalidatePath(ruta);
  return { error: "", ok: true };
}

// --- Grupo ------------------------------------------------------------------

export async function guardarGrupoAction(
  _previo: EstadoOrganizacion,
  formData: FormData,
): Promise<EstadoOrganizacion> {
  const nombre = texto(formData, "nombre");
  if (!nombre) return { error: "El nombre es obligatorio.", ok: false };
  return guardar("/api/v1/grupos", "/organizacion/empresas", formData, { nombre }, "el grupo");
}

// --- Empresa ----------------------------------------------------------------

export async function guardarEmpresaAction(
  _previo: EstadoOrganizacion,
  formData: FormData,
): Promise<EstadoOrganizacion> {
  const razonSocial = texto(formData, "razon_social");
  const ruc = texto(formData, "ruc");
  const domicilio = texto(formData, "domicilio_fiscal");
  if (!razonSocial || !domicilio) {
    return { error: "Razón social y domicilio fiscal son obligatorios.", ok: false };
  }
  if (!/^\d{11}$/.test(ruc)) return { error: "El RUC son 11 dígitos.", ok: false };

  const grupoId = texto(formData, "grupo_id");
  return guardar(
    "/api/v1/empresas",
    "/organizacion/empresas",
    formData,
    {
      // `grupo_id` solo viaja al crear: una empresa no se muda de grupo, se
      // funda en uno. El PATCH tampoco lo acepta.
      ...(texto(formData, "id") ? {} : { grupo_id: grupoId }),
      razon_social: razonSocial,
      ruc,
      domicilio_fiscal: domicilio,
      tipo: String(formData.get("tipo") ?? "operativa"),
      zona_tributaria: String(formData.get("zona_tributaria") ?? "general"),
      contacto: texto(formData, "contacto") || undefined,
    },
    "la empresa",
  );
}

// --- Marca ------------------------------------------------------------------

export async function guardarMarcaAction(
  _previo: EstadoOrganizacion,
  formData: FormData,
): Promise<EstadoOrganizacion> {
  const nombre = texto(formData, "nombre");
  const tipo = texto(formData, "tipo");
  if (!nombre || !tipo) return { error: "Nombre y tipo son obligatorios.", ok: false };
  return guardar(
    "/api/v1/marcas",
    "/organizacion/marcas",
    formData,
    { nombre, tipo },
    "la marca",
  );
}

// --- Sucursal ---------------------------------------------------------------

export async function guardarSucursalAction(
  _previo: EstadoOrganizacion,
  formData: FormData,
): Promise<EstadoOrganizacion> {
  const nombre = texto(formData, "nombre");
  const direccion = texto(formData, "direccion");
  const marcaId = texto(formData, "marca_id");
  if (!nombre || !direccion) {
    return { error: "Nombre y dirección son obligatorios.", ok: false };
  }
  if (!marcaId) return { error: "Elegir la marca.", ok: false };

  return guardar(
    "/api/v1/sucursales",
    "/organizacion/sucursales",
    formData,
    {
      marca_id: marcaId,
      nombre,
      direccion,
      tenencia: String(formData.get("tenencia") ?? "alquilada"),
      // Cerrar un local es `estado="inactiva"`: no hay baja de sucursal, sigue
      // siendo el ancla de sus ventas, cajas y trabajadores.
      estado: String(formData.get("estado") ?? "activa"),
    },
    "la sucursal",
  );
}

// --- Almacén ----------------------------------------------------------------

export async function guardarAlmacenAction(
  _previo: EstadoOrganizacion,
  formData: FormData,
): Promise<EstadoOrganizacion> {
  const nombre = texto(formData, "nombre");
  const tipo = texto(formData, "tipo");
  if (!nombre || !tipo) return { error: "Nombre y tipo son obligatorios.", ok: false };

  return guardar(
    "/api/v1/almacenes",
    "/organizacion/almacenes",
    formData,
    {
      nombre,
      tipo,
      direccion: texto(formData, "direccion") || undefined,
      sucursal_id: texto(formData, "sucursal_id") || undefined,
      almacen_abastecedor_id: texto(formData, "almacen_abastecedor_id") || undefined,
    },
    "el almacén",
  );
}
