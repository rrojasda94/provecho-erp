"use client";

import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { tienePermiso } from "@/lib/permisos";

import {
  emitirAmonestacionAction,
  emitirCertificadoAction,
  emitirMemorandumAction,
} from "./actions";

const DISCIPLINA = "rrhh.disciplina_gestionar";
const GESTIONAR = "rrhh.trabajador_gestionar";

/** La escala disciplinaria, de menor a mayor (RN-RRHH-002). Cerrada porque el
 * tipo decide el peso de la sanción en un despido posterior: «llamada» y
 * «llamado de atención» tecleados a mano son dos historiales distintos del
 * mismo trabajador. */
const TIPOS_AMONESTACION = ["verbal", "escrita", "suspension"];

export function AccionesLegajo({
  trabajadorId,
  hoy,
  permisos,
}: {
  trabajadorId: string;
  /** La fecha la pone el servidor que renderiza, no el navegador: la zona del
   * negocio es la que manda (ADR-084). */
  hoy: string;
  permisos: string[];
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {tienePermiso(permisos, DISCIPLINA) && (
        <>
          <DialogoFormulario
            titulo="Amonestar"
            disparador="+ Amonestación"
            etiquetaEnvio="Emitir"
            etiquetaPendiente="Emitiendo..."
            accion={emitirAmonestacionAction}
            ayuda="Queda en el legajo y es la prueba de que se avisó antes. La firma quien la emite, que sale de tu sesión."
          >
            <input type="hidden" name="trabajador_id" value={trabajadorId} />
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Tipo
              <select name="tipo" defaultValue={TIPOS_AMONESTACION[0]}>
                {TIPOS_AMONESTACION.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Falta
              <textarea name="falta" required rows={3} placeholder="Qué pasó, con fecha y lugar" />
            </label>
            <div className="flex gap-4">
              <label className="flex flex-col gap-1 text-sm font-semibold">
                Fecha del hecho
                <input name="fecha_hecho" type="date" required defaultValue={hoy} />
              </label>
              <label className="flex flex-col gap-1 text-sm font-semibold">
                Fecha de emisión
                <input name="fecha_emision" type="date" required defaultValue={hoy} />
              </label>
            </div>
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Días para el descargo
              <input name="descargo_plazo_dias" type="number" min="1" max="30" placeholder="Opcional" />
              <span className="text-xs font-normal text-gray">
                El plazo que se le da para responder. Sin descargo, la sanción es
                más fácil de discutir.
              </span>
            </label>
          </DialogoFormulario>

          <DialogoFormulario
            titulo="Memorándum"
            disparador="+ Memorándum"
            etiquetaEnvio="Emitir"
            etiquetaPendiente="Emitiendo..."
            accion={emitirMemorandumAction}
            ayuda="Comunicación formal. No es una sanción: sirve para instruir o dejar constancia."
          >
            <input type="hidden" name="trabajador_id" value={trabajadorId} />
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Asunto
              <input name="asunto" required maxLength={200} />
            </label>
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Cuerpo
              <textarea name="cuerpo" required rows={5} />
            </label>
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Fecha
              <input name="fecha" type="date" required defaultValue={hoy} />
            </label>
          </DialogoFormulario>
        </>
      )}

      {tienePermiso(permisos, GESTIONAR) && (
        <DialogoFormulario
          titulo="Certificado de trabajo"
          disparador="+ Certificado"
          etiquetaEnvio="Emitir"
          etiquetaPendiente="Emitiendo..."
          accion={emitirCertificadoAction}
          ayuda="El tiempo de servicios y si sale dentro del plazo de ley los calcula el sistema: son la razón de ser del documento y no se teclean."
        >
          <input type="hidden" name="trabajador_id" value={trabajadorId} />
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Cargos ocupados
            <input name="cargos" required maxLength={255} placeholder="Cajero, luego encargado de turno" />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Fecha de emisión
            <input name="fecha_emision" type="date" required defaultValue={hoy} />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Conducta y desempeño
            <textarea name="conducta_desempeno" rows={3} placeholder="Opcional" />
          </label>
        </DialogoFormulario>
      )}
    </div>
  );
}
