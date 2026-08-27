"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useActionState, useMemo, useState, useTransition } from "react";

import {
  BOTON_FILA,
  DialogoFormulario,
  ESTADO_INICIAL,
  type EstadoFormulario,
} from "@/components/formulario/dialogo-formulario";
import { PersonaPicker } from "@/components/persona-picker/persona-picker";
import type { PersonaBusqueda } from "@/components/persona-picker/actions";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { tienePermiso } from "@/lib/permisos";

import {
  asignarRolAction,
  asignarSucursalAction,
  cambiarActivoAction,
  crearUsuarioAction,
  editarUsuarioAction,
  quitarRolAction,
  quitarSucursalAction,
  resetearPinAction,
} from "./actions";

export type Usuario = {
  id: string;
  username: string;
  tipo: string;
  nombre_display: string | null;
  email: string | null;
  persona_id: string | null;
  // Para pintar la persona vinculada sin un segundo viaje al abrir el
  // editor (ADR-070) — antes solo llegaba el id y no había forma de
  // mostrarla al reabrir.
  persona: PersonaBusqueda | null;
  activo: boolean;
};
export type Rol = { id: string; nombre: string; descripcion: string | null };
export type Sucursal = { id: string; nombre: string };

function DialogoNuevaCuenta() {
  return (
    <DialogoFormulario
      titulo="Nueva cuenta"
      disparador="+ Nueva cuenta"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearUsuarioAction}
    >
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
        Persona vinculada
        <PersonaPicker name="persona_id" />
        <span className="text-xs font-normal text-gray">
          Quién es esta cuenta en la vida real. Es lo que habilita a un
          trabajador a marcar asistencia con su PIN en el pad del local.
        </span>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Tipo
        {/* "Servicio" no existe: la columna solo admite `humano` y
            `agente_ia`, así que elegirlo devolvía un 500 del ORM en vez de un
            error entendible. Una cuenta de integración es `agente_ia` y entra
            por token, no por PIN (ADR-032). */}
        <select name="tipo" defaultValue="humano">
          <option value="humano">Humano</option>
          <option value="agente_ia">Agente IA</option>
        </select>
      </label>
    </DialogoFormulario>
  );
}

/** Corrige los datos de la cuenta.
 *
 * El `username` no se ofrece: es con lo que quedó firmada cada acción en el
 * `audit_log`, y cambiarlo dejaría ese rastro apuntando a un nombre que ya
 * no existe. El PIN tampoco — lo cambia su dueño con su propia sesión. */
