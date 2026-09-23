import Link from "next/link";
import type { Metadata } from "next";

import { GoogleBoton } from "@/components/google-boton";

import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Ingresar" };

export default async function IngresarPage({
  searchParams,
}: {
  searchParams: Promise<{ clave?: string }>;
}) {
  const clientId = process.env.GOOGLE_OAUTH_CLIENT_ID ?? "";
  const { clave } = await searchParams;
  return (
    <div className="mx-auto flex max-w-sm flex-col gap-4 px-4 py-16">
      <h1 className="font-display text-2xl uppercase text-negro">Ingresar</h1>
      {clave === "ok" && (
        <p className="rounded border-2 border-verde bg-crema-2 px-3 py-2 text-sm">
          Listo, cambiaste tu clave. Ingresa con la nueva.
        </p>
      )}
      <LoginForm />
      {/* Sin Client ID el botón no se dibuja: tampoco el separador. */}
      {clientId && <div className="text-center text-xs text-humo">o</div>}
      <GoogleBoton clientId={clientId} />
      <p className="text-center text-sm text-humo">
        ¿No tienes cuenta?{" "}
        <Link href="/cuenta/registro" className="font-bold text-verde underline">
          Regístrate
        </Link>
      </p>
    </div>
  );
}
