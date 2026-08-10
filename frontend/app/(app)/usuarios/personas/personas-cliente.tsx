"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import {
  BOTON_FILA,
  DialogoFormulario,
  valor,
} from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";

import { crearPersonaAction, editarPersonaAction } from "./actions";

export type Persona = {
  id: string;
  nombres: string;
  apellidos: string;
  tipo_documento: string;
  numero_documento: string;
  fecha_nacimiento: string | null;
  domicilio: string | null;
  telefono: string | null;
  email: string | null;
  version: number;
  anonimizado_at: string | null;
};

const TIPOS_DOCUMENTO = ["dni", "ce", "pasaporte", "ruc"] as const;

/** Los mismos campos en el alta y en la corrección: una persona es una
 * persona, y tener dos formularios distintos para la misma ficha es cómo
 * termina habiendo un campo que solo se puede cargar al crearla. */
function CamposPersona({ persona }: { persona?: Persona }) {
  const p: Partial<Persona> = persona ?? {};
  return (
    <>
      <div className="flex gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Nombres
          <input name="nombres" required maxLength={100} defaultValue={valor(p.nombres)} />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Apellidos
          <input name="apellidos" required maxLength={100} defaultValue={valor(p.apellidos)} />
        </label>
      </div>
      <div className="flex gap-2">
        <label className="flex w-32 flex-col gap-1 text-sm font-semibold">
          Tipo doc.
          <select name="tipo_documento" defaultValue={p.tipo_documento ?? "dni"}>
            {TIPOS_DOCUMENTO.map((t) => (
              <option key={t} value={t}>
                {t.toUpperCase()}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Número de documento
          <input
            name="numero_documento"
            required
            maxLength={20}
            defaultValue={valor(p.numero_documento)}
          />
        </label>
      </div>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Fecha de nacimiento
        <input name="fecha_nacimiento" type="date" defaultValue={valor(p.fecha_nacimiento)} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Domicilio
        <input name="domicilio" maxLength={255} defaultValue={valor(p.domicilio)} />
      </label>
      <div className="flex gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Teléfono
          <input name="telefono" maxLength={20} defaultValue={valor(p.telefono)} />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Email
          <input name="email" type="email" defaultValue={valor(p.email)} />
        </label>
      </div>
    </>
  );
}

function DialogoNuevaPersona() {
  return (
    <DialogoFormulario
      titulo="Nueva persona"
      disparador="+ Nueva persona"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearPersonaAction}
      ayuda="La ficha única de alguien. Trabajador, proveedor natural y cliente apuntan acá en vez de repetir su nombre (RN-GEN-007)."
    >
      <CamposPersona />
    </DialogoFormulario>
  );
}

/** Rectificación (derecho ARCO, Ley 29733).
 *
 * La `version` viaja en un input oculto: si otro administrador guardó
 * primero, la API responde 409 en vez de dejar que el segundo pise al
 * primero sin que nadie se entere. */
function DialogoEditarPersona({ persona }: { persona: Persona }) {
  return (
    <DialogoFormulario
      titulo="Editar persona"
      disparador="Editar"
      claseDisparador={BOTON_FILA}
      accion={editarPersonaAction}
      ayuda="Esta ficha la comparten trabajador, proveedor natural y cliente: corregir acá los corrige a todos."
    >
      <input type="hidden" name="id" value={persona.id} />
      <input type="hidden" name="version" value={persona.version} />
      <CamposPersona persona={persona} />
    </DialogoFormulario>
  );
}

export function PersonasCliente({ personas }: { personas: Persona[] }) {
  const columnas: ColumnDef<Persona>[] = useMemo(
    () => [
      {
        id: "nombre",
        header: "Nombre",
        accessorFn: (p) => `${p.apellidos}, ${p.nombres}`,
      },
      {
        id: "documento",
        header: "Documento",
        accessorFn: (p) => `${p.tipo_documento.toUpperCase()} ${p.numero_documento}`,
      },
      { accessorKey: "telefono", header: "Teléfono" },
      { accessorKey: "email", header: "Email" },
      { accessorKey: "domicilio", header: "Domicilio" },
      {
        id: "acciones",
        header: "",
        // Una ficha anonimizada no admite rectificación (la API responde 409):
        // ofrecer el botón sería prometer algo que la ley ya cerró.
        cell: ({ row }) =>
          row.original.anonimizado_at ? (
            <span className="text-xs text-gray">Anonimizada</span>
          ) : (
            <DialogoEditarPersona persona={row.original} />
          ),
      },
    ],
    [],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl italic uppercase text-dark">Personas</h1>
        <DialogoNuevaPersona />
      </div>
      <p className="text-sm text-gray">
        La ficha única de cada persona del ERP (RN-GEN-007): trabajador, proveedor natural
        y cliente apuntan a la misma en vez de repetir su nombre, así que corregir un
        domicilio acá lo corrige en todas. Es también donde se ejerce el derecho de
        <strong> rectificación</strong> de la Ley 29733.
      </p>
      <TablaDatos
        columnas={columnas}
        datos={personas}
        placeholderBusqueda="Buscar por nombre o documento..."
      />
    </div>
  );
}
