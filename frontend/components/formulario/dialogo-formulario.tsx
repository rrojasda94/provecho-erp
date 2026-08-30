"use client";

import { AlertCircle, HelpCircle, X } from "lucide-react";
import { startTransition, useActionState, useEffect, useRef } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ESTADO_INICIAL, type EstadoFormulario } from "@/lib/errores";

/**
 * Diálogo con formulario: el molde de toda alta y toda corrección del ERP.
 *
 * Existía copiado y pegado en siete pantallas —el mismo `<dialog>`, el mismo
 * `useActionState`, el mismo `role="alert"`, los mismos dos botones— y cada
 * pantalla nueva lo volvía a escribir. Con la edición encima habrían sido
 * veinte copias del mismo bloque; la que se olvidara de cerrar al `ok` o de
 * resetear al cancelar iba a ser un bug que nadie relaciona con las otras
 * diecinueve. Hoy lo usan diecisiete pantallas.
 *
 * Sigue siendo `<dialog>` nativo, no el `Dialog` de shadcn: el overlay, el
 * foco atrapado y el cierre con Esc ya vienen del navegador, y ninguna
 * pantalla pidió todavía algo que eso no cubra (ADR-013 dejó shadcn
 * instalado para cuando haga falta, no para usarlo por defecto). Lo que sí
 * cambió es cómo se ve: fondo desenfocado, panel que entra con escala,
 * encabezado y pie fijos con el cuerpo scrolleable — un formulario de doce
 * campos empujaba los botones fuera de la pantalla.
 */

// El tipo del estado vive en `lib/errores.ts` —donde se arma— y se
// reexporta acá porque diecisiete pantallas ya lo importan de este módulo.
export { ESTADO_INICIAL, type EstadoFormulario };

const CLASE_PRIMARIO =
  "inline-flex items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/85 disabled:pointer-events-none disabled:opacity-50";

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
  accion: (estado: EstadoFormulario, formData: FormData) => Promise<EstadoFormulario>;
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

  // El servidor dice qué campos rechazó (`errores[]` del 422) y el `campo`
  // que manda es el mismo `name` del input: se marca y se enfoca el primero,
  // que es lo que evita releer un formulario de doce campos para encontrar
  // cuál era.
  // ponytail: se marca por DOM y no con un slot de error en
  // `CampoFormulario` porque eso obligaría a pasar `nombre` en cada campo de
  // las diecisiete pantallas. Techo conocido: un campo anidado
  // (`valor.monto`) no tiene input con ese `name` y solo aparece en el texto
  // del pie. Si hace falta el mensaje bajo el input, ahí sí se agrega.
  useEffect(() => {
    const form = formRef.current;
    if (!form) return;
    form.querySelectorAll("[aria-invalid]").forEach((el) => el.removeAttribute("aria-invalid"));
    let primero: HTMLElement | null = null;
    for (const { campo } of estado.campos ?? []) {
      const control = form.querySelector<HTMLElement>(`[name="${CSS.escape(campo)}"]`);
      if (!control) continue;
      control.setAttribute("aria-invalid", "true");
      primero ??= control;
    }
    primero?.focus();
  }, [estado.campos]);

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
        className="dialogo w-full max-w-md rounded-xl border border-border bg-card p-0 text-card-foreground shadow-[var(--sombra-3)]"
        onClose={() => {
          // El reset va al cerrar, no al enviar (ver `onSubmit`).
          formRef.current?.reset();
          alCerrar?.();
        }}
      >
        {/* `onSubmit` y no `action={formAction}`: React 19 **resetea solo** el
            formulario cuando la acción va en el prop `action`, y lo hace
            también cuando la acción devolvió error. El efecto es que un
            rechazo del servidor borra todo lo tecleado — verificado en el
            navegador: corregir un RUC y errarle al plazo de crédito dejaba
            el diálogo abierto con el RUC viejo de vuelta. Recontar un
            formulario entero porque un campo estaba mal es la fricción que
            termina en un dato inventado (mismo criterio que el conteo de
            caja). Despachando la acción a mano dentro de una transición no
            hay reset automático y `pendiente` sigue funcionando igual. */}
        <form
          ref={formRef}
          aria-busy={pendiente}
          onSubmit={(e) => {
            e.preventDefault();
            const datos = new FormData(e.currentTarget);
            startTransition(() => formAction(datos));
          }}
          className="flex max-h-[85vh] flex-col"
        >
          <header className="flex items-start justify-between gap-4 border-b border-border px-5 py-3.5">
            <div>
              <h2 className="text-base leading-tight">{titulo}</h2>
              {ayuda && <p className="mt-1 text-xs text-muted-foreground">{ayuda}</p>}
            </div>
            <button
              type="button"
              aria-label="Cerrar"
              onClick={() => dialogRef.current?.close()}
              className="-mt-0.5 -mr-1 rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <X size={16} strokeWidth={2} aria-hidden />
            </button>
          </header>

          {/* El cuerpo scrollea; encabezado y pie no. Un formulario largo
              dejaba «Guardar» fuera de la pantalla y la única salida visible
              era Esc. */}
          <div className="flex flex-col gap-3.5 overflow-y-auto px-5 py-4">{children}</div>

          <footer className="flex items-center justify-between gap-3 border-t border-border px-5 py-3">
            {estado.error ? (
              <p
                role="alert"
                className="flex items-start gap-1.5 text-sm font-medium text-status-danger"
              >
                <AlertCircle size={14} strokeWidth={2.25} aria-hidden className="mt-0.5 shrink-0" />
                {estado.error}
              </p>
            ) : (
              <span />
            )}
            <div className="flex shrink-0 gap-2">
              <button
                type="button"
                onClick={() => dialogRef.current?.close()}
                className="rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-muted"
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
          </footer>
        </form>
      </dialog>
    </>
  );
}

/**
 * Campo de formulario con su etiqueta y, opcionalmente, su ayuda contextual.
 *
 * La ayuda por campo es un pendiente escrito desde julio
 * (docs/product/ui-ux.md): quien carga un proveedor no tiene por qué saber
 * que "condición de pago" se cuenta en días desde la recepción, y hoy esa
 * explicación no está en ningún lado de la pantalla. Va como tooltip sobre un
 * ícono y no como texto permanente para no engordar un formulario de doce
 * campos con doce párrafos.
 *
 * `pista` es lo contrario: formato esperado ("11 dígitos"), siempre visible,
 * porque saberlo DESPUÉS de que el servidor rechace es tarde.
 */
export function CampoFormulario({
  etiqueta,
  ayuda,
  pista,
  children,
}: {
  etiqueta: string;
  /** Qué significa este campo en el negocio. Aparece al apuntar el ícono. */
  ayuda?: string;
  /** Formato esperado. Siempre visible, bajo el campo. */
  pista?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="flex items-center gap-1 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
        {etiqueta}
        {ayuda && (
          <Tooltip>
            <TooltipTrigger
              render={
                <button
                  type="button"
                  aria-label={`Qué es ${etiqueta}`}
                  className="text-muted-foreground transition-colors hover:text-foreground"
                />
              }
            >
              <HelpCircle size={13} strokeWidth={2} aria-hidden />
            </TooltipTrigger>
            <TooltipContent>{ayuda}</TooltipContent>
          </Tooltip>
        )}
      </span>
      {children}
      {pista && <span className="text-xs text-muted-foreground">{pista}</span>}
    </label>
  );
}

/** Clase del botón "Editar" de una fila: discreto, no compite con el alta. */
export const BOTON_FILA =
  "inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs font-medium text-foreground transition-colors hover:bg-muted";

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
