"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";

import { Insignia } from "@/components/estado/insignia";
import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { Combobox } from "@/components/ui/combobox";
import { ErrorApi, pedir } from "@/lib/cliente-api";
import { tienePermiso } from "@/lib/permisos";

import { emitirGuiaAction, recibirTransferenciaAction, trasladoDirectoAction } from "./actions";

export type Transferencia = {
  id: string;
  origen_almacen_id: string;
  destino_almacen_id: string;
  solicitud_id: string | null;
  estado: string;
  observacion: string | null;
};
type TransferenciaItem = {
  id: string;
  sku_id: string;
  lote_id: string | null;
  cantidad_enviada: string;
  cantidad_recibida: string | null;
};
type TransferenciaDetalle = Transferencia & { items: TransferenciaItem[] };

type GuiaRemision = {
  id: string;
  serie: string;
  correlativo: number;
  estado_emision: string;
  detalle_emision: string | null;
};

export type OpcionSku = { id: string; etiqueta: string };

const TONO: Record<string, "exito" | "peligro" | "neutro"> = {
  en_transito: "peligro",
  recibida: "exito",
};

const TONO_GUIA: Record<string, "exito" | "alerta" | "peligro" | "info" | "neutro"> = {
  pendiente: "info",
  aceptado: "exito",
  rechazado: "peligro",
  error: "alerta",
};

/**
 * Traslados entre almacenes: lo que ya salió y todavía no llegó.
 *
 * La pantalla que faltaba. `despachar` y `recibir` existían en la API desde
 * el slice de transferencias y **ninguna** pantalla las llamaba: lo
 * despachado quedaba `en_transito` para siempre y el almacén que lo había
 * pedido no tenía dónde decir "llegó".
 *
 * Lo que faltaba después (auditoría del 2026-08-30, bloque
 * `feat/inventario-transferencias-mermas`): la recepción se mandaba con
 * `{items: [], parcial: false}` clavado, así que el camión que trae la mitad
 * —o el bulto que llegó roto— no tenía cómo declararse; y el traslado
 * lateral, sin requerimiento previo, no tenía por dónde crearse.
 */
