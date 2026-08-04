"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useActionState, useEffect, useMemo, useRef, useState, useTransition } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";

import {
  asignarRolAction,
  cambiarActivoAction,
  crearUsuarioAction,
  quitarRolAction,
  type EstadoUsuario,
} from "./actions";

export type Usuario = {
  id: string;
  username: string;
  tipo: string;
  nombre_display: string | null;
  email: string | null;
  activo: boolean;
};
export type Rol = { id: string; nombre: string; descripcion: string | null };

const ESTADO_INICIAL: EstadoUsuario = { error: "", ok: false };

function DialogoNuevaCuenta() {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [estado, formAction, pendiente] = useActionState(crearUsuarioAction, ESTADO_INICIAL);

  useEffect(() => {
    if (estado.ok) {
      formRef.current?.reset();
      dialogRef.current?.close();
    }
  }, [estado.ok]);

  return (
    <>
      <button
        type="button"
        onClick={() => dialogRef.current?.showModal()}
        className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
      >
        + Nueva cuenta
      </button>
      <dialog ref={dialogRef} className="w-full max-w-md rounded-lg p-0 backdrop:bg-dark/40">
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg italic uppercase text-dark">Nueva cuenta</h2>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Usuario
            <input name="username" required minLength={3} maxLength={50} autoComplete="off" />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            PIN
            <input
              name="pin"
              required
              inputMode="numeric"
              autoComplete="new-password"
              type="password"
            />
            <span className="text-xs font-normal text-gray">
              Solo dígitos. El usuario lo cambia después con su propia sesión.
            </span>
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Nombre visible
            <input name="nombre_display" maxLength={100} placeholder="Opcional" />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Email
            <input name="email" type="email" placeholder="Opcional" />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Tipo
            <select name="tipo" defaultValue="humano">
              <option value="humano">Humano</option>
              <option value="servicio">Servicio</option>
              <option value="agente_ia">Agente IA</option>
            </select>
          </label>
          {estado.error && (
            <p role="alert" className="text-sm font-semibold text-secondary">
              {estado.error}
            </p>
          )}
          <div className="mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => dialogRef.current?.close()}
              className="rounded border border-gray px-4 py-2 text-sm font-semibold text-dark"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={pendiente}
              className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
            >
              {pendiente ? "Creando..." : "Crear"}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

/** Roles de una cuenta: los muestra, los quita y agrega el que falte.
 *
 * Vive en la fila y no en un diálogo aparte porque asignar un rol es la
 * operación que más se hace en esta pantalla — un modal por cada cambio
 * sería un clic de más cada vez. */
function CeldaRoles({
  usuario,
  roles,
  asignados,
}: {
  usuario: Usuario;
  roles: Rol[];
  asignados: Rol[];
}) {
  const [estado, formAction] = useActionState(asignarRolAction, ESTADO_INICIAL);
  const [pendiente, startTransition] = useTransition();
  const disponibles = roles.filter((r) => !asignados.some((a) => a.id === r.id));

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {asignados.map((rol) => (
        <span
          key={rol.id}
          className="flex items-center gap-1 rounded-full bg-accent/30 px-2 py-0.5 text-xs font-semibold text-dark"
        >
          {rol.nombre}
          <button
            type="button"
            aria-label={`Quitar rol ${rol.nombre} a ${usuario.username}`}
            title="Quitar rol"
            disabled={pendiente}
            onClick={() => startTransition(() => void quitarRolAction(usuario.id, rol.id))}
            className="text-gray hover:text-secondary"
          >
            ×
          </button>
        </span>
      ))}
      {disponibles.length > 0 && (
        <form action={formAction} className="flex items-center gap-1">
          <input type="hidden" name="usuario_id" value={usuario.id} />
          <select
            name="rol_id"
            defaultValue=""
            aria-label={`Agregar rol a ${usuario.username}`}
            className="rounded border border-gray/40 px-1 py-0.5 text-xs"
          >
            <option value="" disabled>
              + rol
            </option>
            {disponibles.map((r) => (
              <option key={r.id} value={r.id}>
                {r.nombre}
              </option>
            ))}
          </select>
          <button type="submit" className="text-xs font-bold text-primary hover:underline">
            Asignar
          </button>
        </form>
      )}
      {estado.error && <span className="text-xs text-secondary">{estado.error}</span>}
    </div>
  );
}

function BotonActivo({ usuario }: { usuario: Usuario }) {
  const [pendiente, startTransition] = useTransition();
  return (
    <button
      type="button"
      disabled={pendiente}
      onClick={() => startTransition(() => void cambiarActivoAction(usuario.id, !usuario.activo))}
      className={
        usuario.activo
          ? "rounded-full bg-accent/30 px-2 py-0.5 text-xs font-semibold text-dark hover:bg-accent/50"
          : "rounded-full bg-gray/20 px-2 py-0.5 text-xs font-semibold text-gray hover:bg-gray/30"
      }
      title={usuario.activo ? "Desactivar la cuenta" : "Reactivar la cuenta"}
    >
      {usuario.activo ? "Activa" : "Inactiva"}
    </button>
  );
}

export function UsuariosCliente({
  usuarios,
  roles,
  rolesPorUsuario,
}: {
  usuarios: Usuario[];
  roles: Rol[];
  rolesPorUsuario: Record<string, Rol[]>;
}) {
  const [busquedaRol, setBusquedaRol] = useState("");
  const visibles = useMemo(
    () =>
      busquedaRol
        ? usuarios.filter((u) =>
            (rolesPorUsuario[u.id] ?? []).some((r) => r.nombre === busquedaRol),
          )
        : usuarios,
    [usuarios, rolesPorUsuario, busquedaRol],
  );

  const columnas: ColumnDef<Usuario>[] = useMemo(
    () => [
      { accessorKey: "username", header: "Usuario" },
      {
        id: "nombre",
        header: "Nombre",
        accessorFn: (u) => u.nombre_display ?? "—",
      },
      { accessorKey: "tipo", header: "Tipo" },
      {
        id: "roles",
        header: "Roles",
        // Sin `accessorFn`: el buscador de la tabla filtra por texto y estos
        // son controles, no texto.
        cell: ({ row }) => (
          <CeldaRoles
            usuario={row.original}
            roles={roles}
            asignados={rolesPorUsuario[row.original.id] ?? []}
          />
        ),
      },
      {
        accessorKey: "activo",
        header: "Estado",
        cell: ({ row }) => <BotonActivo usuario={row.original} />,
      },
    ],
    [roles, rolesPorUsuario],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl italic uppercase text-dark">Cuentas</h1>
        <DialogoNuevaCuenta />
      </div>
      <p className="text-sm text-gray">
        Quién entra al ERP y con qué rol. Una cuenta sin rol entra pero no ve nada: el
        RBAC deniega por defecto.
      </p>
      <label className="flex w-64 flex-col gap-1 text-sm font-semibold">
        Filtrar por rol
        <select
          value={busquedaRol}
          onChange={(e) => setBusquedaRol(e.target.value)}
          className="rounded border border-gray/40 px-2 py-1 text-sm font-normal"
        >
          <option value="">Todos</option>
          {roles.map((r) => (
            <option key={r.id} value={r.nombre}>
              {r.nombre}
            </option>
          ))}
        </select>
      </label>
      <TablaDatos columnas={columnas} datos={visibles} placeholderBusqueda="Buscar usuario..." />
    </div>
  );
}
