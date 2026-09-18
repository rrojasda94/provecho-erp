"use client";

import Script from "next/script";
import { useState } from "react";

import { loginGoogleAction } from "@/app/cuenta/actions";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: { client_id: string; callback: (r: { credential: string }) => void }) => void;
          renderButton: (parent: HTMLElement, opciones: Record<string, unknown>) => void;
        };
      };
    };
  }
}

/**
 * "Continuar con Google" (ADR-104). Si la cuenta ya existe, entra directo.
 * Si es nueva, el backend responde 409 pidiendo el resto del perfil
 * (RN-WEB-005) y este componente muestra el formulario que falta antes de
 * reintentar con los mismos datos de Google.
 */
export function GoogleBoton({ clientId }: { clientId: string }) {
  const [idToken, setIdToken] = useState<string | null>(null);
  const [faltaPerfil, setFaltaPerfil] = useState(false);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  const intentar = async (token: string, extra: Record<string, string> = {}) => {
    setEnviando(true);
    setError("");
    const resultado = await loginGoogleAction({ idToken: token, ...extra });
    setEnviando(false);
    if (resultado.error.toLowerCase().includes("faltan datos")) {
      setIdToken(token);
      setFaltaPerfil(true);
      return;
    }
    if (resultado.error) setError(resultado.error);
  };

  if (!clientId) return null;

  return (
    <div className="flex flex-col gap-3">
      {!faltaPerfil && (
        <>
          <Script
            src="https://accounts.google.com/gsi/client"
            strategy="afterInteractive"
            onReady={() => {
              const contenedor = document.getElementById("google-boton");
              if (!contenedor || !window.google) return;
              window.google.accounts.id.initialize({
                client_id: clientId,
                callback: (r) => void intentar(r.credential),
              });
              window.google.accounts.id.renderButton(contenedor, {
                theme: "outline", size: "large", width: 280,
              });
            }}
          />
          <div id="google-boton" />
        </>
      )}
      {faltaPerfil && idToken && (
        <form
          className="flex flex-col gap-2 rounded border-2 border-negro bg-crema-2 p-4"
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            void intentar(idToken, {
              numeroDocumento: String(f.get("numero_documento") ?? ""),
              telefono: String(f.get("telefono") ?? ""),
              fechaNacimiento: String(f.get("fecha_nacimiento") ?? ""),
              direccion: String(f.get("direccion") ?? ""),
            });
          }}
        >
          <p className="text-sm text-humo">
            Un dato más para crear tu cuenta con Google.
          </p>
          <input name="numero_documento" placeholder="DNI" required maxLength={15} />
          <input name="telefono" placeholder="Teléfono" required maxLength={20} />
          <input name="fecha_nacimiento" type="date" required />
          <input name="direccion" placeholder="Dirección (opcional)" maxLength={255} />
          <button
            type="submit"
            disabled={enviando}
            className="rounded bg-verde px-4 py-2 font-bold text-negro disabled:opacity-60"
          >
            {enviando ? "Creando..." : "Crear cuenta"}
          </button>
        </form>
      )}
      {error && <p className="text-sm text-rojo">{error}</p>}
    </div>
  );
}
