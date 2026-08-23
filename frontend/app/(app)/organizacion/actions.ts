"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { ubicacionDe } from "@/lib/ubicacion-form";

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
      ...ubicacionDe(formData),
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

  const guardada = await guardar(
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
      ...ubicacionDe(formData),
    },
    "la sucursal",
  );

  const almacenId = texto(formData, "almacen_id");
  if (!guardada.ok || !almacenId) return guardada;
  return guardarAbastecimiento(almacenId, formData, guardada);
}

/**
 * El abastecimiento se elige en la pantalla de sucursales pero se guarda en
 * `almacen`, que es de quien es el dato.
 *
 * Va después de guardar la sucursal y solo si esa parte salió bien: dejar el
 * almacén apuntando a otro central por un cambio de nombre que falló sería
 * peor que no haber guardado nada.
 */
async function guardarAbastecimiento(
  almacenId: string,
  formData: FormData,
  guardada: EstadoOrganizacion,
): Promise<EstadoOrganizacion> {
  try {
    await apiFetch(`/api/v1/almacenes/${almacenId}`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: {
        almacen_abastecedor_id: texto(formData, "almacen_abastecedor_id") || undefined,
        almacen_abastecedor_respaldo_id:
          texto(formData, "almacen_abastecedor_respaldo_id") || undefined,
      },
    });
  } catch (e) {
    return {
      error: mensajeDe(e, "La sucursal se guardó, pero no su abastecimiento."),
      ok: false,
    };
  }
  revalidatePath("/organizacion/sucursales");
  return guardada;
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
      almacen_abastecedor_respaldo_id:
        texto(formData, "almacen_abastecedor_respaldo_id") || undefined,
      ...ubicacionDe(formData),
    },
    "el almacén",
  );
}

// --- Punto de venta ---------------------------------------------------------

/**
 * La caja de una sucursal. Vive acá y no en Ventas porque asignarle series
 * SUNAT es identidad fiscal de la empresa, del mismo orden que fundar el
 * local — el backend la gatea con `organizacion.gestionar` (ADR-059).
 */
export async function guardarPuntoVentaAction(
  _previo: EstadoOrganizacion,
  formData: FormData,
): Promise<EstadoOrganizacion> {
  const sucursalId = texto(formData, "sucursal_id");
  const serieBoleta = texto(formData, "serie_boleta");
  const serieFactura = texto(formData, "serie_factura");
  const editando = Boolean(texto(formData, "id"));

  if (!editando && !sucursalId) {
    return { error: "Elige la sucursal a la que pertenece la caja.", ok: false };
  }
  if (!serieBoleta || !serieFactura) {
    return { error: "Las series de boleta y factura son obligatorias.", ok: false };
  }

  // Sin ninguna marcada el backend rechaza la lista vacía; `undefined` es lo
  // que significa "las tres" (RN-MDC-001).
  const modalidades = formData.getAll("modalidades_habilitadas").map(String);

  return guardar(
    "/api/v1/sales/puntos-venta",
    "/organizacion/puntos-venta",
    formData,
    {
      // La caja no se muda de local: sus comprobantes y aperturas cuelgan de
      // ahí, así que al editar ni se manda.
      ...(editando ? {} : { sucursal_id: sucursalId }),
      canal: texto(formData, "canal"),
      politica_pago: texto(formData, "politica_pago"),
      serie_boleta: serieBoleta,
      serie_factura: serieFactura,
      serie_nc_boleta: texto(formData, "serie_nc_boleta") || null,
      serie_nc_factura: texto(formData, "serie_nc_factura") || null,
      hardware_id: texto(formData, "hardware_id") || null,
      modalidades_habilitadas: modalidades.length ? modalidades : null,
    },
    "el punto de venta",
  );
}