function DialogoEditarCuenta({ usuario }: { usuario: Usuario }) {
  return (
    <DialogoFormulario
      titulo={`Editar ${usuario.username}`}
      disparador="Editar"
      claseDisparador={BOTON_FILA}
      accion={editarUsuarioAction}
      ayuda="El usuario y el PIN no se editan: el primero firma el rastro de auditoría, el segundo lo cambia su dueño."
    >
      <input type="hidden" name="id" value={usuario.id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre visible
        <input
          name="nombre_display"
          maxLength={100}
          defaultValue={usuario.nombre_display ?? ""}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Email
        <input name="email" type="email" defaultValue={usuario.email ?? ""} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Persona vinculada
        <PersonaPicker name="persona_id" inicial={usuario.persona} />
        <span className="text-xs font-normal text-gray">
          Quién es esta cuenta en la vida real. &quot;Quitar&quot; la
          desvincula: sin persona, el trabajador no puede marcar en el pad
          de asistencia.
        </span>
      </label>
    </DialogoFormulario>
  );
}

/** Lo que una cuenta tiene asignado —roles o sucursales—: lo muestra, lo quita
 * y agrega lo que falte.
 *
 * Vive en la fila y no en un diálogo aparte porque asignar es la operación que
 * más se hace en esta pantalla — un modal por cada cambio sería un clic de más
 * cada vez. */
function CeldaAsignaciones({
  usuario,
  asignados,
  disponibles,
  campo,
  singular,
  accionAsignar,
  quitar,
}: {
  usuario: Usuario;
  asignados: { id: string; nombre: string }[];
  disponibles: { id: string; nombre: string }[];
  campo: string;
  singular: string;
  accionAsignar: (previo: EstadoFormulario, datos: FormData) => Promise<EstadoFormulario>;
  quitar: (usuarioId: string, id: string) => Promise<unknown>;
}) {
  const [estado, formAction] = useActionState(accionAsignar, ESTADO_INICIAL);
  const [pendiente, startTransition] = useTransition();

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {asignados.map((item) => (
        <span
          key={item.id}
          className="flex items-center gap-1 rounded-full bg-accent/30 px-2 py-0.5 text-xs font-semibold text-dark"
        >
          {item.nombre}
          <button
            type="button"
            aria-label={`Quitar ${singular} ${item.nombre} a ${usuario.username}`}
            title={`Quitar ${singular}`}
            disabled={pendiente}
            onClick={() => startTransition(() => void quitar(usuario.id, item.id))}
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
            name={campo}
            defaultValue=""
            aria-label={`Agregar ${singular} a ${usuario.username}`}
            className="rounded border border-gray/40 px-1 py-0.5 text-xs"
          >
            <option value="" disabled>
              + {singular}
            </option>
            {disponibles.map((d) => (
              <option key={d.id} value={d.id}>
                {d.nombre}
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

function faltantes<T extends { id: string }>(todos: T[], asignados: T[]): T[] {
  return todos.filter((t) => !asignados.some((a) => a.id === t.id));
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

/** Resetear el PIN es poder entrar como esa persona, así que pregunta antes.
 * Lo que pasa después lo hace cumplir el servidor: la cuenta no puede hacer
 * nada hasta elegir un PIN nuevo, se le cierran las sesiones abiertas y queda
 * escrito quién la reseteó. */
function BotonResetPin({ usuario }: { usuario: Usuario }) {
  const [pendiente, startTransition] = useTransition();
  const [aviso, setAviso] = useState("");

  if (usuario.tipo !== "humano") return null;

  return (
    <span className="flex flex-col">
      <button
        type="button"
        disabled={pendiente}
        className={BOTON_FILA}
        title="Devuelve el PIN a 123456 y obliga a cambiarlo al entrar"
        onClick={() => {
          if (
            !window.confirm(
              `¿Resetear el PIN de ${usuario.username}? Volverá a 123456, ` +
                "se cerrarán sus sesiones abiertas y tendrá que elegir uno " +
                "nuevo la próxima vez que entre.",
            )
          ) {
            return;
          }
          startTransition(async () => {
            const r = await resetearPinAction(usuario.id);
            setAviso(r.error || "PIN reseteado a 123456.");
          });
        }}
      >
        {pendiente ? "Reseteando..." : "Resetear PIN"}
      </button>
      {aviso && (
        <span role="status" className="text-xs text-gray">
          {aviso}
        </span>
      )}
    </span>
  );
}

export function UsuariosCliente({
  usuarios,
  roles,
  rolesPorUsuario,
  sucursales,
  sucursalesPorUsuario,
  permisos,
}: {
  usuarios: Usuario[];
  roles: Rol[];
  rolesPorUsuario: Record<string, Rol[]>;
  sucursales: Sucursal[];
  sucursalesPorUsuario: Record<string, Sucursal[]>;
  permisos: string[];
}) {
  // El botón se oculta a quien no puede: dejarlo visible para chocar con un
  // 403 al confirmar es peor que no ofrecerlo (mismo criterio que ADR-013).
  const puedeResetear = tienePermiso(permisos, "users.resetear_pin");
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
        id: "persona",
        header: "Persona",
        accessorFn: (u) =>
          u.persona ? `${u.persona.apellidos}, ${u.persona.nombres}` : "—",
      },
      {
        id: "roles",
        header: "Roles",
        // Sin `accessorFn`: el buscador de la tabla filtra por texto y estos
        // son controles, no texto.
        cell: ({ row }) => {
          const asignados = rolesPorUsuario[row.original.id] ?? [];
          return (
            <CeldaAsignaciones
              usuario={row.original}
              asignados={asignados}
              disponibles={faltantes(roles, asignados)}
              campo="rol_id"
              singular="rol"
              accionAsignar={asignarRolAction}
              quitar={quitarRolAction}
            />
          );
        },
      },
      {
        id: "sucursales",
        header: "Sucursales",
        cell: ({ row }) => {
          const asignadas = sucursalesPorUsuario[row.original.id] ?? [];
          return (
            <CeldaAsignaciones
              usuario={row.original}
              asignados={asignadas}
              disponibles={faltantes(sucursales, asignadas)}
              campo="sucursal_id"
              singular="sucursal"
              accionAsignar={asignarSucursalAction}
              quitar={quitarSucursalAction}
            />
          );
        },
      },
      {
        accessorKey: "activo",
        header: "Estado",
        cell: ({ row }) => <BotonActivo usuario={row.original} />,
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => (
          <span className="flex items-center gap-2">
            <DialogoEditarCuenta usuario={row.original} />
            {puedeResetear && <BotonResetPin usuario={row.original} />}
          </span>
        ),
      },
    ],
    [roles, rolesPorUsuario, sucursales, sucursalesPorUsuario, puedeResetear],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl text-dark">Cuentas</h1>
        <DialogoNuevaCuenta />
      </div>
      <p className="text-sm text-gray">
        Quién entra al ERP y con qué rol. Una cuenta sin rol entra pero no ve nada: el
        RBAC deniega por defecto. Las sucursales acotan qué datos alcanza —un
        supervisor lleva las que tenga a cargo—; no son dónde trabaja la persona, eso
        se registra en RRHH → Trabajadores. Un cambio de sucursales le aplica cuando
        esa cuenta vuelva a entrar.
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
