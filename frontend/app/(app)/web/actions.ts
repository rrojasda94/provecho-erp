"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { ESTADO_INICIAL, estadoDeError, type EstadoFormulario } from "@/lib/errores";

export { ESTADO_INICIAL };
export type { EstadoFormulario };

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function texto(formData: FormData, campo: string): string {
  return String(formData.get(campo) ?? "").trim();
}

// --- CMS de contenido (`storefront_contenido`) -------------------------------

function leerHero(formData: FormData) {
  return {
    titulo: texto(formData, "titulo"),
    subtitulo: texto(formData, "subtitulo") || undefined,
    cta_texto: texto(formData, "cta_texto") || undefined,
    cta_url: texto(formData, "cta_url") || undefined,
    imagen_url: texto(formData, "imagen_url") || undefined,
  };
}

function leerNosotros(formData: FormData) {
  return {
    titulo: texto(formData, "titulo"),
    parrafos: texto(formData, "parrafos")
      .split("\n")
      .map((p) => p.trim())
      .filter(Boolean),
    hitos: [],
  };
}

function leerContacto(formData: FormData) {
  return {
    whatsapp: texto(formData, "whatsapp") || undefined,
    email: texto(formData, "email") || undefined,
    instagram: texto(formData, "instagram") || undefined,
    facebook: texto(formData, "facebook") || undefined,
    tiktok: texto(formData, "tiktok") || undefined,
  };
}

function leerTrabaja(formData: FormData) {
  return { titulo: texto(formData, "titulo"), cuerpo: texto(formData, "cuerpo") };
}

function leerPie(formData: FormData) {
  return { texto: texto(formData, "texto") };
}

function leerSeo(formData: FormData) {
  return { titulo: texto(formData, "titulo"), descripcion: texto(formData, "descripcion") };
}

const LECTORES_POR_CLAVE: Record<string, (formData: FormData) => Record<string, unknown>> = {
  hero: leerHero,
  nosotros: leerNosotros,
  contacto: leerContacto,
  trabaja: leerTrabaja,
  pie: leerPie,
  seo: leerSeo,
};

/** Arma `valor` según la clave: cada clave tiene su propia forma de campos
 * en el formulario (ver `contenido-cliente.tsx`). */
function leerValorDeContenido(clave: string, formData: FormData): Record<string, unknown> {
  return LECTORES_POR_CLAVE[clave]?.(formData) ?? {};
}

export async function guardarContenidoAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const marcaId = texto(formData, "marca_id");
  const clave = texto(formData, "clave");
  if (!marcaId || !clave) return { error: "Falta la marca o la clave de contenido.", ok: false };

  try {
    await apiFetch(`/api/v1/storefront/contenido/${clave}?marca_id=${marcaId}`, {
      token: await token(),
      metodo: "PUT",
      cuerpo: { valor: leerValorDeContenido(clave, formData) },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo guardar el contenido.");
  }
  revalidatePath("/web");
  return { error: "", ok: true };
}

// --- Fotos de catálogo (producto/ingrediente) --------------------------------

type Entidad = "producto" | "ingrediente";

export async function subirFotoAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const entidad = texto(formData, "entidad") as Entidad;
  const entidadId = texto(formData, "entidad_id");
  const archivo = formData.get("archivo");
  if (!(archivo instanceof File) || archivo.size === 0) {
    return { error: "Elige una foto.", ok: false };
  }

  try {
    const t = await token();
    const presign = await apiFetch<{ upload_url: string; url_storage: string }>(
      `/api/v1/storefront/fotos/${entidad}/${entidadId}/presign-upload`,
      {
        token: t,
        metodo: "POST",
        cuerpo: { nombre: archivo.name, mime_type: archivo.type || "image/jpeg" },
      },
    );

    const subida = await fetch(presign.upload_url, {
      method: "PUT",
      headers: { "Content-Type": archivo.type || "image/jpeg" },
      body: await archivo.arrayBuffer(),
    });
    if (!subida.ok) {
      return { error: "No se pudo subir la foto al almacenamiento.", ok: false };
    }

    await apiFetch(`/api/v1/storefront/fotos/${entidad}/${entidadId}`, {
      token: t,
      metodo: "POST",
      cuerpo: {
        nombre: archivo.name,
        mime_type: archivo.type || "image/jpeg",
        tamano_bytes: archivo.size,
        url_storage: presign.url_storage,
      },
    });
  } catch (e) {
    const mensaje = e instanceof ApiError ? e.message : "No se pudo subir la foto.";
    return { error: mensaje, ok: false };
  }
  revalidatePath("/web/carta");
  revalidatePath("/web/ingredientes");
  return { error: "", ok: true };
}

export async function borrarFotoAction(archivoId: string): Promise<void> {
  await apiFetch(`/api/v1/storefront/fotos/${archivoId}`, {
    token: await token(),
    metodo: "DELETE",
  });
  revalidatePath("/web/carta");
  revalidatePath("/web/ingredientes");
}

// --- Descripción de producto / insumo ----------------------------------------

export async function guardarDescripcionProductoAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const productoId = texto(formData, "producto_id");
  try {
    await apiFetch(`/api/v1/sales/productos/${productoId}`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: { descripcion: texto(formData, "descripcion") || null },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo guardar la descripción.");
  }
  revalidatePath("/web/carta");
  return { error: "", ok: true };
}

export async function guardarDescripcionArticuloAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const articuloId = texto(formData, "articulo_id");
  try {
    await apiFetch(`/api/v1/inventory/articulos/${articuloId}`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: { descripcion: texto(formData, "descripcion") || null },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo guardar la descripción.");
  }
  revalidatePath("/web/ingredientes");
  return { error: "", ok: true };
}
