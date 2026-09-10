"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Insignia } from "@/components/estado/insignia";
import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { Combobox } from "@/components/ui/combobox";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { ErrorApi, pedir } from "@/lib/cliente-api";
import { primeroElDe } from "@/lib/destinos";
import { tienePermiso } from "@/lib/permisos";

import {
  anularDevolucionAction,
  emitirGuiaDevolucionAction,
  registrarDevolucionAction,
} from "./actions";

export type Devolucion = {
  id: string;
  almacen_id: string;
  origen: string;
  referencia_id: string | null;
  motivo: string;
  destino: string | null;
  estado: string;
  reporte_dirigido_a: string;
  observacion: string | null;
};

export type OpcionAlmacen = { id: string; nombre: string };
export type OpcionSku = { id: string; etiqueta: string };

type GuiaRemision = {
  id: string;
  serie: string;
  correlativo: number;
  estado_emision: string;
  detalle_emision: string | null;
};

const TONO_GUIA: Record<string, "exito" | "alerta" | "peligro" | "info" | "neutro"> = {
  pendiente: "info",
  aceptado: "exito",
  rechazado: "peligro",
  error: "alerta",
};

/** Los mismos valores que el enum del servidor (`devoluciones.MOTIVOS`). */
const MOTIVOS = [
  ["vencido", "Vencido"],
  ["dañado", "Dañado"],
  ["incumplimiento_plazo", "Llegó fuera de plazo"],
  ["no_requerido", "No se necesitaba"],
  ["error_solicitud", "Error al solicitar"],
  ["duplicidad", "Pedido duplicado"],
] as const;

/** Qué se hace con lo que volvió (RN-INV-019). Solo aplica a cliente. */
const DESTINOS = [
  ["reintegro", "Vuelve al estante"],
  ["desecho", "Se desecha"],
  ["auditoria", "Se aparta para auditar"],
] as const;

/**
 * Devoluciones: registrar, ver y anular (RN-INV-019/020).
 *
 * Hasta 2026-08-13 era una tabla de solo lectura y la API completa quedaba
 * inalcanzable: la devolución existía en el modelo y no había forma de
 * registrar una sin llamar al endpoint a mano.
 */
export function DevolucionesCliente({
  devoluciones,
  resaltado,
  almacenes,
  skus,
  permisos,
}: {
  devoluciones: Devolucion[];
  resaltado: string | null;
  almacenes: OpcionAlmacen[];
  skus: OpcionSku[];
  permisos: string[];
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  // Registrar una devolución y anularla mueven stock real: las dos exigen
  // `inventory.registrar_movimiento` en la API. El permiso decide si el
  // control se ofrece —autoriza la API—, porque un botón que siempre
  // termina en 403 es peor que no tenerlo.
  const puedeRegistrar = tienePermiso(permisos, "inventory.registrar_movimiento");
  const puedeEmitirGuia = tienePermiso(permisos, "inventory.emitir_guia");

  const anular = async (id: string) => {
    setError("");
    const r = await anularDevolucionAction(id);
    if (!r.ok) setError(r.error);
    else router.refresh();
  };

  const columnas = useMemo<ColumnDef<Devolucion>[]>(
    () => [
      {
        header: "Origen",
        accessorKey: "origen",
        cell: ({ row }) => (
          <Link
            href={`/inventario/devoluciones/${row.original.id}`}
            className="font-semibold text-primary hover:underline"
          >
            {row.original.origen === "proveedor" ? "A proveedor" : "De cliente"}
          </Link>
        ),
      },
      { header: "Motivo", accessorKey: "motivo" },
      {
        header: "Destino",
        accessorKey: "destino",
        cell: ({ row }) => row.original.destino ?? "—",
      },
      { header: "Dirigida a", accessorKey: "reporte_dirigido_a" },
      { header: "Estado", accessorKey: "estado" },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => (
          <div className="flex items-center gap-3">
            {row.original.estado === "registrada" && puedeRegistrar && (
              <button
                type="button"
                className="text-xs text-secondary underline"
                onClick={() => anular(row.original.id)}
              >
                Anular
              </button>
            )}
            {row.original.origen === "proveedor" &&
              row.original.estado === "registrada" &&
              puedeEmitirGuia && <DialogoGuia devolucion={row.original} />}
          </div>
        ),
      },
    ],
    // `anular` se recrea en cada render y no aporta nada como dependencia:
    // lo que importa es que las columnas no se rearmen por cada tecla.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [puedeRegistrar, puedeEmitirGuia],
  );

  const ordenadas = useMemo(
    () => primeroElDe(devoluciones, resaltado, (d) => d.id),
    [devoluciones, resaltado],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-xl italic uppercase text-dark">
            Devoluciones
          </h1>
          <p className="text-xs text-gray">
            Lo que se le devuelve al proveedor y lo que devuelve un cliente.
            Mueve stock real y queda auditado.
          </p>
        </div>
        {puedeRegistrar && <FormularioDevolucion almacenes={almacenes} skus={skus} />}
      </div>

      {error && <p className="text-sm text-secondary">{error}</p>}

      <TablaDatos
        columnas={columnas}
        datos={ordenadas}
        placeholderBusqueda="Buscar por motivo u origen..."
        vacio="Todavía no se registró ninguna devolución."
      />
    </div>
  );
}

