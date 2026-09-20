"use client";

import { useFormStatus } from "react-dom";

/**
 * Botón de envío con estado de espera.
 *
 * El sitio tenía ocho formularios que al enviarse solo se deshabilitaban: sin
 * texto, sin giro, sin nada. En un celular con la conexión de un local eso se
 * ve idéntico a "el botón no hizo nada" — el reporte literal fue "no se sabe
 * si el click fue bueno". `useFormStatus` lee el estado del `<form>` padre, así
 * que no hay que pasarle `pendiente` desde cada pantalla.
 */
export function Boton({
  children,
  esperando = "Enviando...",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { esperando?: string }) {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending || props.disabled}
      aria-busy={pending}
      className={`sombra-dura flex items-center justify-center gap-2 rounded bg-verde px-4 py-2 font-bold uppercase text-negro disabled:opacity-60 ${className}`}
      {...props}
    >
      {pending && <Girador />}
      {pending ? esperando : children}
    </button>
  );
}

/** Giro de espera. `currentColor` para que sirva sobre verde o sobre crema, y
 * `aria-hidden` porque quien usa lector de pantalla ya oyó el `aria-busy`. */
export function Girador({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
