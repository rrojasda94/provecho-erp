"use server";

import { ApiError, apiFetch } from "@/lib/api";

import type { Cupon, EstadoRegistro } from "./estado";

/**
 * Server Actions de la landing pública.
 *
 * Llaman a `apiFetch` **sin token**, que es lo que la distingue del resto del
 * front: acá no hay sesión de la que sacarlo. Y no pasan por
 * `app/api/proxy/[...ruta]`, que exige la cookie y responde 401 sin ella.
 *
 * El navegador no habla con la API directo (la CSP tiene `connect-src 'self'`
 * y no hay excepción para el ERP, ver `middleware.ts`): el fetch sale del
 * proceso de Next contra `API_INTERNAL_URL`, igual que en todo el back office.
 */

// Las rutas van completas y literales en cada llamada, sin armarlas desde una
// constante: `lib/contrato.test.ts` escanea estos archivos y compara cada
// ruta contra `docs/architecture/openapi.json`. Una ruta interpolada es una
// ruta que ese test no puede leer, y deja de avisar cuando la API cambia.

function texto(datos: FormData, campo: string): string {
  return String(datos.get(campo) ?? "").trim();
}

/** El vacío de un `FormData` es `""`, y la API espera `null`. */
function opcional(datos: FormData, campo: string): string | null {
  return texto(datos, campo) || null;
}

/**
 * El nombre que RENIEC tiene para ese DNI, para que el cliente lo confirme.
 *
 * **Nunca lanza.** Si el proveedor no contesta devuelve vacío y el formulario
 * deja escribir el nombre a mano (RN-PTS-004): que un tercero esté caído no
 * puede ser el motivo por el que alguien no se registra.
 */
export async function buscarNombreAction(
  numeroDocumento: string,
): Promise<{ nombres: string; apellidos: string }> {
  const dni = numeroDocumento.trim();
  if (!/^\d{8}$/.test(dni)) return { nombres: "", apellidos: "" };
  try {
    return await apiFetch(`/api/v1/sales/publico/reconocerte/dni/${dni}/nombre`);
  } catch {
    return { nombres: "", apellidos: "" };
  }
}

/**
 * Registra al cliente y devuelve su cupón.
 *
 * Devuelve el error tal como lo mandó la API en vez de uno genérico: los
 * mensajes del caso de uso son los que le dicen al cliente cuál de los
 * caminos le tocó —«ya usaste tu cupón», «la promoción no está disponible»—
 * y traducirlos todos a «no se pudo» sería justo perder eso.
 */
export async function registrarAction(
  _previo: EstadoRegistro,
  datos: FormData,
): Promise<EstadoRegistro> {
  const numeroDocumento = texto(datos, "numero_documento");
  const nombre = texto(datos, "nombre");
  const telefono = texto(datos, "telefono");

  // Validación de forma acá, reglas de negocio en la API. Lo primero evita
  // un viaje para decir algo que se ve desde el navegador; lo segundo no se
  // duplica, porque una regla escrita dos veces se corrige una sola.
  if (!/^\d{8}$/.test(numeroDocumento)) {
    return { error: "El DNI son 8 dígitos.", cupon: null };
  }
  if (!nombre) {
    return { error: "Necesitamos tu nombre para registrarte.", cupon: null };
  }
  if (telefono.length < 6) {
    return { error: "Escribe un teléfono con el que podamos ubicarte.", cupon: null };
  }
  if (datos.get("acepta_terminos") !== "on") {
    return {
      error: "Para participar tienes que aceptar los términos y condiciones.",
      cupon: null,
    };
  }

  try {
    const cupon = await apiFetch<Cupon>("/api/v1/sales/publico/reconocerte/registro", {
      metodo: "POST",
      cuerpo: {
        numero_documento: numeroDocumento,
        nombre,
        telefono,
        fecha_nacimiento: opcional(datos, "fecha_nacimiento"),
        direccion: opcional(datos, "direccion"),
        ubicacion_place_id: opcional(datos, "ubicacion_place_id"),
        ubicacion_lat: opcional(datos, "ubicacion_lat"),
        ubicacion_lng: opcional(datos, "ubicacion_lng"),
        ubicacion_plus_code: opcional(datos, "ubicacion_plus_code"),
        ubicacion_distrito: opcional(datos, "ubicacion_distrito"),
        acepta_terminos: true,
      },
    });
    return { error: "", cupon };
  } catch (e) {
    if (e instanceof ApiError) return { error: e.message, cupon: null };
    // Se distingue del error de negocio a propósito: acá el cliente NO sabe
    // si su registro entró, y decirle que reintente sin avisarle eso lo
    // dejaría creyendo que no quedó nada.
    return {
      error:
        "No pudimos confirmar tu registro. Vuelve a intentarlo en un momento; " +
        "si ya estabas registrado, no se duplicará.",
      cupon: null,
    };
  }
}
