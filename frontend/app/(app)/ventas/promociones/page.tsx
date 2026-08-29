import { ApiError, apiFetch } from "@/lib/api";
import { tienePermiso } from "@/lib/permisos";
import { obtenerSesion } from "@/lib/sesion";

import {
  PromocionesCliente,
  type Promocion,
  type Sucursal,
} from "./promociones-cliente";

/**
 * Las promociones que se aplican **solas** (ADR-076).
 *
 * Tres cosas distintas bajan un total en este ERP y conviene no mezclarlas:
 *
 * - **Esta pantalla**: reglas condicionales. El pedido las cumple o no; nadie
 *   las pide ni las firma.
 * - **El cupón** (ADR-061): un código por cliente, que se canjea en caja.
 * - **El descuento manual** (RN-COM-017): lo aplica el cajero y lo firma un
 *   supervisor con su PIN, sobre una orden concreta.
 *
 * Vive en Comercial y no en la caja porque crear una regla que regala margen
 * todos los días no es lo mismo que firmar un descuento puntual.
 */
export default async function PromocionesPage() {
  const { token, usuario } = await obtenerSesion();

  let promociones: Promocion[];
  try {
    promociones = await apiFetch<Promocion[]>("/api/v1/sales/promociones", { token });
  } catch (e) {
    return (
      <p className="text-secondary">
        {e instanceof ApiError && e.status === 403
          ? "Tu usuario no tiene permiso para ver las promociones. Pídele a un administrador `sales.gestionar_promociones`."
          : "No se pudieron cargar las promociones."}
      </p>
    );
  }

  // El catálogo de sucursales no bloquea: sin él la pantalla muestra "Todas"
  // y la promoción se crea igual para toda la empresa.
  const sucursales = await apiFetch<Sucursal[]>("/api/v1/sucursales", { token }).catch(
    () => [] as Sucursal[],
  );

  return (
    <PromocionesCliente
      promociones={promociones}
      sucursales={sucursales}
      puedeGestionar={tienePermiso(usuario.permisos, "sales.gestionar_promociones")}
    />
  );
}
