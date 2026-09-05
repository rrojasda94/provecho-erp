"use client";

import { useState, useTransition } from "react";

import { InsigniaActiva } from "@/components/estado/insignia";
import { BOTON_FILA, DialogoFormulario, valor } from "@/components/formulario/dialogo-formulario";
import { Combobox } from "@/components/ui/combobox";
import { tienePermiso } from "@/lib/permisos";

import {
  agregarMiembroAction,
  crearAreaAction,
  editarAreaAction,
  quitarMiembroAction,
} from "./actions";

export type Area = { id: string; codigo: string; nombre: string; activa: boolean };
export type Miembro = {
  id: string;
  area_id: string;
  rol_id: string | null;
  usuario_id: string | null;
  sucursal_id: string | null;
};
export type Opcion = { id: string; nombre: string };

const ADMINISTRAR = "reports.administrar";

function DialogoNuevaArea() {
  return (
    <DialogoFormulario
      titulo="Nueva área"
      disparador="+ Nueva área"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearAreaAction}
      ayuda="Un área es a quién le llega un reporte. El código lo nombran las reglas de distribución y no se puede cambiar después."
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Código
        <input
          name="codigo"
          required
          maxLength={30}
          pattern="[a-z][a-z0-9_]*"
          placeholder="operaciones"
        />
        <span className="text-xs font-normal text-gray">
          Minúsculas, sin espacios. Se escribe una vez.
        </span>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input name="nombre" required maxLength={100} placeholder="Operaciones" />
      </label>
    </DialogoFormulario>
  );
}

