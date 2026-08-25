"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import { BOTON_FILA, DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { PersonaPicker } from "@/components/persona-picker/persona-picker";
import { TablaDatos } from "@/components/tabla/tabla-datos";

import {
  cesarTrabajadorAction,
  crearTrabajadorAction,
  editarTrabajadorAction,
} from "./actions";

export type Trabajador = {
  id: string;
  persona_id: string;
  sucursal_id: string | null;
  usuario_id: string | null;
  cargo: string;
  area: string;
  tipo_vinculo: string;
  fecha_ingreso: string;
  fecha_cese: string | null;
  remuneracion_base: string | null;
  estado: string;
};
export type Sucursal = { id: string; nombre: string };
export type Cuenta = {
  id: string;
  username: string;
  tipo: string;
  nombre_display: string | null;
};
export type Persona = {
  id: string;
  nombres: string;
  apellidos: string;
  numero_documento: string | null;
};

const TIPOS_VINCULO = ["planilla", "practicante", "locacion_servicios"] as const;

/** El local donde trabaja, no a qué datos accede: el alcance de la cuenta se
 * reparte en Usuarios → Cuentas (ADR-062). Vacío es válido — gerencia y
 * administración no están en ninguna sucursal. */
function CampoSucursal({
  sucursales,
  valor,
}: {
  sucursales: Sucursal[];
  valor?: string | null;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm font-semibold">
      Sucursal donde trabaja
      <select name="sucursal_id" defaultValue={valor ?? ""}>
        <option value="">Sin sucursal asignada</option>
        {sucursales.map((s) => (
          <option key={s.id} value={s.id}>
            {s.nombre}
          </option>
        ))}
      </select>
    </label>
  );
}

/** La cuenta con la que marca asistencia. Sin ella el pad lo rechaza: el PIN
 * que firma la marcación es el de esta cuenta (RN-RRHH-020), no un dato del
 * trabajador. Vacío es válido — quien no ficha en el pad no necesita una, y
 * su asistencia la registra RRHH por back-office. */
function CampoCuenta({ cuentas, valor }: { cuentas: Cuenta[]; valor?: string | null }) {
  const humanas = cuentas.filter((c) => c.tipo === "humano");
  return (
    <label className="flex flex-col gap-1 text-sm font-semibold">
      Cuenta para marcar asistencia
      {humanas.length === 0 ? (
        <p className="text-sm font-normal text-secondary">
          No se pudieron listar las cuentas: hace falta permiso de administración
          de usuarios. Pídelo a quien administre Usuarios → Cuentas.
        </p>
      ) : (
        <select name="usuario_id" defaultValue={valor ?? ""}>
          <option value="">Sin cuenta (marca por back-office)</option>
          {humanas.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nombre_display ? `${c.nombre_display} — ${c.username}` : c.username}
            </option>
          ))}
        </select>
      )}
    </label>
  );
}

