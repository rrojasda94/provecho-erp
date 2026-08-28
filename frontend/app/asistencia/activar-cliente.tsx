"use client";

/**
 * Pantalla de activación del pad (ADR-073): sin el secreto del terminal, la
 * tablet no muestra tarjetas ni marca nada — la sesión de la cuenta de
 * servicio ya no alcanza sola. Un admin genera el código de 6 dígitos desde
 * Organización → Terminales; la tablet lo teclea acá, una sola vez.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";

import Pinpad from "@/components/pinpad/pinpad";
import { apiAsistencia } from "@/lib/asistencia";
import { ErrorApi } from "@/lib/cliente-api";

import { guardarTerminalAction } from "./actions";

export default function ActivarCliente({ sucursalId }: { sucursalId: string }) {
  const [codigo, setCodigo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const router = useRouter();

  const activar = async (codigoCompleto: string) => {
    if (enviando) return;
    setEnviando(true);
    setError(null);
    try {
      const { secreto } = await apiAsistencia.enrolarTerminal(sucursalId, codigoCompleto);
      // El secreto solo se ve una vez: se guarda en la cookie httpOnly del
      // terminal y de acá en más el navegador nunca vuelve a tocarlo.
      await guardarTerminalAction(secreto);
      router.refresh();
    } catch (e) {
      setCodigo("");
      setError(
        e instanceof ErrorApi ? e.message : "No se pudo activar el terminal",
      );
    } finally {
      setEnviando(false);
    }
  };

  return (
    <main className="asistencia-vacio">
      <h1>Activar este terminal</h1>
      <p>
        Pide a un administrador el código de 6 dígitos del terminal de este
        local (Organización → Terminales) y tecléalo acá.
      </p>
      {error && <p className="asistencia-error">{error}</p>}
      <Pinpad
        value={codigo}
        onChange={setCodigo}
        label="Código del terminal"
        testid="pinpad-activacion"
        onCompleto={activar}
      />
    </main>
  );
}
