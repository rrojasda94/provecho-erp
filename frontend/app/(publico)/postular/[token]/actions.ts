"use server";

import { ApiError, apiFetch } from "@/lib/api";

import type { EstadoPostulacion } from "./estado";

/**
 * Server Action del formulario público de postulación.
 *
 * Llama a `apiFetch` **sin token de sesión**: quien postula no es usuario del
 * ERP. Lo que autoriza a escribir es el token de la convocatoria, que viaja en
 * la ruta y sale de la URL que el candidato abrió (ADR-087). Tampoco pasa por
 * `app/api/proxy/[...ruta]`, que exige la cookie y responde 401 sin ella.
 */

// La ruta va literal en la llamada, como en toda Server Action del front:
// `lib/contrato.test.ts` escanea estos archivos y compara cada ruta contra
// `docs/architecture/openapi.json`.

/** La pregunta abierta del formulario. Es la clave con la que se guarda en
 *  `respuestas` y la que después se lee en la ficha del postulante, así que
 *  se escribe una sola vez. */
const PREGUNTA_ABIERTA = "Experiencia y disponibilidad";

function texto(datos: FormData, campo: string): string {
  return String(datos.get(campo) ?? "").trim();
}

/** El vacío de un `FormData` es `""`, y la API espera `null`. */
function opcional(datos: FormData, campo: string): string | null {
  return texto(datos, campo) || null;
}

export async function postularAction(
  _previo: EstadoPostulacion,
  datos: FormData,
): Promise<EstadoPostulacion> {
  const convocatoria = texto(datos, "convocatoria");
  const nombres = texto(datos, "nombres");
  const apellidos = texto(datos, "apellidos");
  const telefono = texto(datos, "telefono");
  const experiencia = texto(datos, "experiencia");

  // Validación de forma acá, reglas de negocio en la API: lo primero evita un
  // viaje para decir algo que se ve desde el navegador; lo segundo no se
  // duplica, porque una regla escrita dos veces se corrige una sola.
  if (!nombres || !apellidos) {
    return { error: "Escribe tus nombres y apellidos.", puesto: "" };
  }
  if (telefono.length < 6) {
    return { error: "Escribe un teléfono con el que podamos ubicarte.", puesto: "" };
  }
  if (datos.get("consentimiento_datos") !== "on") {
    return {
      error: "Para postular necesitamos tu autorización para tratar tus datos.",
      puesto: "",
    };
  }

  try {
    const acuse = await apiFetch<{ recibida: boolean; puesto: string }>(
      `/api/v1/rrhh/postulaciones/${encodeURIComponent(convocatoria)}`,
      {
        metodo: "POST",
        cuerpo: {
          nombres,
          apellidos,
          telefono,
          email: opcional(datos, "email"),
          canal_origen: opcional(datos, "canal_origen"),
          respuestas: experiencia ? { [PREGUNTA_ABIERTA]: experiencia } : null,
          consentimiento_datos: true,
        },
      },
    );
    return { error: "", puesto: acuse.puesto };
  } catch (e) {
    // Los mensajes del caso de uso son los que le dicen al candidato cuál de
    // los caminos le tocó —«la convocatoria cerró su fecha límite»— y
    // traducirlos todos a «no se pudo» sería justo perder eso.
    if (e instanceof ApiError) return { error: e.message, puesto: "" };
    return {
      error:
        "No pudimos registrar tu postulación. Vuelve a intentarlo en un momento.",
      puesto: "",
    };
  }
}
