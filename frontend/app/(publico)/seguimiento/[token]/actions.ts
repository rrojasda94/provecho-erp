"use server";

import { ApiError, apiFetch } from "@/lib/api";

/**
 * Server Action del enlace público de seguimiento (RN-DLV-008, ADR-098).
 *
 * Llama a `apiFetch` **sin token de sesión**: quien sigue su pedido no es
 * usuario del ERP. Lo que autoriza a leer es el token de la entrega, que
 * viaja en la ruta y sale del enlace que se le mandó por WhatsApp — mismo
 * criterio que `postular/[token]/actions.ts` con el token de convocatoria.
 *
 * La ruta va literal en la llamada: `lib/contrato.test.ts` escanea este
 * archivo y la compara contra `docs/architecture/openapi.json`.
 */

export type EstadoPublico = "preparando" | "en_camino" | "entregado" | "no_entregado";

export type HitoSeguimiento = { hito: string; at: string | null };

export type Seguimiento = {
  estado_publico: EstadoPublico;
  numero_orden: number | null;
  sucursal: { nombre: string };
  repartidor: { nombre: string } | null;
  eta_at: string | null;
  // Decimal del backend: llega como string u number según el serializador,
  // nunca se hace aritmética con esto — solo se le pasa a Maps (Number()).
  posicion: { lat: string | number; lng: string | number; registrado_at: string | null } | null;
  destino: { lat: string | number | null; lng: string | number | null };
  linea_tiempo: HitoSeguimiento[];
};

/**
 * El seguimiento detrás del token, o `null`.
 *
 * Token inexistente, vencido o de una entrega cancelada responden igual
 * —404— porque el backend ya los unifica (RN-DLV-008): distinguirlos acá
 * le confirmaría a quien reenvía el link que ese token existió alguna vez.
 */
export async function consultarSeguimiento(token: string): Promise<Seguimiento | null> {
  try {
    return await apiFetch<Seguimiento>(
      `/api/v1/delivery/publico/seguimiento/${encodeURIComponent(token)}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}