type LineaDevolucion = { clave: number; sku: string; cantidad: string };

const LINEAS_INICIALES: LineaDevolucion[] = [{ clave: 1, sku: "", cantidad: "1" }];

function FormularioDevolucion({
  almacenes,
  skus,
}: {
  almacenes: OpcionAlmacen[];
  skus: OpcionSku[];
}) {
  const [origen, setOrigen] = useState("proveedor");
  const [lineas, setLineas] = useState<LineaDevolucion[]>(LINEAS_INICIALES);

  const editar = (clave: number, campo: keyof LineaDevolucion, valor: string) =>
    setLineas((prev) => prev.map((l) => (l.clave === clave ? { ...l, [campo]: valor } : l)));

  return (
    <DialogoFormulario
      titulo="Registrar devolución"
      disparador="+ Nueva devolución"
      accion={registrarDevolucionAction}
      etiquetaEnvio="Registrar"
      ayuda="A proveedor la mercadería sale del almacén; de cliente entra, y el destino decide si vuelve al estante o se aparta."
      envioDeshabilitado={almacenes.length === 0 || skus.length === 0}
      alAbrir={() => setLineas(LINEAS_INICIALES)}
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Origen
        <select name="origen" value={origen} onChange={(e) => setOrigen(e.target.value)}>
          <option value="proveedor">A proveedor (sale del almacén)</option>
          <option value="cliente">De cliente (entra al almacén)</option>
        </select>
      </label>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Almacén
        <Combobox
          name="almacen_id"
          etiqueta="Almacén"
          requerido
          marcador="Elegir…"
          opciones={almacenes.map((a) => ({ valor: a.id, etiqueta: a.nombre }))}
        />
      </label>

      <div className="flex flex-col gap-2">
        {lineas.map((linea) => (
          <div key={linea.clave} className="flex items-end gap-2">
            <label className="flex flex-1 flex-col gap-1 text-xs font-semibold">
              Qué se devuelve
              <Combobox
                name="sku_id"
                etiqueta="Qué se devuelve"
                requerido
                marcador="Elegir…"
                value={linea.sku}
                alCambiar={(v) => editar(linea.clave, "sku", v ?? "")}
                opciones={skus.map((s) => ({ valor: s.id, etiqueta: s.etiqueta }))}
              />
            </label>
            <label className="flex w-28 flex-col gap-1 text-xs font-semibold">
              Cantidad
              <input
                name="cantidad"
                type="number"
                min="0.0001"
                step="0.0001"
                required
                value={linea.cantidad}
                onChange={(e) => editar(linea.clave, "cantidad", e.target.value)}
              />
            </label>
            <button
              type="button"
              aria-label="Quitar línea"
              disabled={lineas.length <= 1}
              onClick={() => setLineas((prev) => prev.filter((l) => l.clave !== linea.clave))}
              className="pb-1.5 text-muted-foreground hover:text-status-danger disabled:opacity-30"
            >
              ×
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() =>
            setLineas((prev) => [
              ...prev,
              { clave: Math.max(...prev.map((l) => l.clave)) + 1, sku: "", cantidad: "1" },
            ])
          }
          className="self-start text-sm font-semibold text-primary hover:underline"
        >
          + Agregar artículo
        </button>
      </div>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Motivo
        <select name="motivo" defaultValue="dañado">
          {MOTIVOS.map(([valor, etiqueta]) => (
            <option key={valor} value={valor}>
              {etiqueta}
            </option>
          ))}
        </select>
      </label>

      {/* El destino solo existe para una devolución de cliente: a proveedor
          la mercadería se va, así que no hay nada que decidir. */}
      {origen === "cliente" && (
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Qué se hace con lo que volvió
          <select name="destino" defaultValue="reintegro">
            {DESTINOS.map(([valor, etiqueta]) => (
              <option key={valor} value={valor}>
                {etiqueta}
              </option>
            ))}
          </select>
        </label>
      )}

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Observación
        <input name="observacion" maxLength={255} placeholder="Opcional" />
      </label>
    </DialogoFormulario>
  );
}

/**
 * Guía de remisión de la devolución a proveedor.
 *
 * La mercadería que se le devuelve al proveedor viaja por la vía pública:
 * SUNAT no distingue el motivo para exigir la guía. Igual que la del
 * traslado, se pregunta al abrir si ya existe una — reenviar el formulario
 * no numera una segunda (RN-GDR-001..003).
 */
function DialogoGuia({ devolucion }: { devolucion: Devolucion }) {
  const [guia, setGuia] = useState<GuiaRemision | null | undefined>(undefined);
  const [errorCarga, setErrorCarga] = useState("");

  async function cargar() {
    setErrorCarga("");
    setGuia(undefined);
    try {
      const detalle = await pedir<GuiaRemision>(
        `/inventory/devoluciones/${devolucion.id}/guia-remision`,
      );
      setGuia(detalle);
    } catch (e) {
      if (e instanceof ErrorApi && e.status === 404) {
        setGuia(null);
        return;
      }
      setGuia(null);
      setErrorCarga("No se pudo consultar si la devolución ya tiene guía.");
    }
  }

  const yaEmitida = guia != null;

  return (
    <DialogoFormulario
      titulo="Guía de remisión"
      disparador="Guía"
      claseDisparador="text-xs font-semibold text-primary hover:underline"
      etiquetaEnvio="Emitir"
      etiquetaPendiente="Emitiendo..."
      accion={emitirGuiaDevolucionAction}
      ancho="max-w-lg"
      ayuda="Lo que se devuelve sale del almacén por la vía pública. Lo que se teclea es lo que el sistema no puede saber: a dónde va, quién maneja y en qué vehículo."
      alAbrir={cargar}
      envioDeshabilitado={yaEmitida || guia === undefined}
    >
      <input type="hidden" name="devolucion_id" value={devolucion.id} />
      {errorCarga && (
        <p role="alert" className="text-sm font-semibold text-status-danger">
          {errorCarga}
        </p>
      )}
      {guia === undefined && !errorCarga && (
        <p className="text-sm text-muted-foreground">Consultando...</p>
      )}
      {yaEmitida && guia && (
        <div className="flex items-center gap-2 text-sm">
          <span className="font-semibold">
            {guia.serie}-{String(guia.correlativo).padStart(8, "0")}
          </span>
          <Insignia tono={TONO_GUIA[guia.estado_emision] ?? "neutro"}>
            {guia.estado_emision}
          </Insignia>
        </div>
      )}
      {guia === null && !errorCarga && (
        <>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Lugar de destino
            <input name="lugar_destino" required minLength={3} maxLength={255} />
          </label>
          <div className="grid grid-cols-2 gap-4">
            <label className="flex flex-col gap-1 text-xs font-semibold">
              Chofer — nombres
              <input name="chofer_nombres" required minLength={2} maxLength={120} />
            </label>
            <label className="flex flex-col gap-1 text-xs font-semibold">
              Chofer — apellidos
              <input name="chofer_apellidos" required minLength={2} maxLength={120} />
            </label>
            <label className="flex flex-col gap-1 text-xs font-semibold">
              Documento
              <input name="chofer_num_doc" required minLength={8} maxLength={15} />
            </label>
            <label className="flex flex-col gap-1 text-xs font-semibold">
              Licencia
              <input name="chofer_licencia" required minLength={6} maxLength={20} />
            </label>
            <label className="flex flex-col gap-1 text-xs font-semibold">
              Vehículo registrado (Activos) — opcional
              <input name="vehiculo_id" placeholder="uuid del vehículo" />
            </label>
            <label className="flex flex-col gap-1 text-xs font-semibold">
              Placa del vehículo (si no eliges uno registrado)
              <input name="vehiculo_placa" minLength={6} maxLength={10} />
            </label>
            <label className="flex flex-col gap-1 text-xs font-semibold">
              Peso bruto (kg)
              <input name="peso_bruto_kg" type="number" min="0.001" step="0.001" required />
            </label>
            <label className="flex flex-col gap-1 text-xs font-semibold">
              Inicio del traslado
              <input name="fecha_inicio_traslado" type="date" />
            </label>
          </div>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Observación
            <input name="observacion" maxLength={500} />
          </label>
        </>
      )}
    </DialogoFormulario>
  );
}
