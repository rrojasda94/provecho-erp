"use client";

import { useActionState, useMemo, useState, useTransition } from "react";

import { DialogoFormulario, ESTADO_INICIAL } from "@/components/formulario/dialogo-formulario";
import { Combobox } from "@/components/ui/combobox";

import { asignarPermisoAction, crearRolAction, quitarPermisoAction } from "./actions";

export type Rol = { id: string; nombre: string; descripcion: string | null };
export type Permiso = {
  id: string;
  codigo: string;
  descripcion: string | null;
  restricciones: Record<string, unknown> | null;
};

/** Prefijo del código (`sales.cobrar` → `sales`): el catálogo pasa los 90
 * permisos y sin agrupar es una lista imposible de leer. */
function modulo(codigo: string): string {
  return codigo.includes(".") ? codigo.split(".")[0] : "general";
}

function DialogoNuevoRol() {
  return (
    <DialogoFormulario
      titulo="Nuevo rol"
      disparador="+ Nuevo rol"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearRolAction}
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input name="nombre" required maxLength={50} placeholder="ej. supervisor_turno" />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Descripción
        <input name="descripcion" maxLength={200} placeholder="Qué hace quien lo tiene" />
      </label>
    </DialogoFormulario>
  );
}

function PermisosDelRol({
  rol,
  permisos,
  asignados,
}: {
  rol: Rol;
  permisos: Permiso[];
  asignados: Permiso[];
}) {
  const [estado, formAction] = useActionState(asignarPermisoAction, ESTADO_INICIAL);
  const [pendiente, startTransition] = useTransition();
  const disponibles = useMemo(
    () => permisos.filter((p) => !asignados.some((a) => a.id === p.id)),
    [permisos, asignados],
  );
  const porModulo = useMemo(() => {
    const mapa = new Map<string, Permiso[]>();
    for (const p of disponibles) {
      const clave = modulo(p.codigo);
      mapa.set(clave, [...(mapa.get(clave) ?? []), p]);
    }
    return [...mapa.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [disponibles]);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-1.5">
        {asignados.length === 0 && (
          <span className="text-sm text-gray">
            Sin permisos: quien tenga este rol entra y no ve nada.
          </span>
        )}
        {asignados.map((p) => (
          <span
            key={p.id}
            title={p.descripcion ?? undefined}
            className="flex items-center gap-1 rounded-full bg-cream px-2 py-0.5 text-xs font-semibold text-dark"
          >
            {p.codigo}
            <button
              type="button"
              aria-label={`Quitar ${p.codigo} de ${rol.nombre}`}
              disabled={pendiente}
              onClick={() => startTransition(() => void quitarPermisoAction(rol.id, p.id))}
              className="text-gray hover:text-secondary"
            >
              ×
            </button>
          </span>
        ))}
      </div>
      {disponibles.length > 0 && (
        <form action={formAction} className="flex items-center gap-2">
          <input type="hidden" name="rol_id" value={rol.id} />
          <Combobox
            name="permiso_id"
            etiqueta={`Agregar permiso a ${rol.nombre}`}
            marcador="Elegir permiso..."
            className="max-w-xs"
            opciones={porModulo.flatMap(([mod, lista]) =>
              lista.map((p) => ({ valor: p.id, etiqueta: p.codigo, pista: mod })),
            )}
          />
          <button type="submit" className="text-xs font-bold text-primary hover:underline">
            Agregar
          </button>
          {estado.error && <span className="text-xs text-secondary">{estado.error}</span>}
        </form>
      )}
    </div>
  );
}

export function RolesCliente({
  roles,
  permisos,
  permisosPorRol,
}: {
  roles: Rol[];
  permisos: Permiso[];
  permisosPorRol: Record<string, Permiso[]>;
}) {
  // Acordeón en vez de tabla: cada rol tiene decenas de permisos y una
  // celda con 30 etiquetas no se lee. Se abre el que se está tocando.
  const [abierto, setAbierto] = useState<string | null>(null);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl text-dark">Roles</h1>
        <DialogoNuevoRol />
      </div>
      <p className="text-sm text-gray">
        Un rol es un conjunto de permisos. El ERP deniega por defecto: lo que no está
        acá, no se puede hacer.
      </p>
      <ul className="flex flex-col gap-2">
        {roles.map((rol) => {
          const asignados = permisosPorRol[rol.id] ?? [];
          const activo = abierto === rol.id;
          return (
            <li key={rol.id} className="rounded border border-gray/20 bg-white">
              <button
                type="button"
                onClick={() => setAbierto(activo ? null : rol.id)}
                aria-expanded={activo}
                className="flex w-full items-center justify-between px-4 py-3 text-left"
              >
                <span className="flex flex-col">
                  <span className="font-semibold text-dark">{rol.nombre}</span>
                  {rol.descripcion && (
                    <span className="text-xs text-gray">{rol.descripcion}</span>
                  )}
                </span>
                <span className="text-xs text-gray">
                  {asignados.length} permiso{asignados.length === 1 ? "" : "s"} {activo ? "▲" : "▼"}
                </span>
              </button>
              {activo && (
                <div className="border-t border-gray/20 px-4 py-3">
                  <PermisosDelRol rol={rol} permisos={permisos} asignados={asignados} />
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
