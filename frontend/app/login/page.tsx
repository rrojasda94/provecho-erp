"use client";

import { startTransition, useActionState, useEffect, useRef, useState } from "react";

import Pinpad from "@/components/pinpad/pinpad";

import { loginAction, type EstadoLogin } from "./actions";

/**
 * Entrada al ERP: usuario tecleado + PIN en el pinpad (ADR-050).
 *
 * El PIN **no tiene campo**. Mientras lo tuvo, el navegador ofrecía
 * guardarlo, y un PIN guardado en la tablet de la caja hace que el turno
 * siguiente entre con la cuenta del anterior — con toda la auditoría de
 * RN-AUD-005 nombrando a la persona equivocada. ADR-045 ya lo había sacado
 * de los cuatro diálogos del PDV; el login era la puerta que quedaba
 * abierta, y es la que más veces se cruza.
 */

const ESTADO_INICIAL: EstadoLogin = { error: "", motivo: "" };

/**
 * Último usuario de la app instalada (ADR-109). La sesión sigue muriendo al
 * cerrarse la app (ADR-084) y Android la cierra cuando quiere: sin esto el
 * repartidor tecleaba su usuario cada vez. Solo el usuario, nunca el PIN
 * (ADR-050), y solo en la app instalada — en el navegador de una PC
 * compartida no se recuerda nada.
 */
const CLAVE_ULTIMO_USUARIO = "provecho.ultimo_usuario";

function esAppInstalada(): boolean {
  return window.matchMedia("(display-mode: standalone)").matches;
}

function recordarUsuario(valor: string | null) {
  try {
    if (valor) localStorage.setItem(CLAVE_ULTIMO_USUARIO, valor);
    else localStorage.removeItem(CLAVE_ULTIMO_USUARIO);
  } catch {
    // Almacenamiento bloqueado: se vuelve a escribir el usuario, nada más.
  }
}

export default function LoginPage() {
  const [estado, despachar, pendiente] = useActionState(loginAction, ESTADO_INICIAL);
  const usuario = useRef<HTMLInputElement>(null);
  const [pin, setPin] = useState("");
  const [recordado, setRecordado] = useState("");

  useEffect(() => {
    if (!esAppInstalada() || !usuario.current || usuario.current.value) return;
    let valor: string | null = null;
    try {
      valor = localStorage.getItem(CLAVE_ULTIMO_USUARIO);
    } catch {
      return;
    }
    if (!valor) return;
    usuario.current.value = valor;
    // Sin foco en el usuario: en el teléfono abriría el teclado encima del
    // pinpad, que es lo único que queda por tocar.
    usuario.current.blur();
    setRecordado(valor);
  }, []);

  // La acción se despacha a mano y **nunca** por `<form action={...}>`: React
  // 19 resetea los campos de un formulario cuando su acción termina, también
  // cuando devolvió error, y con el PIN equivocado se borraba además el
  // usuario. Volver a escribirlo en cada intento es justo la fricción que
  // empuja a dejar la sesión de otro abierta. Mismo candado que ya se puso en
  // los diálogos del back office (`components/formulario/`).
  //
  // El usuario queda **sin controlar**, leído del DOM al enviar. No es
  // descuido: mientras la página no hidrata, lo que se teclee vive solo en el
  // DOM, y un campo controlado descartaría eso al arrancar React. Sin
  // `action` no hay reseteo del que defenderse, así que no hace falta estado.
  const enviar = (candidato: string) => {
    const datos = new FormData();
    datos.set("username", usuario.current?.value ?? "");
    datos.set("pin", candidato);
    if (esAppInstalada()) recordarUsuario(usuario.current?.value.trim() || null);
    // `?next=` lo agrega `/oauth/authorize` (ADR-083 Fase B) cuando el SSO
    // del BI encuentra a alguien sin sesión de Provecho todavía. Leído del
    // `location` y no de un hook de router: esta página es enteramente
    // cliente y no hay otro dato de servidor que justifique el round-trip
    // extra ni el `<Suspense>` que pide `useSearchParams`.
    const siguiente = new URLSearchParams(window.location.search).get("next");
    if (siguiente) datos.set("next", siguiente);
    // Dentro de una transición porque la acción es asíncrona: despachada
    // suelta, React avisa que `pendiente` no se actualiza bien — y sin
    // `pendiente` el botón nunca dice "Ingresando..." ni se bloquea, así que
    // un segundo toque manda el mismo PIN dos veces.
    startTransition(() => despachar(datos));
    // Todo envío vacía el pinpad, y en el mismo gesto y no al llegar la
    // respuesta: si el servidor rechaza, los seis puntos llenos no dejarían
    // teclear de nuevo sin borrar a mano, y lo que se haya tocado mientras
    // tanto no se pierde. Si lo enviado iba a medias, empezar de cero es
    // mejor que adivinar por dónde iba — de los dígitos solo se ven puntos.
    setPin("");
  };

  return (
    <main className="login-page">
      <div className="login-card">
        <h1>Provecho</h1>
        <p className="login-tagline">¿Qué se te antoja hoy?</p>
        <form
          className="login-form"
          onSubmit={(e) => {
            e.preventDefault();
            enviar(pin);
          }}
        >
          <label>
            Usuario
            <input ref={usuario} name="username" autoComplete="username" required autoFocus />
          </label>
          {recordado && (
            <button
              type="button"
              className="login-no-soy-yo"
              onClick={() => {
                recordarUsuario(null);
                setRecordado("");
                if (usuario.current) {
                  usuario.current.value = "";
                  usuario.current.focus();
                }
              }}
            >
              No soy {recordado}
            </button>
          )}
          <div className="login-pin">
            <span className="login-pin-titulo">PIN</span>
            {/* Al sexto dígito entra solo: en una tablet un botón más es un
                toque más, y desde una PC el teclado numérico ya lo completa
                sin soltar las manos. "Ingresar" queda igual para quien
                llegó hasta acá con Tab. */}
            <Pinpad
              value={pin}
              onChange={setPin}
              label="Tu PIN"
              testid="login-pin"
              onCompleto={enviar}
            />
            <p className="login-nota">Toca los dígitos o usa el teclado numérico.</p>
          </div>
          {estado.error && (
            <p
              className="login-error"
              role="alert"
              data-testid="login-error"
              data-motivo={estado.motivo}
            >
              {estado.error}
            </p>
          )}
          <button type="submit" disabled={pendiente}>
            {pendiente ? "Ingresando..." : "Ingresar"}
          </button>
        </form>
      </div>
    </main>
  );
}
