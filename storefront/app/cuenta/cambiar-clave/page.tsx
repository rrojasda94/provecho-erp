import { redirect } from "next/navigation";
import type { Metadata } from "next";

import { apiAuth } from "@/lib/api";
import { obtenerSesion } from "@/lib/auth";

import { CambiarClaveForm } from "./cambiar-clave-form";

export const metadata: Metadata = { title: "Cambiar mi clave" };

type Perfil = { tiene_password: boolean; debe_cambiar_clave: boolean };

export default async function CambiarClavePage() {
  const sesion = await obtenerSesion();
  if (!sesion) redirect("/cuenta/ingresar");
  const perfil = await apiAuth<Perfil>("/api/v1/storefront/cuentas/me", { token: sesion.token });

  return (
    <div className="mx-auto flex max-w-sm flex-col gap-4 px-4 py-16">
      <h1 className="font-display text-2xl uppercase text-negro">Cambiar mi clave</h1>
      {perfil.debe_cambiar_clave && (
        <p className="rounded border-2 border-rojo bg-crema-2 px-3 py-2 text-sm">
          Entraste con una clave temporal. Elige una propia para seguir.
        </p>
      )}
      <CambiarClaveForm pideActual={perfil.tiene_password} />
    </div>
  );
}
