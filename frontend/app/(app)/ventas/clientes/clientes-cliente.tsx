"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useMemo } from "react";

import { BuscarDocumento } from "@/components/consulta/buscar-documento";
import { BOTON_FILA, DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";

import { completarDocumentoAction, editarClienteAction } from "./actions";

export type Cliente = {
  id: string;
  tipo: string;
  nombre: string;
  telefono: string | null;
  numero_documento: string | null;
  direccion: string | null;
  identificado: boolean;
  persona_id: string | null;
};

/** Un cliente jurídico guarda lo suyo: razón social, RUC y contacto. */
function DialogoEditarJuridico({
  cliente,
  permisos,
}: {
  cliente: Cliente;
  permisos: string[];
}) {
  return (
    <DialogoFormulario
      titulo="Editar cliente"
      disparador="Editar"
      claseDisparador={BOTON_FILA}
      accion={editarClienteAction}
      ayuda="SUNAT manda sobre la razón social tecleada cuando el RUC existe."
    >
      <input type="hidden" name="id" value={cliente.id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Razón social
        <input name="razon_social" required maxLength={255} defaultValue={cliente.nombre} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        RUC
        <input
          name="ruc"
          required
          minLength={11}
          maxLength={11}
          inputMode="numeric"
          defaultValue={cliente.numero_documento ?? ""}
        />
      </label>
      {/* La ayuda del diálogo dice que SUNAT manda sobre la razón social
          tecleada, y hasta ahora no había forma de verla antes de guardar:
          se descubría al grabar que el sistema escribió otra. Solo se
          prellena la razón social — `contacto` es el teléfono o el correo de
          quien coordina, no el domicilio fiscal, y traerlo de SUNAT
          reemplazaría un dato real por otro. */}
      <BuscarDocumento
        permisos={permisos}
        tipo="ruc"
        campo="ruc"
        rellena={{ razon_social: "razon_social" }}
      />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Contacto
        <input
          name="contacto"
          maxLength={255}
          defaultValue={cliente.direccion ?? ""}
          placeholder="Dirección, correo o teléfono de quien coordina"
        />
      </label>
    </DialogoFormulario>
  );
}

/** Completar el documento de un natural registrado solo por teléfono.
 *
 * Es el camino normal y no una excepción: el cliente da su DNI cuando le
 * conviene —una factura, entrar al programa de puntos— y desde ese momento
 * cuenta como identificado (RN-PTS-002).
 *
 * **Sin botón de búsqueda, a propósito**: acá no hay nada que prellenar. El
 * nombre de un cliente natural vive en su `persona` (RN-GEN-007) y este
 * endpoint no lo toca —solo le cuelga el documento—, así que una consulta
 * traería un dato que ningún campo de este formulario puede recibir. El
 * botón sí está donde ese nombre se edita: Usuarios → Personas. */
function DialogoCompletarDocumento({ cliente }: { cliente: Cliente }) {
  return (
    <DialogoFormulario
      titulo="Registrar documento"
      disparador="Documento"
      claseDisparador={BOTON_FILA}
      accion={completarDocumentoAction}
      ayuda="Sin documento el cliente existe y compra, pero queda fuera de las promociones que lo exigen (RN-PTS-002)."
    >
      <input type="hidden" name="id" value={cliente.id} />
      <div className="flex gap-2">
        <label className="flex w-32 flex-col gap-1 text-sm font-semibold">
          Tipo
          <select name="tipo_documento" defaultValue="dni">
            <option value="dni">DNI</option>
            <option value="ce">CE</option>
            <option value="pasaporte">Pasaporte</option>
          </select>
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Número
          <input name="numero_documento" required maxLength={11} inputMode="numeric" />
        </label>
      </div>
    </DialogoFormulario>
  );
}

function AccionesCliente({ cliente, permisos }: { cliente: Cliente; permisos: string[] }) {
  if (cliente.tipo === "juridico")
    return <DialogoEditarJuridico cliente={cliente} permisos={permisos} />;

  return (
    <div className="flex items-center gap-1.5">
      {!cliente.identificado && <DialogoCompletarDocumento cliente={cliente} />}
      {cliente.persona_id && (
        // El nombre, el teléfono y la dirección de un natural viven en su
        // persona (RN-GEN-007). Ofrecerlos acá sería una segunda fuente para
        // el mismo dato; el enlace lleva a donde de verdad se corrigen.
        <Link
          href="/usuarios/personas"
          className={`${BOTON_FILA} inline-block`}
          title="Sus datos viven en la ficha de persona"
        >
          Ver ficha
        </Link>
      )}
    </div>
  );
}

export function ClientesCliente({
  clientes,
  permisos,
}: {
  clientes: Cliente[];
  permisos: string[];
}) {
  const columnas: ColumnDef<Cliente>[] = useMemo(
    () => [
      { accessorKey: "nombre", header: "Cliente" },
      { accessorKey: "tipo", header: "Tipo" },
      {
        id: "documento",
        header: "Documento",
        accessorFn: (c) => c.numero_documento ?? "—",
      },
      { accessorKey: "telefono", header: "Teléfono" },
      { accessorKey: "direccion", header: "Dirección / contacto" },
      {
        accessorKey: "identificado",
        header: "Identificado",
        cell: ({ getValue }) => (
          <span
            className={
              getValue<boolean>()
                ? "rounded-full bg-accent/30 px-2 py-0.5 text-xs font-semibold text-dark"
                : "rounded-full bg-gray/20 px-2 py-0.5 text-xs font-semibold text-gray"
            }
          >
            {getValue<boolean>() ? "Sí" : "No"}
          </span>
        ),
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => <AccionesCliente cliente={row.original} permisos={permisos} />,
      },
    ],
    [permisos],
  );

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-heading text-xl italic uppercase text-dark">Clientes</h1>
      <p className="text-sm text-gray">
        El padrón del grupo (RN-PTS-001): un cliente registrado en una sucursal es el mismo
        en todas. El alta ocurre en caja —registrar es opcional, vender anónimo siempre es
        válido (RN-PER-005)—; acá se corrige lo que se tecleó mal. De un cliente{" "}
        <strong>natural</strong> solo se completa el documento: su nombre, teléfono y
        dirección viven en su ficha de persona, fuente única (RN-GEN-007).
      </p>
      <TablaDatos
        columnas={columnas}
        datos={clientes}
        placeholderBusqueda="Buscar por nombre, documento o teléfono..."
      />
    </div>
  );
}
