import Link from "next/link";
import type { Metadata } from "next";

import { apiFetch } from "@/lib/api";

import { RecuperarForm } from "./recuperar-form";

export const metadata: Metadata = { title: "Recuperar mi clave" };

type Contenido = { contenido: { contacto?: { whatsapp?: string } } };

export default async function RecuperarPage() {
  const datos = await apiFetch<Contenido>("/api/v1/storefront/publico/contenido");
  const whatsapp = datos?.contenido?.contacto?.whatsapp?.replace(/\D/g, "");

  return (
    <div className="mx-auto flex max-w-sm flex-col gap-4 px-4 py-16">
      <h1 className="font-display text-2xl uppercase text-negro">Recuperar mi clave</h1>
      <p className="text-sm text-humo">
        Escribe el email de tu cuenta y te mandamos un enlace para elegir una clave nueva.
      </p>
      <RecuperarForm />
      <div className="rounded border-2 border-negro/20 bg-white p-3 text-sm text-humo">
        <strong className="text-negro">¿No tienes acceso a ese correo?</strong> Llámanos o
        escríbenos y te ayudamos a entrar
        {whatsapp && (
          <>
            {": "}
            <a
              href={`https://wa.me/51${whatsapp}`}
              className="font-bold text-verde underline"
              target="_blank"
              rel="noreferrer"
            >
              WhatsApp {whatsapp}
            </a>
          </>
        )}
        .
      </div>
      <Link href="/cuenta/ingresar" className="text-center text-sm font-bold text-verde underline">
        Volver a ingresar
      </Link>
    </div>
  );
}
