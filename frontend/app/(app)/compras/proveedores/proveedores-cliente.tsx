"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";

import { BuscarDocumento } from "@/components/consulta/buscar-documento";
import { BOTON_FILA, DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { PersonaPicker } from "@/components/persona-picker/persona-picker";
import { TablaDatos } from "@/components/tabla/tabla-datos";

import { crearProveedorAction, editarProveedorAction } from "./actions";

export type Proveedor = {
  id: string;
  tipo: string;
  persona_id: string | null;
  razon_social: string | null;
  ruc: string | null;
  contacto: string | null;
  direccion: string | null;
  provincia: string | null;
  pais: string;
  plazo_dias_credito: number | null;
  formal: boolean;
  clasificacion: string;
  condicion_pago: string;
  activo: boolean;
};
export type Persona = { id: string; nombres: string; apellidos: string };

const CLASIFICACIONES = ["regular", "preferente"] as const;

/** Condición de pago + plazo: van juntos porque 'credito' sin plazo lo
 * rechaza el servidor (accounting no tendría vencimiento que calcular). */
function CamposCondicionPago({ proveedor }: { proveedor?: Proveedor }) {
  return (
    <>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Condición de pago
        <select name="condicion_pago" defaultValue={proveedor?.condicion_pago ?? "contado"}>
          <option value="contado">Contado</option>
          <option value="credito">Crédito</option>
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Plazo de crédito (días)
        <input
          name="plazo_dias_credito"
          type="number"
          min={1}
          defaultValue={proveedor?.plazo_dias_credito ?? ""}
          placeholder="Solo si es crédito"
        />
      </label>
    </>
  );
}

function DialogoNuevoProveedor({ permisos }: { permisos: string[] }) {
  const [tipo, setTipo] = useState<"juridico" | "natural">("juridico");

  return (
    <DialogoFormulario
      titulo="Nuevo proveedor"
      disparador="+ Nuevo proveedor"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearProveedorAction}
      alCerrar={() => setTipo("juridico")}
    >
      <div className="flex gap-4 text-sm font-semibold">
        <label className="flex items-center gap-1.5">
          <input
            type="radio"
            name="tipo"
            value="juridico"
            checked={tipo === "juridico"}
            onChange={() => setTipo("juridico")}
          />
          Jurídico (RUC)
        </label>
        <label className="flex items-center gap-1.5">
          <input
            type="radio"
            name="tipo"
            value="natural"
            checked={tipo === "natural"}
            onChange={() => setTipo("natural")}
          />
          Natural (persona)
        </label>
      </div>
      {tipo === "juridico" ? (
        <>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Razón social
            <input name="razon_social" required maxLength={255} />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            RUC
            <input name="ruc" required maxLength={11} minLength={11} inputMode="numeric" />
          </label>
          {/* El domicilio fiscal lo trae SUNAT junto con la razón social;
              sigue siendo editable porque el declarado no siempre es el
              almacén al que uno va a recoger. */}
          <BuscarDocumento
            permisos={permisos}
            tipo="ruc"
            campo="ruc"
            rellena={{
              razon_social: "razon_social",
              direccion: "direccion",
              provincia: "provincia",
            }}
          />
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Dirección
            <input name="direccion" maxLength={255} />
          </label>
          <div className="flex gap-2">
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              Provincia
              <input name="provincia" maxLength={100} />
            </label>
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              País
              <input name="pais" maxLength={60} defaultValue="PE" />
            </label>
          </div>
        </>
      ) : (
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Persona (debe existir de antes)
          <PersonaPicker name="persona_id" />
        </label>
      )}
      <CamposCondicionPago />
    </DialogoFormulario>
  );
}

/** Corrección de un proveedor ya dado de alta.
 *
 * El tipo no se ofrece: cambiarlo convertiría al proveedor en otro y dejaría
 * sus órdenes de compra apuntando a algo que ya no es. En uno natural
 * tampoco hay razón social ni RUC — esos datos viven en su persona
 * (RN-GEN-007) y se corrigen desde Usuarios → Personas. */
