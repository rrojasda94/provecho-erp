"use client";

import { useActionState, useEffect, useRef } from "react";

/**
 * Diálogo con formulario: el molde de toda alta y toda corrección del ERP.
 *
 * Existía copiado y pegado en siete pantallas —el mismo `<dialog>`, el mismo
 * `useActionState`, el mismo `role="alert"`, los mismos dos botones— y cada
 * pantalla nueva lo volvía a escribir. Con la edición encima habrían sido
 * veinte copias del mismo bloque; la que se olvidara de cerrar al `ok` o de
 * resetear al cancelar iba a ser un bug que nadie relaciona con las otras
 * diecinueve.
 *
 * Sigue siendo `<dialog>` nativo, no el `Dialog` de shadcn: el overlay, el
 * foco atrapado y el cierre con Esc ya vienen del navegador, y ninguna
 * pantalla pidió todavía algo que eso no cubra (ADR-013 dejó shadcn
 * instalado para cuando haga falta, no para usarlo por defecto).
 */

/** Lo que devuelve toda Server Action de formulario del ERP. */
export type EstadoFormulario = { error: string; ok: boolean };

export const ESTADO_INICIAL: EstadoFormulario = { error: "", ok: false };

const CLASE_PRIMARIO =
  "rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary disabled:opacity-50";

export function DialogoFormulario({
  titulo,
  disparador,
  accion,
  children,
  etiquetaEnvio = "Guardar",
  etiquetaPendiente = "Guardando...",
  claseDisparador = CLASE_PRIMARIO,
  ayuda,
  envioDeshabilitado = false,
  alAbrir,
  alCerrar,
}: {
  titulo: string;
  /** Contenido del botón que abre el diálogo. */
  disparador: React.ReactNode;
  accion: (
    estado: EstadoFormulario,
    formData: FormData,
  ) => Promise<EstadoFormulario>;
  children: React.ReactNode;
  etiquetaEnvio?: string;
  etiquetaPendiente?: string;
  claseDisparador?: string;
  /** Texto bajo el título: para qué sirve el formulario o qué no hace. */
  ayuda?: React.ReactNode;
  /** Para el caso "no se puede crear todavía" (sin unidades de medida, por ej.). */
  envioDeshabilitado?: boolean;
  /** Reset del estado propio de la pantalla, si el formulario tiene alguno. */
  alAbrir?: () => void;
  alCerrar?: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [estado, formAction, pendiente] = useActionState(accion, ESTADO_INICIAL);

  useEffect(() => {
    if (estado.ok) dialogRef.current?.close();
  }, [estado.ok]);

  return (
    <>
      <button
        type="button"
        onClick={() => {
          alAbrir?.();
          dialogRef.current?.showModal();
        }}
        className={claseDisparador}
      >
        {disparador}
      </button>
      <dialog
        ref={dialogRef}
        className="w-full max-w-md rounded-lg p-0 backdrop:bg-dark/40"
        onClose={() => {
          // El reset va al cerrar y no al enviar: si el servidor rechazó, lo
          // tecleado tiene que seguir ahí. Recontar un formulario entero
          // porque un campo estaba mal es la fricción que termina en un dato
          // inventado (mismo criterio que el conteo de caja).
          formRef.current?.reset();
          alCerrar?.();
        }}
      >
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg italic uppercase text-dark">{titulo}</h2>
          {ayuda && <p className="-mt-2 text-xs text-gray">{ayuda}</p>}
          {children}
          {estado.error && (
            <p role="alert" className="text-sm font-semibold text-secondary">
              {estado.error}
            </p>
          )}
          <div className="mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => dialogRef.current?.close()}
              className="rounded border border-gray px-4 py-2 text-sm font-semibold text-dark"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={pendiente || envioDeshabilitado}
              className={CLASE_PRIMARIO}
            >
              {pendiente ? etiquetaPendiente : etiquetaEnvio}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

/** Clase del botón "Editar" de una fila: discreto, no compite con el alta. */
export const BOTON_FILA =
  "rounded border border-gray/40 px-2 py-1 text-xs font-semibold text-dark hover:bg-cream";

/**
 * `defaultValue` de un `<input>` no admite `null`: React lo lee como "campo
 * no controlado" y avisa por consola. Un opcional vacío de la API llega
 * `null`, así que este paso está en cada formulario de edición del ERP —
 * escrito inline eran dos ramas por campo, y un formulario de ocho campos
 * no pasaba el límite de complejidad del lint por puro ruido de sintaxis.
 */
export function valor(v: string | number | null | undefined): string | number {
  return v ?? "";
}
