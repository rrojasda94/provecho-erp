"use client";

import { useId, useState } from "react";

/**
 * Campo de contraseña con "mostrar/ocultar".
 *
 * Quien escribe una clave en un celular no ve lo que teclea y no tiene forma
 * de saber si el error fue de dedo o de clave. El ojo es el estándar de hecho
 * desde hace años; la alternativa (reintentar a ciegas) es la que nos trajo el
 * reporte.
 */
export function CampoClave({
  className = "",
  ...props
}: Omit<React.InputHTMLAttributes<HTMLInputElement>, "type">) {
  const [visible, setVisible] = useState(false);
  const id = useId();
  return (
    <div className="relative">
      <input
        {...props}
        id={props.id ?? id}
        type={visible ? "text" : "password"}
        className={`w-full rounded border-2 border-negro px-3 py-2 pr-12 ${className}`}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-pressed={visible}
        aria-label={visible ? "Ocultar la contraseña" : "Mostrar la contraseña"}
        title={visible ? "Ocultar" : "Mostrar"}
        className="absolute right-1 top-1/2 -translate-y-1/2 rounded px-2 py-1 text-lg leading-none text-humo transition-transform active:scale-90"
      >
        {visible ? "🙈" : "👁"}
      </button>
    </div>
  );
}
