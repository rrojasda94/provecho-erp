import type { Ubicacion } from "@/components/direccion/ubicacion";

const NUMERICOS = new Set(["ubicacion_lat", "ubicacion_lng"]);

/**
 * Saca del `FormData` los cinco campos que escribe `CampoDireccion`.
 *
 * El vacío se convierte en `null` porque un `FormData` no sabe expresar null
 * —todo llega como texto— y la API distingue "sin ancla" de "ancla vacía":
 * un `""` en `ubicacion_lat` sería un 422.
 *
 * Se usa en las Server Actions de toda pantalla con dirección, y por eso vive
 * acá y no en una: la sexta copia de esta conversión sería la que se olvida
 * de convertir la latitud a número.
 */
export function ubicacionDe(formData: FormData): Ubicacion {
  const salida = {} as Record<string, string | number | null>;
  for (const campo of [
    "ubicacion_place_id",
    "ubicacion_lat",
    "ubicacion_lng",
    "ubicacion_plus_code",
    "ubicacion_distrito",
  ]) {
    const crudo = String(formData.get(campo) ?? "").trim();
    if (!crudo) {
      salida[campo] = null;
    } else if (NUMERICOS.has(campo)) {
      const numero = Number(crudo);
      salida[campo] = Number.isFinite(numero) ? numero : null;
    } else {
      salida[campo] = crudo;
    }
  }
  return salida as unknown as Ubicacion;
}