export function TransferenciasCliente({
  transferencias,
  nombreDeAlmacen,
  skus,
  permisos,
}: {
  transferencias: Transferencia[];
  nombreDeAlmacen: Record<string, string>;
  skus: OpcionSku[];
  permisos: string[];
}) {
  const puedeRecibir = tienePermiso(permisos, "inventory.recepcion");
  const puedeTransferir = tienePermiso(permisos, "inventory.transferir");
  const puedeEmitirGuia = tienePermiso(permisos, "inventory.emitir_guia");

  const nombreDeSku = useMemo(
    () => new Map(skus.map((s) => [s.id, s.etiqueta])),
    [skus],
  );

  const columnas = useMemo<ColumnDef<Transferencia>[]>(
    () => [
      {
        header: "Sale de",
        accessorFn: (t) => nombreDeAlmacen[t.origen_almacen_id] ?? "—",
      },
      {
        header: "Va a",
        accessorFn: (t) => nombreDeAlmacen[t.destino_almacen_id] ?? "—",
      },
      {
        header: "Origen",
        accessorFn: (t) => (t.solicitud_id ? "Requerimiento" : "Traslado directo"),
      },
      {
        header: "Estado",
        accessorKey: "estado",
        cell: ({ row }) => (
          <Insignia tono={TONO[row.original.estado] ?? "neutro"}>
            {row.original.estado === "en_transito"
              ? "En tránsito"
              : row.original.estado}
          </Insignia>
        ),
      },
      {
        header: "Observación",
        accessorFn: (t) => t.observacion ?? "—",
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => (
          <div className="flex items-center gap-3">
            {row.original.estado === "en_transito" && puedeRecibir && (
              <DialogoRecibir transferencia={row.original} nombreDeSku={nombreDeSku} />
            )}
            {puedeEmitirGuia && <DialogoGuia transferencia={row.original} />}
          </div>
        ),
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [puedeRecibir, puedeEmitirGuia, nombreDeAlmacen, skus],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-heading text-xl italic uppercase text-dark">
            Traslados
          </h1>
          <p className="text-xs text-gray">
            Lo que salió de un almacén hacia otro. Mientras está en tránsito el
            stock ya no está en el origen y todavía no está en el destino: lo
            pone ahí quien lo recibe.
          </p>
        </div>
        {puedeTransferir && (
          <DialogoTrasladoDirecto nombreDeAlmacen={nombreDeAlmacen} skus={skus} />
        )}
      </div>

      <TablaDatos
        columnas={columnas}
        datos={transferencias}
        placeholderBusqueda="Buscar por almacén o estado..."
        vacio="No hay traslados todavía. Se crean al despachar un requerimiento aprobado, o desde «Traslado directo»."
      />
    </div>
  );
}

/**
 * Recibir: qué llegó de lo que se envió, línea por línea.
 *
 * El detalle se pide **antes** de abrir (`GET /transferencias/{id}`, que no
 * tenía ningún llamador): sin él la pantalla no puede decir qué trae el
 * traslado, y quien recibe estaba firmando a ciegas. Viene precargado con lo
 * enviado, que es el caso normal — teclear de nuevo lo que el sistema ya
 * sabe es donde se equivoca quien está apurado en el andén.
 */
function DialogoRecibir({
  transferencia,
  nombreDeSku,
}: {
  transferencia: Transferencia;
  nombreDeSku: Map<string, string>;
}) {
  const [items, setItems] = useState<TransferenciaItem[]>([]);
  const [errorCarga, setErrorCarga] = useState("");

  async function cargar() {
    setErrorCarga("");
    try {
      const detalle = await pedir<TransferenciaDetalle>(
        `/inventory/transferencias/${transferencia.id}`,
      );
      setItems(detalle.items ?? []);
    } catch {
      setItems([]);
      setErrorCarga("No se pudo cargar el detalle del traslado.");
    }
  }

  return (
    <DialogoFormulario
      titulo="Qué llegó"
      disparador="Recibir"
      claseDisparador="rounded bg-primary px-3 py-1 text-xs font-bold text-primary-foreground"
      etiquetaEnvio="Recibir"
      etiquetaPendiente="Recibiendo..."
      accion={recibirTransferenciaAction}
      ancho="max-w-2xl"
      ayuda="Viene precargado con lo que se envió. Corrige la cantidad si llegó menos y marca «entrega parcial» si el resto sigue en camino; sin marcarla, la diferencia se registra como faltante."
      alAbrir={cargar}
    >
      <input type="hidden" name="transferencia_id" value={transferencia.id} />
      {errorCarga && (
        <p role="alert" className="text-sm font-semibold text-status-danger">
          {errorCarga}
        </p>
      )}
      <div className="flex flex-col gap-2">
        {items.map((it) => (
          <div key={it.id} className="flex items-end gap-2">
            <input type="hidden" name="item_id" value={it.id} />
            <span className="flex-1 text-sm">
              {nombreDeSku.get(it.sku_id) ?? it.sku_id}
              <span className="ml-2 text-xs text-muted-foreground">
                enviado {it.cantidad_enviada}
              </span>
            </span>
            <label className="flex w-32 flex-col gap-1 text-xs font-semibold">
              Llegó
              <input
                name="cantidad"
                type="number"
                min="0"
                step="0.0001"
                defaultValue={it.cantidad_enviada}
              />
            </label>
          </div>
        ))}
      </div>
      <label className="flex items-start gap-2 text-sm font-semibold">
        <input type="checkbox" name="parcial" className="mt-1" />
        <span>
          Entrega parcial
          <span className="block text-xs font-normal text-muted-foreground">
            El resto sigue en camino y el traslado queda abierto. Sin marcarla,
            lo que falte se registra como diferencia contra lo enviado
            (RN-INV-002).
          </span>
        </span>
      </label>
    </DialogoFormulario>
  );
}

type LineaTraslado = { clave: number; sku: string; cantidad: string };

const LINEAS_INICIALES: LineaTraslado[] = [{ clave: 1, sku: "", cantidad: "" }];

/**
 * Traslado directo: de un almacén a otro sin requerimiento de por medio.
 *
 * El backend lo admite desde el primer día —`solicitud_id` es opcional— y no
 * había por dónde crearlo: la única llamada a `POST /transferencias` salía
 * del despacho de un requerimiento aprobado. Es la sucursal que le presta
 * harina a la de al lado, que hasta hoy se resolvía sin registrar nada.
 */
function DialogoTrasladoDirecto({
  nombreDeAlmacen,
  skus,
}: {
  nombreDeAlmacen: Record<string, string>;
  skus: OpcionSku[];
}) {
  const [lineas, setLineas] = useState<LineaTraslado[]>(LINEAS_INICIALES);
  const almacenes = Object.entries(nombreDeAlmacen).map(([valor, etiqueta]) => ({
    valor,
    etiqueta,
  }));

  const editar = (clave: number, campo: keyof LineaTraslado, valor: string) =>
    setLineas((prev) => prev.map((l) => (l.clave === clave ? { ...l, [campo]: valor } : l)));

  return (
    <DialogoFormulario
      titulo="Traslado directo"
      disparador="+ Traslado directo"
      etiquetaEnvio="Despachar"
      etiquetaPendiente="Despachando..."
      accion={trasladoDirectoAction}
      ancho="max-w-2xl"
      ayuda="Sin requerimiento previo: el stock sale del origen ahora y entra al destino cuando alguien lo reciba. Para lo que sí se pidió, el despacho sale de la ficha del requerimiento."
      envioDeshabilitado={almacenes.length < 2 || skus.length === 0}
      alAbrir={() => setLineas(LINEAS_INICIALES)}
    >
      <div className="grid grid-cols-2 gap-4">
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Sale de
          <Combobox
            name="origen_almacen_id"
            etiqueta="Sale de"
            requerido
            marcador="Elegir…"
            opciones={almacenes}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Va a
          <Combobox
            name="destino_almacen_id"
            etiqueta="Va a"
            requerido
            marcador="Elegir…"
            opciones={almacenes}
          />
        </label>
      </div>

      <div className="flex flex-col gap-2">
        {lineas.map((linea) => (
          <div key={linea.clave} className="flex items-end gap-2">
            <label className="flex flex-1 flex-col gap-1 text-xs font-semibold">
              Qué se manda
              <Combobox
                name="sku_id"
                etiqueta="Qué se manda"
                requerido
                marcador="Elegir…"
                value={linea.sku}
                alCambiar={(v) => editar(linea.clave, "sku", v ?? "")}
                opciones={skus.map((s) => ({ valor: s.id, etiqueta: s.etiqueta }))}
              />
            </label>
            <label className="flex w-32 flex-col gap-1 text-xs font-semibold">
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
              { clave: Math.max(...prev.map((l) => l.clave)) + 1, sku: "", cantidad: "" },
            ])
          }
          className="self-start text-sm font-semibold text-primary hover:underline"
        >
          + Agregar artículo
        </button>
      </div>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Observación
        <input name="observacion" maxLength={500} placeholder="Por qué se manda, si hace falta" />
      </label>
    </DialogoFormulario>
  );
}

/**
 * Guía de remisión del traslado.
 *
 * Cuatro endpoints con ADR (ADR-027) y catorce pruebas sin un solo llamador
 * desde el frontend: quien despachaba un traslado no tenía dónde emitir la
 * guía que la ley exige para que la mercadería viaje por la vía pública.
 *
 * Al abrir se pregunta si ya existe una (`GET .../guia`): si el traslado ya
 * tiene guía se muestra su estado y, aceptada, los enlaces de descarga —
 * volver a enviar el formulario no numera una segunda, el servidor devuelve
 * la misma (RN-TRP-002). Si no existe, se muestra el formulario: lo único
 * que se teclea es lo que el sistema no puede saber.
 */
function DialogoGuia({ transferencia }: { transferencia: Transferencia }) {
  const [guia, setGuia] = useState<GuiaRemision | null | undefined>(undefined);
  const [errorCarga, setErrorCarga] = useState("");

  async function cargar() {
    setErrorCarga("");
    setGuia(undefined);
    try {
      const detalle = await pedir<GuiaRemision>(
        `/inventory/transferencias/${transferencia.id}/guia`,
      );
      setGuia(detalle);
    } catch (e) {
      if (e instanceof ErrorApi && e.status === 404) {
        setGuia(null);
        return;
      }
      setGuia(null);
      setErrorCarga("No se pudo consultar si el traslado ya tiene guía.");
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
      accion={emitirGuiaAction}
      ancho="max-w-lg"
      ayuda="Los bienes salen de la transferencia, no se teclean. Lo que sí se teclea es lo que el sistema no puede saber: quién maneja, en qué vehículo, cuánto pesa y qué día arranca el viaje."
      alAbrir={cargar}
      envioDeshabilitado={yaEmitida || guia === undefined}
    >
      <input type="hidden" name="transferencia_id" value={transferencia.id} />
      {errorCarga && (
        <p role="alert" className="text-sm font-semibold text-status-danger">
          {errorCarga}
        </p>
      )}
      {guia === undefined && !errorCarga && (
        <p className="text-sm text-muted-foreground">Consultando...</p>
      )}
      {yaEmitida && guia && <ResumenGuia guia={guia} />}
      {guia === null && !errorCarga && <CamposGuia />}
    </DialogoFormulario>
  );
}

function ResumenGuia({ guia }: { guia: GuiaRemision }) {
  return (
    <div className="flex flex-col gap-2 text-sm">
      <p className="flex items-center gap-2">
        <span className="font-semibold">
          {guia.serie}-{String(guia.correlativo).padStart(8, "0")}
        </span>
        <Insignia tono={TONO_GUIA[guia.estado_emision] ?? "neutro"}>
          {guia.estado_emision}
        </Insignia>
      </p>
      {guia.detalle_emision && (
        <p className="text-xs text-muted-foreground">{guia.detalle_emision}</p>
      )}
      {guia.estado_emision === "aceptado" && (
        <div className="flex gap-3">
          {(["pdf", "xml", "cdr"] as const).map((formato) => (
            <a
              key={formato}
              href={`/api/proxy/api/v1/inventory/guias-remision/${guia.id}/descargar/${formato}`}
              title={formato === "cdr" ? "Constancia de recepción de SUNAT" : undefined}
              className="text-xs font-semibold text-primary hover:underline"
            >
              {formato.toUpperCase()}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

function CamposGuia() {
  return (
    <>
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
  );
}
