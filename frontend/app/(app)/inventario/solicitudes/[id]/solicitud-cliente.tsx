"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { tienePermiso } from "@/lib/permisos";

import {
  agregarItemAction,
  aprobarSolicitudAction,
  cambiarCantidadAction,
  cancelarSolicitudAction,
  enviarSolicitudAction,
  quitarItemAction,
  rechazarSolicitudAction,
} from "../actions";

export type ItemSolicitud = {
  sku_id: string;
  cantidad_solicitada: string;
  cantidad_aprobada: string | null;
  cantidad_despachada: string | null;
  bajo_minimo_al_pedir: boolean;
};

export type SolicitudDetalle = {
  id: string;
  almacen_solicitante_id: string;
  almacen_abastecedor_id: string;
  estado: string;
  observacion: string | null;
  items: ItemSolicitud[];
};

type OpcionSku = { id: string; etiqueta: string };

/** Lanza una acción del servidor y deja el error a la vista si falla. */
type Correr = (accion: () => Promise<{ error: string; ok: boolean }>) => void;

/**
 * Un requerimiento: la lista de la jornada mientras es borrador, y el pedido
 * que el abastecedor aprueba una vez enviado (ADR-051).
 *
 * Es una sola pantalla y no dos porque son el mismo documento en dos momentos:
 * duplicarla habría dejado dos lugares donde arreglar la columna que importa
 * —la urgencia— y el que se olvida es siempre el que mira el almacén.
 */
export function SolicitudCliente({
  solicitud,
  nombreDeAlmacen,
  skus,
  permisos,
}: {
  solicitud: SolicitudDetalle;
  nombreDeAlmacen: Record<string, string>;
  skus: OpcionSku[];
  permisos: string[];
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [pendiente, ejecutar] = useTransition();

  const esBorrador = solicitud.estado === "borrador";
  const editable = esBorrador && tienePermiso(permisos, "inventory.solicitar_insumos");

  const correr: Correr = (accion) => {
    setError("");
    ejecutar(async () => {
      const r = await accion();
      if (!r.ok) setError(r.error);
      else router.refresh();
    });
  };

  const urgentes = solicitud.items.filter((i) => i.bajo_minimo_al_pedir).length;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <Cabecera solicitud={solicitud} nombreDeAlmacen={nombreDeAlmacen} />
        <Acciones
          solicitud={solicitud}
          editable={editable}
          puedeAprobar={tienePermiso(permisos, "inventory.aprobar_solicitud")}
          skus={skus}
          pendiente={pendiente}
          correr={correr}
        />
      </div>

      {/* Lo que el almacenero necesita saber antes de leer la tabla: cuánto
          de esto se está por acabar y cuánto lo pidió el local por decisión
          propia (RN-INV-024). */}
      <p className="text-xs text-gray">
        {urgentes} bajo mínimo · {solicitud.items.length - urgentes} a pedido
        del local
      </p>

      {error && <p className="text-sm text-secondary">{error}</p>}

      <Tabla
        solicitud={solicitud}
        editable={editable}
        skus={skus}
        pendiente={pendiente}
        correr={correr}
      />
    </div>
  );
}

/** De quién es el pedido y a quién se lo hace. */
function Cabecera({
  solicitud,
  nombreDeAlmacen,
}: {
  solicitud: SolicitudDetalle;
  nombreDeAlmacen: Record<string, string>;
}) {
  const solicitante = nombreDeAlmacen[solicitud.almacen_solicitante_id] ?? "—";
  const abastecedor = nombreDeAlmacen[solicitud.almacen_abastecedor_id] ?? "—";
  return (
    <div>
      <Link href="/inventario/solicitudes" className="text-xs text-gray underline">
        ← Requerimientos
      </Link>
      <h1 className="font-heading text-xl italic uppercase text-dark">
        {solicitud.estado === "borrador"
          ? "Requerimiento de la jornada"
          : "Requerimiento"}
      </h1>
      <p className="text-xs text-gray">
        {solicitante} · se abastece de {abastecedor} ·{" "}
        <span className="font-semibold">{solicitud.estado}</span>
      </p>
    </div>
  );
}

/** Lo que se puede hacer con el documento **en este estado**: editarlo y
 * enviarlo mientras es borrador, aprobarlo o rechazarlo una vez enviado. */
function Acciones({
  solicitud,
  editable,
  puedeAprobar,
  skus,
  pendiente,
  correr,
}: {
  solicitud: SolicitudDetalle;
  editable: boolean;
  puedeAprobar: boolean;
  skus: OpcionSku[];
  pendiente: boolean;
  correr: Correr;
}) {
  const yaEnLaLista = new Set(solicitud.items.map((i) => i.sku_id));

  if (editable) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <AgregarProducto
          solicitudId={solicitud.id}
          skus={skus.filter((s) => !yaEnLaLista.has(s.id))}
        />
        <Boton
          onClick={() => correr(() => enviarSolicitudAction(solicitud.id))}
          deshabilitado={pendiente || solicitud.items.length === 0}
        >
          Enviar
        </Boton>
        <BotonSecundario
          onClick={() => correr(() => cancelarSolicitudAction(solicitud.id))}
          deshabilitado={pendiente}
        >
          Descartar
        </BotonSecundario>
      </div>
    );
  }

  if (solicitud.estado === "pendiente" && puedeAprobar) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <Boton
          onClick={() => correr(() => aprobarSolicitudAction(solicitud.id))}
          deshabilitado={pendiente}
        >
          Aprobar
        </Boton>
        <BotonSecundario
          onClick={() => correr(() => rechazarSolicitudAction(solicitud.id))}
          deshabilitado={pendiente}
        >
          Rechazar
        </BotonSecundario>
      </div>
    );
  }

  return null;
}

