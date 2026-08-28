"use client";

import { useEffect, useRef, useState } from "react";

import { logoutAction } from "@/app/(app)/actions";
import { ErrorApi } from "@/lib/cliente-api";
import { api } from "@/lib/pdv";

import Pinpad from "./pinpad";

/**
 * Bloqueo de pantalla del PDV por inactividad (ADR-045, RN-POS-014).
 *
 * NO cierra sesión, y esa es toda la diferencia: la caja abierta, el
 * borrador del pedido y las cookies quedan intactos. Cerrar sesión a los
 * cinco minutos habría hecho que el turno dejara la sesión abierta a
 * propósito para no perder el pedido a medio armar, que es justo lo que
 * hay que evitar.
 *
 * Se desbloquea con el PIN del dueño de la sesión contra
 * `POST /auth/verificar-pin`; "Cambiar de usuario" sí hace logout real.
 *
 * También se bloquea **a pedido**, con el botón del encabezado del PDV: los
 * cinco minutos no le sirven a quien se aleja de la caja y quiere cerrarla
 * al irse. Llega por un evento de `window` y no por una prop porque este
 * overlay vive fuera de `PdvCliente` a propósito — es un `<dialog>` del top
 * layer, y meterlo adentro para pasarle un estado perdería eso.
 */

const INACTIVIDAD_MS = 5 * 60 * 1000;
/** Cada cuánto se comprueba si ya pasó el plazo. Un `setTimeout` de cinco
 * minutos no sirve: en una tablet con la pantalla apagada el navegador lo
 * estrangula y llega tarde — que es exactamente cuando hay que bloquear. */
const LATIDO_MS = 10_000;

export default function BloqueoPorInactividad({ username }: { username: string }) {
  const [bloqueado, setBloqueado] = useState(false);
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [verificando, setVerificando] = useState(false);
  const dialogo = useRef<HTMLDialogElement>(null);
  // Arranca en 0 y se estampa al montar: leer el reloj durante el render
  // daría un valor distinto en cada re-render (y en el servidor, otro).
  const ultimaActividad = useRef(0);

  useEffect(() => {
    const tocar = () => {
      ultimaActividad.current = Date.now();
    };
    tocar();
    // En captura: hay diálogos nativos por encima de todo, y sin capturar
    // el PDV no se enteraría de que alguien está operando dentro de uno.
    const opciones = { capture: true, passive: true } as const;
    // `wheel` y `touchmove` cuentan como actividad además del toque y la
    // tecla: en una tablet, recorrer la carta con el dedo es operar el PDV,
    // y sin ellos la pantalla se bloqueaba en la cara de quien la estaba
    // usando.
    for (const evento of ["pointerdown", "keydown", "wheel", "touchmove"]) {
      window.addEventListener(evento, tocar, opciones);
    }
    const bloquearAhora = () => setBloqueado(true);
    window.addEventListener("pdv:bloquear", bloquearAhora);
    const latido = setInterval(() => {
      if (Date.now() - ultimaActividad.current >= INACTIVIDAD_MS) setBloqueado(true);
    }, LATIDO_MS);
    return () => {
      for (const evento of ["pointerdown", "keydown", "wheel", "touchmove"]) {
        window.removeEventListener(evento, tocar, opciones);
      }
      window.removeEventListener("pdv:bloquear", bloquearAhora);
      clearInterval(latido);
    };
  }, []);

  useEffect(() => {
    const d = dialogo.current;
    if (!d) return;
    // `showModal()` mete el overlay en la capa superior del navegador, que
    // es la única forma de tapar un `<dialog>` ya abierto: ningún `z-index`
    // gana contra el top layer.
    if (bloqueado && !d.open) d.showModal();
    if (!bloqueado && d.open) d.close();
  }, [bloqueado]);

  const desbloquear = async (candidato: string) => {
    setVerificando(true);
    setError(null);
    try {
      await api.verificarPin(candidato);
      ultimaActividad.current = Date.now();
      setPin("");
      setBloqueado(false);
    } catch (e) {
      setPin("");
      setError(
        e instanceof ErrorApi && e.status === 423
          ? "Cuenta bloqueada por intentos fallidos. Pide ayuda a un supervisor."
          : "PIN incorrecto.",
      );
    } finally {
      setVerificando(false);
    }
  };

  return (
    <dialog
      ref={dialogo}
      className="pdv-bloqueo"
      aria-label="Pantalla bloqueada"
      // Escape no desbloquea: sería una pantalla bloqueada que se abre sola.
      onCancel={(e) => e.preventDefault()}
    >
      <div className="pdv-bloqueo-caja">
        <h2>Pantalla bloqueada</h2>
        <p>
          Sesión de <strong>{username}</strong>. El pedido y la caja siguen abiertos —
          ingresa tu PIN para seguir.
        </p>
        <Pinpad
          value={pin}
          onChange={setPin}
          label="Tu PIN"
          testid="bloqueo-pin"
          onCompleto={desbloquear}
        />
        {error && <p className="pdv-error">{error}</p>}
        {verificando && <p className="pdv-nota">Verificando…</p>}
        <button
          type="button"
          className="pdv-bloqueo-salir"
          onClick={() => logoutAction()}
        >
          Cambiar de usuario
        </button>
      </div>
    </dialog>
  );
}
