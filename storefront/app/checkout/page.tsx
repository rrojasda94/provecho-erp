import type { Metadata } from "next";

import { apiAuth, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/auth";

import { CheckoutCliente, type Direccion, type Perfil, type SucursalOpcion } from "./checkout-cliente";

export const metadata: Metadata = { title: "Checkout" };

export default async function CheckoutPage() {
  const sesion = await obtenerSesion();
  const [sucursales, perfil, direcciones] = await Promise.all([
    apiFetch<SucursalOpcion[]>("/api/v1/storefront/publico/sucursales"),
    sesion
      ? apiAuth<Perfil>("/api/v1/storefront/cuentas/me", { token: sesion.token }).catch(() => null)
      : Promise.resolve(null),
    sesion
      ? apiAuth<Direccion[]>("/api/v1/storefront/cuentas/me/direcciones", {
          token: sesion.token,
        }).catch(() => [])
      : Promise.resolve([]),
  ]);

  return (
    <CheckoutCliente
      sucursales={sucursales ?? []}
      perfil={perfil}
      direcciones={direcciones ?? []}
    />
  );
}
