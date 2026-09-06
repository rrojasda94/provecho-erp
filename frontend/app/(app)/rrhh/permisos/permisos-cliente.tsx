"use client";

import { useState, useTransition } from "react";

import { Insignia } from "@/components/estado/insignia";
import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { Combobox } from "@/components/ui/combobox";
import { tienePermiso } from "@/lib/permisos";

import { aprobarPermisoAction, crearPermisoAction, rechazarPermisoAction } from "./actions";

export type Solicitud = {
  id: string;
  trabajador_id: string;
  tipo: string;
  fecha_desde: string;
  fecha_hasta: string | null;
  estado: string;
  aprobador_id: string | null;
};

export type TrabajadorRef = { id: string; nombre: string; estado: string };

/** Los tipos que el negocio reconoce. Campo cerrado y no libre: «vacaciones»
 * y «vacacion» son dos permisos distintos para cualquier reporte que después
 * agrupe, y nadie se entera hasta que el conteo no cuadra. */
const TIPOS = [
  "vacaciones",
  "licencia_con_goce",
  "licencia_sin_goce",
  "descanso_medico",
  "permiso_personal",
  "duelo",
];

const APROBAR = "rrhh.permiso_aprobar";
const SOLICITAR = "rrhh.permiso_solicitar";

function DialogoNuevoPermiso({ trabajadores }: { trabajadores: TrabajadorRef[] }) {
  const [trabajador, setTrabajador] = useState("");
  return (
    <DialogoFormulario
      titulo="Nueva solicitud de permiso"
      disparador="+ Nuevo permiso"
      etiquetaEnvio="Registrar"
      etiquetaPendiente="Registrando..."
      accion={crearPermisoAction}
      ayuda="Queda pendiente hasta que alguien con permiso de aprobación la resuelva. Quien la carga no la aprueba."
      alAbrir={() => setTrabajador("")}
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Trabajador
        <Combobox
          name="trabajador_id"
          etiqueta="Trabajador"
          requerido
          marcador="Elegir trabajador..."
          value={trabajador}
          alCambiar={(v) => setTrabajador(v ?? "")}
          opciones={trabajadores
            .filter((t) => t.estado !== "cesado")
            .map((t) => ({ valor: t.id, etiqueta: t.nombre }))}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Tipo
        <select name="tipo" defaultValue={TIPOS[0]}>
          {TIPOS.map((t) => (
            <option key={t} value={t}>
              {t.replaceAll("_", " ")}
            </option>
          ))}
        </select>
      </label>
      <div className="flex gap-4">
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Desde
          <input name="fecha_desde" type="date" required />
        </label>
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Hasta
          <input name="fecha_hasta" type="date" />
          <span className="text-xs font-normal text-gray">Vacío = un solo día</span>
        </label>
      </div>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Motivo
        <input name="motivo" maxLength={255} placeholder="Opcional" />
      </label>
    </DialogoFormulario>
  );
}

/** Aprobar y rechazar muestran su error debajo: la acción devuelve el motivo
 * —solapamiento con otro permiso, trabajador cesado— y descartarlo dejaría la
 * fila igual que si no hubiera pasado nada. */
function Decision({ solicitud }: { solicitud: Solicitud }) {
  const [pendiente, startTransition] = useTransition();
  const [error, setError] = useState("");

  if (solicitud.estado !== "pendiente") {
    return (
      <Insignia tono={solicitud.estado === "aprobado" ? "exito" : "neutro"}>
        {solicitud.estado}
      </Insignia>
    );
  }
  const decidir = (accion: (id: string) => Promise<{ error: string }>) =>
    startTransition(async () => setError((await accion(solicitud.id)).error));

  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-center gap-3">
        <button
          type="button"
          disabled={pendiente}
          onClick={() => decidir(aprobarPermisoAction)}
          className="text-xs font-bold text-primary hover:underline"
        >
          {pendiente ? "..." : "Aprobar"}
        </button>
        <button
          type="button"
          disabled={pendiente}
          onClick={() => decidir(rechazarPermisoAction)}
          className="text-xs font-semibold text-secondary hover:underline"
        >
          Rechazar
        </button>
      </div>
      {error && <span className="text-xs text-secondary">{error}</span>}
    </div>
  );
}

export function PermisosCliente({
  solicitudes,
  trabajadores,
  permisos,
  soloPendientes,
}: {
  solicitudes: Solicitud[];
  trabajadores: TrabajadorRef[];
  permisos: string[];
  soloPendientes: boolean;
}) {
  const nombre = new Map(trabajadores.map((t) => [t.id, t.nombre] as const));
  const puedeAprobar = tienePermiso(permisos, APROBAR);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4">
        <h1 className="font-heading text-xl text-dark">Permisos</h1>
        {tienePermiso(permisos, SOLICITAR) && (
          <DialogoNuevoPermiso trabajadores={trabajadores} />
        )}
      </div>
      <p className="text-sm text-gray">
        Vacaciones, licencias y descansos médicos (RN-RRHH-005). La bandeja abre
        en las pendientes: la que envejece sin respuesta es la que hay que
        atender, y el trabajador se entera de la decisión por su encargado, no
        por el sistema.
      </p>

      <a
        href={soloPendientes ? "/rrhh/permisos?estado=" : "/rrhh/permisos"}
        className="self-start text-sm font-semibold text-primary hover:underline"
      >
        {soloPendientes ? "Ver todas" : "Ver solo pendientes"}
      </a>

      {solicitudes.length === 0 ? (
        <p className="rounded bg-cream px-3 py-2 text-sm text-gray">
          {soloPendientes
            ? "No hay solicitudes pendientes."
            : "No hay solicitudes registradas."}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[42rem] border-collapse text-sm">
            <thead>
              <tr className="border-b border-gray/30 text-left text-xs uppercase text-gray">
                <th className="py-2 pr-4 font-semibold">Trabajador</th>
                <th className="py-2 pr-4 font-semibold">Tipo</th>
                <th className="py-2 pr-4 font-semibold">Desde</th>
                <th className="py-2 pr-4 font-semibold">Hasta</th>
                <th className="py-2 font-semibold">Estado</th>
              </tr>
            </thead>
            <tbody>
              {solicitudes.map((s) => (
                <tr key={s.id} className="border-b border-gray/15">
                  <td className="py-2 pr-4 font-semibold text-dark">
                    {nombre.get(s.trabajador_id) ?? "trabajador"}
                  </td>
                  <td className="py-2 pr-4">{s.tipo.replaceAll("_", " ")}</td>
                  <td className="py-2 pr-4 cifra">{s.fecha_desde}</td>
                  <td className="py-2 pr-4 cifra">{s.fecha_hasta ?? "—"}</td>
                  <td className="py-2">
                    {puedeAprobar ? (
                      <Decision solicitud={s} />
                    ) : (
                      <Insignia
                        tono={
                          s.estado === "aprobado"
                            ? "exito"
                            : s.estado === "pendiente"
                              ? "alerta"
                              : "neutro"
                        }
                      >
                        {s.estado}
                      </Insignia>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
