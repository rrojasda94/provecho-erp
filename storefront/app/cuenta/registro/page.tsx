import Link from "next/link";
import type { Metadata } from "next";

import { GoogleBoton } from "@/components/google-boton";

import { RegistroForm } from "./registro-form";

export const metadata: Metadata = { title: "Crear cuenta" };

export default function RegistroPage() {
  const clientId = process.env.GOOGLE_OAUTH_CLIENT_ID ?? "";
  return (
    <div className="mx-auto flex max-w-sm flex-col gap-4 px-4 py-16">
      <h1 className="font-display text-2xl uppercase text-negro">Crear cuenta</h1>
      <p className="text-sm text-humo">
        Con tu cuenta guardas direcciones, favoritos y ves tu último pedido.
      </p>
      <GoogleBoton clientId={clientId} />
      {clientId && <div className="text-center text-xs text-humo">o con tu email</div>}
      <RegistroForm />
      <p className="text-center text-sm text-humo">
        ¿Ya tienes cuenta?{" "}
        <Link href="/cuenta/ingresar" className="font-bold text-verde underline">
          Ingresa
        </Link>
      </p>
    </div>
  );
}