function DialogoEditarProveedor({
  proveedor,
  permisos,
}: {
  proveedor: Proveedor;
  permisos: string[];
}) {
  const esJuridico = proveedor.tipo === "juridico";

  return (
    <DialogoFormulario
      titulo="Editar proveedor"
      disparador="Editar"
      claseDisparador={BOTON_FILA}
      accion={editarProveedorAction}
      ayuda={
        esJuridico
          ? "SUNAT manda sobre la razón social tecleada cuando el RUC existe."
          : "Nombre y documento viven en la persona: se corrigen en Usuarios → Personas."
      }
    >
      <input type="hidden" name="id" value={proveedor.id} />
      {esJuridico && (
        <>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Razón social
            <input
              name="razon_social"
              required
              maxLength={255}
              defaultValue={proveedor.razon_social ?? ""}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            RUC
            <input
              name="ruc"
              required
              maxLength={11}
              minLength={11}
              inputMode="numeric"
              defaultValue={proveedor.ruc ?? ""}
            />
          </label>
          {/* El domicilio fiscal lo trae SUNAT junto con la razón social;
              sigue siendo editable porque el declarado no siempre es el
              almacén al que uno va a recoger. */}
          <BuscarDocumento
            permisos={permisos}
            tipo="ruc"
            campo="ruc"
            rellena={{
              razon_social: "razon_social",
              direccion: "direccion",
              provincia: "provincia",
            }}
          />
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Dirección
            <input name="direccion" maxLength={255}
              defaultValue={proveedor.direccion ?? ""}
            />
          </label>
          <div className="flex gap-2">
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              Provincia
              <input name="provincia" maxLength={100}
                defaultValue={proveedor.provincia ?? ""}
              />
            </label>
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              País
              <input name="pais" maxLength={60}
                defaultValue={proveedor.pais}
              />
            </label>
          </div>
        </>
      )}
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Contacto
        <input
          name="contacto"
          maxLength={255}
          defaultValue={proveedor.contacto ?? ""}
          placeholder="Teléfono, correo o nombre de quien atiende"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Clasificación
        <select name="clasificacion" defaultValue={proveedor.clasificacion}>
          {CLASIFICACIONES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>
      <CamposCondicionPago proveedor={proveedor} />
      <label className="flex items-center gap-2 text-sm font-semibold">
        <input type="checkbox" name="activo" defaultChecked={proveedor.activo} />
        Activo
      </label>
    </DialogoFormulario>
  );
}

export function ProveedoresCliente({
  proveedores,
  personas,
  permisos,
}: {
  proveedores: Proveedor[];
  personas: Persona[];
  permisos: string[];
}) {
  const nombrePersona = useMemo(
    () => new Map(personas.map((p) => [p.id, `${p.apellidos}, ${p.nombres}`])),
    [personas],
  );

  const columnas: ColumnDef<Proveedor>[] = useMemo(
    () => [
      {
        id: "nombre",
        header: "Proveedor",
        accessorFn: (p) =>
          p.tipo === "natural"
            ? (p.persona_id && nombrePersona.get(p.persona_id)) || "(persona sin resolver)"
            : (p.razon_social ?? "—"),
      },
      {
        id: "identificacion",
        header: "RUC / Doc.",
        accessorFn: (p) => p.ruc ?? "—",
      },
      { accessorKey: "tipo", header: "Tipo" },
      { accessorKey: "condicion_pago", header: "Condición de pago" },
      { accessorKey: "clasificacion", header: "Clasificación" },
      {
        accessorKey: "activo",
        header: "Estado",
        cell: ({ getValue }) => (
          <span
            className={
              getValue<boolean>()
                ? "rounded-full bg-accent/30 px-2 py-0.5 text-xs font-semibold text-dark"
                : "rounded-full bg-gray/20 px-2 py-0.5 text-xs font-semibold text-gray"
            }
          >
            {getValue<boolean>() ? "Activo" : "Inactivo"}
          </span>
        ),
      },
      {
        id: "acciones",
        header: "",
        // Sin `accessorFn`: el buscador de la tabla filtra por texto y esto
        // es un control, no texto.
        cell: ({ row }) => (
          <DialogoEditarProveedor proveedor={row.original} permisos={permisos} />
        ),
      },
    ],
    [nombrePersona, permisos],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl text-dark">Proveedores</h1>
        <DialogoNuevoProveedor permisos={permisos} />
      </div>
      <TablaDatos columnas={columnas} datos={proveedores} placeholderBusqueda="Buscar proveedor..." />
    </div>
  );
}