function DialogoNuevoTrabajador({
  sucursales,
  cuentas,
}: {
  sucursales: Sucursal[];
  cuentas: Cuenta[];
}) {
  return (
    <DialogoFormulario
      titulo="Nuevo trabajador"
      disparador="+ Nuevo trabajador"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearTrabajadorAction}
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Persona (debe existir de antes)
        <PersonaPicker name="persona_id" />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Cargo
        <input name="cargo" required maxLength={100} placeholder="Cocinero" />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Área
        <input name="area" required maxLength={100} placeholder="Cocina" />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Tipo de vínculo
        <select name="tipo_vinculo" defaultValue="planilla">
          {TIPOS_VINCULO.map((t) => (
            <option key={t} value={t}>
              {t.replace("_", " ")}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Fecha de ingreso
        <input name="fecha_ingreso" type="date" required />
      </label>
      <CampoSucursal sucursales={sucursales} />
      <CampoCuenta cuentas={cuentas} />
    </DialogoFormulario>
  );
}

/** Corrección del legajo: cargo, área, remuneración y suspensión.
 *
 * El nombre y el documento no están porque viven en la persona
 * (RN-GEN-007); el tipo de vínculo y la fecha de ingreso tampoco, porque
 * cambiarlos reescribe la historia laboral —eso es un contrato nuevo, no una
 * corrección—. */
function DialogoEditarTrabajador({
  trabajador,
  sucursales,
  cuentas,
}: {
  trabajador: Trabajador;
  sucursales: Sucursal[];
  cuentas: Cuenta[];
}) {
  return (
    <DialogoFormulario
      titulo="Editar trabajador"
      disparador="Editar"
      claseDisparador={BOTON_FILA}
      accion={editarTrabajadorAction}
      ayuda="Nombre y documento se corrigen en Usuarios → Personas. El vínculo y la fecha de ingreso no se editan: cambiarlos sería otro contrato."
    >
      <input type="hidden" name="id" value={trabajador.id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Cargo
        <input name="cargo" required maxLength={100} defaultValue={trabajador.cargo} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Área
        <input name="area" required maxLength={100} defaultValue={trabajador.area} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Remuneración base
        <input
          name="remuneracion_base"
          type="number"
          min={0}
          step="0.01"
          defaultValue={trabajador.remuneracion_base ?? ""}
          placeholder="O subvención, si es practicante"
        />
      </label>
      <CampoSucursal sucursales={sucursales} valor={trabajador.sucursal_id} />
      <CampoCuenta cuentas={cuentas} valor={trabajador.usuario_id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Estado
        <select name="estado" defaultValue={trabajador.estado}>
          <option value="activo">Activo</option>
          <option value="suspendido">Suspendido</option>
        </select>
      </label>
    </DialogoFormulario>
  );
}

/** Cese: acción aparte porque fija la fecha y dispara la liquidación. */
function DialogoCesarTrabajador({ trabajador }: { trabajador: Trabajador }) {
  return (
    <DialogoFormulario
      titulo="Registrar cese"
      disparador="Cesar"
      claseDisparador={BOTON_FILA}
      etiquetaEnvio="Registrar cese"
      etiquetaPendiente="Registrando..."
      accion={cesarTrabajadorAction}
      ayuda="El cese fija la fecha y avisa a los módulos que dependen de ella. No se deshace desde acá."
    >
      <input type="hidden" name="id" value={trabajador.id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Fecha de cese
        <input name="fecha_cese" type="date" required />
      </label>
    </DialogoFormulario>
  );
}

export function TrabajadoresCliente({
  trabajadores,
  personas,
  sucursales,
  cuentas,
}: {
  trabajadores: Trabajador[];
  personas: Persona[];
  sucursales: Sucursal[];
  cuentas: Cuenta[];
}) {
  const nombrePersona = useMemo(
    () => new Map(personas.map((p) => [p.id, `${p.apellidos}, ${p.nombres}`])),
    [personas],
  );
  const nombreSucursal = useMemo(
    () => new Map(sucursales.map((s) => [s.id, s.nombre])),
    [sucursales],
  );

  const columnas: ColumnDef<Trabajador>[] = useMemo(
    () => [
      {
        id: "persona",
        header: "Nombre",
        accessorFn: (t) => nombrePersona.get(t.persona_id) ?? "—",
      },
      { accessorKey: "cargo", header: "Cargo" },
      { accessorKey: "area", header: "Área" },
      {
        id: "sucursal",
        header: "Sucursal",
        accessorFn: (t) => (t.sucursal_id ? nombreSucursal.get(t.sucursal_id) ?? "—" : "—"),
      },
      {
        accessorKey: "tipo_vinculo",
        header: "Vínculo",
        cell: ({ getValue }) => getValue<string>().replace("_", " "),
      },
      { accessorKey: "fecha_ingreso", header: "Ingreso" },
      // Quién puede fichar en el pad se ve de un vistazo: sin cuenta, la
      // marcación la tiene que cargar RRHH a mano.
      {
        id: "cuenta",
        header: "Marca",
        accessorFn: (t) => (t.usuario_id ? "sí" : "no"),
      },
      {
        accessorKey: "estado",
        header: "Estado",
        cell: ({ getValue }) => (
          <span
            className={
              getValue<string>() === "activo"
                ? "rounded-full bg-accent/30 px-2 py-0.5 text-xs font-semibold text-dark"
                : "rounded-full bg-gray/20 px-2 py-0.5 text-xs font-semibold text-gray"
            }
          >
            {getValue<string>()}
          </span>
        ),
      },
      {
        id: "acciones",
        header: "",
        // Un cesado no se edita ni se vuelve a cesar: ofrecer el control
        // solo invita al 409 (mismo criterio que Producción).
        cell: ({ row }) =>
          row.original.estado === "cesado" ? null : (
            <div className="flex gap-1.5">
              <DialogoEditarTrabajador
                trabajador={row.original}
                sucursales={sucursales}
                cuentas={cuentas}
              />
              <DialogoCesarTrabajador trabajador={row.original} />
            </div>
          ),
      },
    ],
    [nombrePersona, nombreSucursal, sucursales, cuentas],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl text-dark">Trabajadores</h1>
        <DialogoNuevoTrabajador sucursales={sucursales} cuentas={cuentas} />
      </div>
      <TablaDatos
        columnas={columnas}
        datos={trabajadores}
        placeholderBusqueda="Buscar trabajador..."
      />
    </div>
  );
}
