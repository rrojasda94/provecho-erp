"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import {
  BOTON_FILA,
  DialogoFormulario,
  valor,
} from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";

import { guardarEmpresaAction, guardarGrupoAction } from "../actions";
import { CampoDireccion } from "@/components/direccion/campo-direccion";

export type Grupo = { id: string; nombre: string };
export type Empresa = {
  id: string;
  grupo_id: string;
  razon_social: string;
  ruc: string;
  domicilio_fiscal: string;
  ubicacion_place_id: string | null;
  ubicacion_lat: string | number | null;
  ubicacion_lng: string | number | null;
  ubicacion_plus_code: string | null;
  ubicacion_distrito: string | null;
  contacto: string | null;
  tipo: string;
  zona_tributaria: string;
  config_fiscal: { igv_por_defecto?: string } | null;
};

const TIPOS = ["operativa", "logistica", "servicios", "asesoria", "transporte"] as const;

function CamposEmpresa({ empresa }: { empresa?: Empresa }) {
  const e: Partial<Empresa> = empresa ?? {};
  return (
    <>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Razón social
        <input name="razon_social" required maxLength={255} defaultValue={valor(e.razon_social)} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        RUC
        <input
          name="ruc"
          required
          minLength={11}
          maxLength={11}
          inputMode="numeric"
          defaultValue={valor(e.ruc)}
        />
      </label>
      <CampoDireccion
        nombre="domicilio_fiscal"
        etiqueta="Domicilio fiscal"
        requerido
        defaultValue={e.domicilio_fiscal}
        ubicacion={empresa ?? null}
      />
      <div className="flex gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Tipo
          <select name="tipo" defaultValue={e.tipo ?? "operativa"}>
            {TIPOS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Zona tributaria
          <select name="zona_tributaria" defaultValue={e.zona_tributaria ?? "general"}>
            <option value="general">General</option>
            <option value="amazonia_ley27037">Amazonía (Ley 27037)</option>
          </select>
        </label>
      </div>
      {/* La exoneración de Amazonía depende de zona **y** actividad, así que
          la zona sola no alcanza para decidir el régimen. Este es el
          interruptor que usan el comprobante electrónico y el asiento
          contable; una operación suelta se marca al cobrar o al dar
          conformidad, no acá. */}
      <label className="flex flex-col gap-1 text-sm font-semibold">
        IGV por defecto
        <select name="igv_por_defecto" defaultValue={e.config_fiscal?.igv_por_defecto ?? ""}>
          <option value="">Según la zona tributaria</option>
          <option value="gravado">Gravado — las operaciones llevan IGV</option>
          <option value="exonerado">Exonerado — las operaciones no llevan IGV</option>
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Contacto
        <input name="contacto" maxLength={255} defaultValue={valor(e.contacto)} />
      </label>
    </>
  );
}

function DialogoNuevaEmpresa({ grupos }: { grupos: Grupo[] }) {
  return (
    <DialogoFormulario
      titulo="Nueva empresa"
      disparador="+ Nueva empresa"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={guardarEmpresaAction}
      envioDeshabilitado={grupos.length === 0}
      ayuda="Fundar una empresa está reservado a la cuenta de administración: un admin de empresa administra la suya, no funda otras."
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Grupo
        <select name="grupo_id" required defaultValue={grupos[0]?.id ?? ""}>
          {grupos.map((g) => (
            <option key={g.id} value={g.id}>
              {g.nombre}
            </option>
          ))}
        </select>
      </label>
      <CamposEmpresa />
    </DialogoFormulario>
  );
}

/** El grupo no se ofrece: una empresa no se muda de grupo, se funda en uno
 * — y la API tampoco lo acepta en el PATCH. */
function DialogoEditarEmpresa({ empresa }: { empresa: Empresa }) {
  return (
    <DialogoFormulario
      titulo="Editar empresa"
      disparador="Editar"
      claseDisparador={BOTON_FILA}
      accion={guardarEmpresaAction}
      ayuda="La zona tributaria decide si sus comprobantes salen exonerados de IGV: cambiarla afecta lo que se emita de acá en adelante."
    >
      <input type="hidden" name="id" value={empresa.id} />
      <CamposEmpresa empresa={empresa} />
    </DialogoFormulario>
  );
}

function DialogoEditarGrupo({ grupo }: { grupo: Grupo }) {
  return (
    <DialogoFormulario
      titulo="Editar grupo"
      disparador="Editar grupo"
      claseDisparador={BOTON_FILA}
      accion={guardarGrupoAction}
    >
      <input type="hidden" name="id" value={grupo.id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input name="nombre" required maxLength={100} defaultValue={grupo.nombre} />
      </label>
    </DialogoFormulario>
  );
}

export function EmpresasCliente({
  empresas,
  grupos,
  esSuperusuario,
}: {
  empresas: Empresa[];
  grupos: Grupo[];
  /** Fundar o renombrar un grupo lo reserva la API a la cuenta de
   * administración; ofrecerlo a un admin de empresa sería prometer un 403. */
  esSuperusuario: boolean;
}) {
  const nombreGrupo = useMemo(
    () => new Map(grupos.map((g) => [g.id, g.nombre])),
    [grupos],
  );

  const columnas: ColumnDef<Empresa>[] = useMemo(
    () => [
      { accessorKey: "razon_social", header: "Razón social" },
      { accessorKey: "ruc", header: "RUC" },
      { accessorKey: "tipo", header: "Tipo" },
      {
        id: "grupo",
        header: "Grupo",
        accessorFn: (e) => nombreGrupo.get(e.grupo_id) ?? "—",
      },
      {
        accessorKey: "zona_tributaria",
        header: "Zona tributaria",
        cell: ({ getValue }) =>
          getValue<string>() === "amazonia_ley27037" ? "Amazonía" : "General",
      },
      { accessorKey: "domicilio_fiscal", header: "Domicilio fiscal" },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => <DialogoEditarEmpresa empresa={row.original} />,
      },
    ],
    [nombreGrupo],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl italic uppercase text-dark">Empresas</h1>
        {esSuperusuario && <DialogoNuevaEmpresa grupos={grupos} />}
      </div>
      <p className="text-sm text-gray">
        Las personas jurídicas del grupo. Cada venta, compra y comprobante cuelga de una,
        así que no se dan de baja mientras tengan movimiento. Hasta ahora solo se
        administraban por API.
      </p>
      {esSuperusuario && grupos.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded border border-gray/20 bg-cream/40 px-3 py-2 text-sm">
          <span className="font-semibold text-dark">Grupo:</span>
          {grupos.map((g) => (
            <span key={g.id} className="flex items-center gap-2">
              {g.nombre}
              <DialogoEditarGrupo grupo={g} />
            </span>
          ))}
        </div>
      )}
      <TablaDatos columnas={columnas} datos={empresas} placeholderBusqueda="Buscar empresa..." />
    </div>
  );
}