function Tabla({
  solicitud,
  editable,
  skus,
  pendiente,
  correr,
}: {
  solicitud: SolicitudDetalle;
  editable: boolean;
  skus: OpcionSku[];
  pendiente: boolean;
  correr: Correr;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[36rem] text-sm">
        <thead className="text-left text-xs uppercase text-gray">
          <tr>
            <th className="py-2">Producto</th>
            <th className="py-2">Por qué</th>
            <th className="py-2">Pedido</th>
            {editable ? (
              <th className="py-2" />
            ) : (
              <>
                <th className="py-2">Aprobado</th>
                <th className="py-2">Despachado</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {solicitud.items.map((item) => (
            <Fila
              key={item.sku_id}
              item={item}
              solicitudId={solicitud.id}
              editable={editable}
              etiqueta={
                skus.find((s) => s.id === item.sku_id)?.etiqueta ?? item.sku_id
              }
              pendiente={pendiente}
              correr={correr}
            />
          ))}
          {solicitud.items.length === 0 && (
            <tr>
              <td colSpan={5} className="py-6 text-center text-gray">
                La lista está vacía. Nada está bajo mínimo en este almacén:
                agrega lo que necesites.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function Fila({
  item,
  solicitudId,
  editable,
  etiqueta,
  pendiente,
  correr,
}: {
  item: ItemSolicitud;
  solicitudId: string;
  editable: boolean;
  etiqueta: string;
  pendiente: boolean;
  correr: Correr;
}) {
  const [cantidad, setCantidad] = useState(item.cantidad_solicitada);

  return (
    <tr className="border-t border-black/5">
      <td className="py-2">{etiqueta}</td>
      <td className="py-2">
        <Etiqueta urgente={item.bajo_minimo_al_pedir} />
      </td>
      <td className="py-2">
        {editable ? (
          <input
            aria-label={`Cantidad de ${etiqueta}`}
            className="w-24"
            inputMode="decimal"
            value={cantidad}
            onChange={(e) => setCantidad(e.target.value)}
            onBlur={() => {
              if (cantidad !== item.cantidad_solicitada) {
                correr(() =>
                  cambiarCantidadAction(solicitudId, item.sku_id, cantidad),
                );
              }
            }}
          />
        ) : (
          item.cantidad_solicitada
        )}
      </td>
      {!editable && <td className="py-2">{item.cantidad_aprobada ?? "—"}</td>}
      {!editable && <td className="py-2">{item.cantidad_despachada ?? "—"}</td>}
      {editable && (
        <td className="py-2 text-right">
          <button
            type="button"
            className="text-xs text-secondary underline"
            disabled={pendiente}
            onClick={() => correr(() => quitarItemAction(solicitudId, item.sku_id))}
          >
            Quitar
          </button>
        </td>
      )}
    </tr>
  );
}

/** La respuesta a "¿esto es urgente?" en una palabra. */
function Etiqueta({ urgente }: { urgente: boolean }) {
  return urgente ? (
    <span className="rounded-full bg-secondary/15 px-2 py-0.5 text-xs font-semibold text-secondary">
      Bajo mínimo
    </span>
  ) : (
    <span className="rounded-full bg-black/5 px-2 py-0.5 text-xs font-semibold text-gray">
      Pedido del local
    </span>
  );
}

function AgregarProducto({
  solicitudId,
  skus,
}: {
  solicitudId: string;
  skus: OpcionSku[];
}) {
  return (
    <DialogoFormulario
      titulo="Agregar producto"
      disparador="+ Agregar producto"
      accion={agregarItemAction.bind(null, solicitudId)}
      etiquetaEnvio="Agregar"
      ayuda="Lo que agregues acá no está bajo mínimo: el almacén lo va a ver marcado como pedido del local, no como urgencia."
      envioDeshabilitado={skus.length === 0}
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Producto
        <select name="sku_id" defaultValue="">
          <option value="" disabled>
            Elegir…
          </option>
          {skus.map((s) => (
            <option key={s.id} value={s.id}>
              {s.etiqueta}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Cantidad
        <input name="cantidad" inputMode="decimal" defaultValue="1" />
      </label>
    </DialogoFormulario>
  );
}

const CLASE_BOTON =
  "inline-flex items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/85 disabled:pointer-events-none disabled:opacity-50";

function Boton({
  children,
  onClick,
  deshabilitado,
}: {
  children: React.ReactNode;
  onClick: () => void;
  deshabilitado: boolean;
}) {
  return (
    <button
      type="button"
      className={CLASE_BOTON}
      onClick={onClick}
      disabled={deshabilitado}
    >
      {children}
    </button>
  );
}

function BotonSecundario({
  children,
  onClick,
  deshabilitado,
}: {
  children: React.ReactNode;
  onClick: () => void;
  deshabilitado: boolean;
}) {
  return (
    <button
      type="button"
      className="rounded-lg border border-black/10 px-3 py-1.5 text-sm font-semibold text-secondary disabled:pointer-events-none disabled:opacity-50"
      onClick={onClick}
      disabled={deshabilitado}
    >
      {children}
    </button>
  );
}