function DialogoEditarArea({ area }: { area: Area }) {
  return (
    <DialogoFormulario
      titulo={`Editar ${area.codigo}`}
      disparador="Editar"
      claseDisparador={BOTON_FILA}
      accion={editarAreaAction}
      ayuda="El código no se edita: las reglas de distribución lo nombran. Un área inactiva deja de recibir reportes nuevos y conserva los que ya recibió."
    >
      <input type="hidden" name="id" value={area.id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input name="nombre" required maxLength={100} defaultValue={valor(area.nombre)} />
      </label>
      <label className="flex items-center gap-2 text-sm font-semibold">
        <input type="checkbox" name="activa" defaultChecked={area.activa} />
        Activa
      </label>
    </DialogoFormulario>
  );
}

function DialogoAgregarMiembro({
  area,
  roles,
  usuarios,
  sucursales,
}: {
  area: Area;
  roles: Opcion[];
  usuarios: Opcion[];
  sucursales: Opcion[];
}) {
  const [rol, setRol] = useState("");
  const [usuario, setUsuario] = useState("");
  const [sucursal, setSucursal] = useState("");

  return (
    <DialogoFormulario
      titulo={`Sumar a ${area.nombre}`}
      disparador="+ Miembro"
      claseDisparador={BOTON_FILA}
      etiquetaEnvio="Agregar"
      etiquetaPendiente="Agregando..."
      accion={agregarMiembroAction}
      ayuda="Por rol es «quien ocupe ese puesto» y sobrevive al cambio de personas; por persona es esa persona. Una de las dos, no las dos."
      alAbrir={() => {
        setRol("");
        setUsuario("");
        setSucursal("");
      }}
    >
      <input type="hidden" name="area_id" value={area.id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Rol
        <Combobox
          name="rol_id"
          etiqueta="Rol"
          marcador="Ningún rol"
          value={rol}
          alCambiar={(v) => {
            setRol(v ?? "");
            if (v) setUsuario("");
          }}
          opciones={roles.map((r) => ({ valor: r.id, etiqueta: r.nombre }))}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        O una persona
        <Combobox
          name="usuario_id"
          etiqueta="Persona"
          marcador="Ninguna persona"
          value={usuario}
          alCambiar={(v) => {
            setUsuario(v ?? "");
            if (v) setRol("");
          }}
          opciones={usuarios.map((u) => ({ valor: u.id, etiqueta: u.nombre }))}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Solo para una sucursal
        <Combobox
          name="sucursal_id"
          etiqueta="Sucursal"
          marcador="Todas las sucursales"
          value={sucursal}
          alCambiar={(v) => setSucursal(v ?? "")}
          opciones={sucursales.map((s) => ({ valor: s.id, etiqueta: s.nombre }))}
        />
        <span className="text-xs font-normal text-gray">
          Vacío = recibe lo de todas.
        </span>
      </label>
    </DialogoFormulario>
  );
}

function BotonQuitar({ areaId, miembroId }: { areaId: string; miembroId: string }) {
  const [pendiente, startTransition] = useTransition();
  const [error, setError] = useState("");
  return (
    <span className="flex flex-col">
      <button
        type="button"
        disabled={pendiente}
        onClick={() =>
          startTransition(async () => setError((await quitarMiembroAction(areaId, miembroId)).error))
        }
        className="text-xs font-semibold text-secondary hover:underline"
      >
        {pendiente ? "Quitando..." : "Quitar"}
      </button>
      {error && <span className="text-xs text-secondary">{error}</span>}
    </span>
  );
}

export function AreasCliente({
  areas,
  miembros,
  roles,
  usuarios,
  sucursales,
  permisos,
}: {
  areas: Area[];
  miembros: Miembro[];
  roles: Opcion[];
  usuarios: Opcion[];
  sucursales: Opcion[];
  permisos: string[];
}) {
  const puedeAdministrar = tienePermiso(permisos, ADMINISTRAR);
  const nombre = (lista: Opcion[], id: string | null) =>
    id ? (lista.find((o) => o.id === id)?.nombre ?? id.slice(0, 8)) : null;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4">
        <h1 className="font-heading text-xl text-dark">Áreas de reportes</h1>
        {puedeAdministrar && <DialogoNuevaArea />}
      </div>
      <p className="text-sm text-gray">
        A quién le llega cada reporte. Un área agrupa roles y personas; las reglas
        de distribución la nombran por su código. Sin miembros, un área recibe y no
        se lo pasa a nadie — es la mitad de una fuga.
      </p>

      {areas.length === 0 ? (
        <p className="rounded bg-cream px-3 py-2 text-sm text-gray">
          Sin áreas configuradas: hoy ningún reporte se distribuye por área.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {areas.map((a) => {
            const suyos = miembros.filter((m) => m.area_id === a.id);
            return (
              <article key={a.id} className="flex flex-col gap-2 rounded border border-gray/30 p-4">
                <header className="flex flex-wrap items-center gap-2">
                  <h2 className="font-heading text-base text-dark">{a.nombre}</h2>
                  <code className="text-xs text-gray">{a.codigo}</code>
                  <InsigniaActiva activa={a.activa} />
                  <span className="ml-auto flex gap-2">
                    {puedeAdministrar && (
                      <>
                        <DialogoEditarArea area={a} />
                        <DialogoAgregarMiembro
                          area={a}
                          roles={roles}
                          usuarios={usuarios}
                          sucursales={sucursales}
                        />
                      </>
                    )}
                  </span>
                </header>
                {suyos.length === 0 ? (
                  <p className="text-sm text-secondary">
                    Sin miembros: lo que llegue acá no lo lee nadie.
                  </p>
                ) : (
                  <ul className="flex flex-col gap-1 text-sm">
                    {suyos.map((m) => (
                      <li key={m.id} className="flex flex-wrap items-center gap-3 border-b border-gray/15 py-1">
                        <span className="font-semibold text-dark">
                          {m.rol_id
                            ? `rol · ${nombre(roles, m.rol_id)}`
                            : `persona · ${nombre(usuarios, m.usuario_id)}`}
                        </span>
                        <span className="text-xs text-gray">
                          {m.sucursal_id
                            ? nombre(sucursales, m.sucursal_id)
                            : "todas las sucursales"}
                        </span>
                        {puedeAdministrar && <BotonQuitar areaId={a.id} miembroId={m.id} />}
                      </li>
                    ))}
                  </ul>
                )}
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
