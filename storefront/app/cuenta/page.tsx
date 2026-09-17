import { redirect } from "next/navigation";
import type { Metadata } from "next";

import { apiAuth } from "@/lib/api";
import { obtenerSesion } from "@/lib/auth";

import { CuentaCliente, type Direccion, type Perfil, type UltimoPedido } from "./cuenta-cliente";

export const metadata: Metadata = { title: "Mi cuenta" };

export default async function CuentaPage() {
  const sesion = await obtenerSesion();
  if (!sesion) redirect("/cuenta/ingresar");

  const [perfil, direcciones, favoritos, ultimoPedido] = await Promise.all([
    apiAuth<Perfil>("/api/v1/storefront/cuentas/me", { token: sesion.token }),
    apiAuth<Direccion[]>("/api/v1/storefront/cuentas/me/direcciones", { token: sesion.token }),
    apiAuth<string[]>("/api/v1/storefront/cuentas/me/favoritos", { token: sesion.token }),
    apiAuth<UltimoPedido | null>("/api/v1/storefront/cuentas/me/ultimo-pedido", {
      token: sesion.token,
    }),
  ]);

  return (
    <CuentaCliente
      perfil={perfil}
      direcciones={direcciones}
      favoritosIds={favoritos}
      ultimoPedido={ultimoPedido}
    />
  );
}
