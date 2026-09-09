"use client";

import { useActionState } from "react";

import { DialogoFormulario, ESTADO_INICIAL } from "@/components/formulario/dialogo-formulario";
import { Insignia } from "@/components/estado/insignia";

import type { Activo } from "../activos-cliente";
import {
  agregarRepuestoCompatibleAction,
  cancelarOrdenAction,
  crearDocumentoAction,
  crearOrdenAction,
  crearPlanAction,
  darBajaActivoAction,
  iniciarOrdenAction,
  quitarRepuestoCompatibleAction,
  realizarOrdenAction,
  registrarCargaAction,
  registrarLecturaAction,
  renovarDocumentoAction,
} from "./actions";

export type PlanMantenimiento = {
  id: string;
  nombre: string;
  cada_dias: number | null;
  cada_km: number | null;
  estado: string | null;
  proxima_fecha: string | null;
  proximo_km: number | null;
};

export type OrdenMantenimiento = {
  id: string;
  tipo: string;
  estado: string;
  fecha_programada: string | null;
  fecha_realizada: string | null;
  descripcion: string | null;
  costo: string | null;
};

export type Documento = {
  id: string;
  tipo_documento: string;
  numero: string | null;
  fecha_vencimiento: string;
  estado: string | null;
  renovado_por_id: string | null;
};

export type LecturaOdometro = { id: string; fecha: string; km: number; origen: string };

export type CargaCombustible = {
  id: string;
  fecha: string;
  galones: string;
  monto: string;
  km_odometro: number;
  rendimiento_km_gal: string | null;
  anomalo: boolean;
};

export type ResumenConsumo = {
  cargas: number;
  promedio_km_gal: string | null;
  anomalas: number;
};

export type RepuestoCompatible = {
  id: string;
  articulo_id: string;
  notas: string | null;
};

export type ComprobanteDisponible = {
  id: string;
  emisor_num_doc: string | null;
  tipo: string;
  serie: string;
  correlativo: number;
  fecha_emision: string | null;
  total: string | null;
};

const TIPOS_DOCUMENTO = [
  ["soat", "SOAT"],
  ["revision_tecnica", "Revisión técnica"],
  ["tarjeta_propiedad", "Tarjeta de propiedad"],
  ["poliza_seguro", "Póliza de seguro"],
  ["garantia", "Garantía"],
  ["licencia_funcionamiento", "Licencia de funcionamiento"],
  ["certificado_defensa_civil", "Certificado de Defensa Civil"],
  ["fumigacion", "Fumigación"],
  ["registro_sanitario", "Registro sanitario"],
  ["carne_sanidad", "Carné de sanidad"],
  ["licencia_conducir", "Licencia de conducir"],
  ["otro", "Otro"],
] as const;

function Seccion({
  titulo,
  accion,
  children,
}: {
  titulo: string;
  accion?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-base text-dark">{titulo}</h2>
        {accion}
      </div>
      {children}
    </section>
  );
}

function EstadoDerivadoInsignia({ estado }: { estado: string | null }) {
  if (estado === "vencido") return <Insignia tono="peligro">Vencido</Insignia>;
  if (estado === "proximo") return <Insignia tono="alerta">Próximo</Insignia>;
  if (estado === "renovado") return <Insignia tono="neutro">Renovado</Insignia>;
  return <Insignia tono="exito">Al día</Insignia>;
}

function EstadoActivoInsignia({ estado }: { estado: string }) {
  if (estado === "de_baja") return <Insignia tono="neutro">De baja</Insignia>;
  if (estado === "en_mantenimiento") return <Insignia tono="alerta">En mantenimiento</Insignia>;
  return <Insignia tono="exito">Operativo</Insignia>;
}

/** Botón que dispara una acción sin formulario que llenar, mismo patrón que
 * `orden-compra-cliente.tsx`. */
function BotonAccion({
  ocultos,
  accion,
  etiqueta,
  confirmacion,
}: {
  ocultos: Record<string, string>;
  accion: typeof iniciarOrdenAction;
  etiqueta: string;
  confirmacion?: string;
}) {
  const [estado, formAction, pendiente] = useActionState(accion, ESTADO_INICIAL);
  return (
    <form
      action={formAction}
      onSubmit={(e) => {
        if (confirmacion && !confirm(confirmacion)) e.preventDefault();
      }}
      className="inline-flex flex-col gap-1"
    >
      {Object.entries(ocultos).map(([nombre, valor]) => (
        <input key={nombre} type="hidden" name={nombre} value={valor} />
      ))}
      <button
        type="submit"
        disabled={pendiente}
        className="rounded-md border border-border px-2 py-1 text-xs font-medium text-foreground transition-colors hover:bg-muted disabled:opacity-50"
      >
        {pendiente ? "…" : etiqueta}
      </button>
      {estado.error && <p className="text-xs font-medium text-status-danger">{estado.error}</p>}
    </form>
  );
}

function CabeceraActivo({ activo }: { activo: Activo }) {
  const esVehiculo = activo.tipo === "vehiculo";
  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="font-heading text-xl text-dark">{activo.nombre}</h1>
        <p className="text-sm text-muted-foreground">
          {activo.id_interno} ·{" "}
          {esVehiculo ? `Vehículo · ${activo.vehiculo?.placa}` : "Equipamiento"}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <EstadoActivoInsignia estado={activo.estado} />
        {activo.estado !== "de_baja" && (
          <DialogoFormulario
            titulo="Dar de baja el activo"
            disparador="Dar de baja"
            etiquetaEnvio="Confirmar"
            accion={darBajaActivoAction}
          >
            <input type="hidden" name="activo_id" value={activo.id} />
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Motivo
              <textarea name="motivo" required rows={3} />
            </label>
          </DialogoFormulario>
        )}
      </div>
    </div>
  );
}

function DialogoNuevaCarga({
  activoId,
  comprobantesDisponibles,
  hoy,
}: {
  activoId: string;
  comprobantesDisponibles: ComprobanteDisponible[];
  hoy: string;
}) {
  return (
    <DialogoFormulario
      titulo="Registrar carga de combustible"
      disparador="+ Combustible"
      ayuda="El comprobante se compra primero en Compras (compra directa); acá solo se liga."
      accion={registrarCargaAction}
    >
      <input type="hidden" name="activo_id" value={activoId} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Comprobante recibido
        <select name="comprobante_id" required defaultValue="">
          <option value="" disabled>
            Elegir…
          </option>
          {comprobantesDisponibles.map((c) => (
            <option key={c.id} value={c.id}>
              {c.tipo} {c.serie}-{c.correlativo}
              {c.total ? ` · S/ ${c.total}` : ""}
            </option>
          ))}
        </select>
      </label>
      {comprobantesDisponibles.length === 0 && (
        <p className="text-xs text-muted-foreground">
          No hay comprobantes sin usar. Regístralo primero en Compras → Compra directa.
        </p>
      )}
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Fecha
        <input name="fecha" type="date" defaultValue={hoy} required />
      </label>
      <div className="flex gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Galones
          <input name="galones" type="number" step="0.001" min={0} required />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Monto (S/)
          <input name="monto" type="number" step="0.01" min={0} required />
        </label>
      </div>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Kilometraje al cargar
        <input name="km_odometro" type="number" min={0} required />
      </label>
    </DialogoFormulario>
  );
}

function TablaCargas({ cargas }: { cargas: CargaCombustible[] }) {
  if (cargas.length === 0) return null;
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-xs text-muted-foreground">
          <th className="py-1">Fecha</th>
          <th>Galones</th>
          <th>Monto</th>
          <th>Km</th>
          <th>Rendimiento</th>
        </tr>
      </thead>
      <tbody>
        {cargas.map((c) => (
          <tr key={c.id} className={c.anomalo ? "text-status-danger" : ""}>
            <td className="py-1">{c.fecha}</td>
            <td>{c.galones}</td>
            <td>S/ {c.monto}</td>
            <td>{c.km_odometro}</td>
            <td>
              {c.rendimiento_km_gal ?? "—"} {c.anomalo && "⚠"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SeccionCombustible({
  activo,
  lecturas,
  cargas,
  consumo,
  comprobantesDisponibles,
  hoy,
}: {
  activo: Activo;
  lecturas: LecturaOdometro[];
  cargas: CargaCombustible[];
  consumo: ResumenConsumo | null;
  comprobantesDisponibles: ComprobanteDisponible[];
  hoy: string;
}) {
  return (
    <Seccion
      titulo="Kilometraje y combustible"
      accion={
        <div className="flex gap-2">
          <DialogoFormulario
            titulo="Registrar kilometraje"
            disparador="+ Kilometraje"
            accion={registrarLecturaAction}
          >
            <input type="hidden" name="activo_id" value={activo.id} />
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Kilometraje
              <input name="km" type="number" min={0} required />
            </label>
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Fecha
              <input name="fecha" type="date" defaultValue={hoy} required />
            </label>
          </DialogoFormulario>
          <DialogoNuevaCarga
            activoId={activo.id}
            comprobantesDisponibles={comprobantesDisponibles}
            hoy={hoy}
          />
        </div>
      }
    >
      <p className="text-sm text-muted-foreground">
        Kilometraje actual: <strong>{activo.vehiculo?.kilometraje_actual ?? "—"}</strong>
        {consumo?.promedio_km_gal && (
          <>
            {" "}
            · Rendimiento promedio: <strong>{consumo.promedio_km_gal} km/gal</strong>
          </>
        )}
        {consumo && consumo.anomalas > 0 && (
          <>
            {" "}
            · <span className="text-status-danger">{consumo.anomalas} carga(s) anómala(s)</span>
          </>
        )}
      </p>
      <TablaCargas cargas={cargas} />
      {lecturas.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-muted-foreground">
            Historial de kilometraje ({lecturas.length})
          </summary>
          <ul className="mt-2 flex flex-col gap-1">
            {lecturas.map((l) => (
              <li key={l.id} className="text-xs text-muted-foreground">
                {l.fecha} · {l.km} km · {l.origen}
              </li>
            ))}
          </ul>
        </details>
      )}
    </Seccion>
  );
}

function DialogoNuevoPlan({ activoId, esVehiculo }: { activoId: string; esVehiculo: boolean }) {
  return (
    <DialogoFormulario titulo="Nuevo plan de mantenimiento" disparador="+ Plan" accion={crearPlanAction}>
      <input type="hidden" name="activo_id" value={activoId} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input name="nombre" required maxLength={150} />
      </label>
      <div className="flex gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Cada (días)
          <input name="cada_dias" type="number" min={1} />
        </label>
        {esVehiculo && (
          <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
            Cada (km)
            <input name="cada_km" type="number" min={1} />
          </label>
        )}
      </div>
      <p className="text-xs text-muted-foreground">Indica al menos una frecuencia.</p>
      <div className="flex gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Aviso (días antes)
          <input name="dias_aviso" type="number" min={0} placeholder="15" />
        </label>
        {esVehiculo && (
          <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
            Aviso (km antes)
            <input name="km_aviso" type="number" min={0} placeholder="500" />
          </label>
        )}
      </div>
    </DialogoFormulario>
  );
}

function SeccionPlanes({
  activo,
  planes,
}: {
  activo: Activo;
  planes: PlanMantenimiento[];
}) {
  return (
    <Seccion
      titulo="Planes de mantenimiento"
      accion={<DialogoNuevoPlan activoId={activo.id} esVehiculo={activo.tipo === "vehiculo"} />}
    >
      {planes.length === 0 ? (
        <p className="text-sm text-muted-foreground">Sin planes registrados.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {planes.map((p) => (
            <li key={p.id} className="flex items-center justify-between text-sm">
              <span>
                {p.nombre}
                {p.cada_dias && ` · cada ${p.cada_dias} días`}
                {p.cada_km && ` · cada ${p.cada_km} km`}
                {p.proxima_fecha && ` · próxima: ${p.proxima_fecha}`}
                {p.proximo_km && ` (${p.proximo_km} km)`}
              </span>
              <EstadoDerivadoInsignia estado={p.estado} />
            </li>
          ))}
        </ul>
      )}
    </Seccion>
  );
}

function DialogoNuevaOrden({
  activoId,
  planes,
}: {
  activoId: string;
  planes: PlanMantenimiento[];
}) {
  return (
    <DialogoFormulario titulo="Nueva orden de mantenimiento" disparador="+ Orden" accion={crearOrdenAction}>
      <input type="hidden" name="activo_id" value={activoId} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Tipo
        <select name="tipo" defaultValue="programado">
          <option value="programado">Programado (de un plan)</option>
          <option value="adelantado">Adelantado (avería)</option>
        </select>
      </label>
      {planes.length > 0 && (
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Plan (opcional)
          <select name="plan_id" defaultValue="">
            <option value="">Ninguno</option>
            {planes.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nombre}
              </option>
            ))}
          </select>
        </label>
      )}
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Motivo del adelanto
        <select name="motivo_adelanto" defaultValue="">
          <option value="">—</option>
          <option value="desperfecto">Desperfecto</option>
          <option value="baja_productividad">Baja productividad</option>
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Descripción
        <textarea name="descripcion" rows={2} />
      </label>
    </DialogoFormulario>
  );
}

function EstadoOrdenInsignia({ estado }: { estado: string }) {
  if (estado === "realizada") return <Insignia tono="exito">realizada</Insignia>;
  if (estado === "cancelada") return <Insignia tono="neutro">cancelada</Insignia>;
  if (estado === "en_curso") return <Insignia tono="alerta">en_curso</Insignia>;
  return <Insignia tono="info">programada</Insignia>;
}

function DialogoRealizarOrden({
  orden,
  activo,
  hoy,
}: {
  orden: OrdenMantenimiento;
  activo: Activo;
  hoy: string;
}) {
  return (
    <DialogoFormulario
      titulo="Registrar mantenimiento realizado"
      disparador="Realizar"
      claseDisparador="rounded-md border border-border px-2 py-1 text-xs font-medium text-foreground transition-colors hover:bg-muted"
      accion={realizarOrdenAction}
    >
      <input type="hidden" name="orden_id" value={orden.id} />
      <input type="hidden" name="activo_id" value={activo.id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Fecha realizada
        <input name="fecha_realizada" type="date" defaultValue={hoy} required />
      </label>
      {activo.tipo === "vehiculo" && (
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Kilometraje
          <input name="km_al_realizar" type="number" min={0} />
        </label>
      )}
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Resultado
        <textarea name="resultado" rows={2} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Costo (S/)
        <input name="costo" type="number" step="0.01" min={0} />
      </label>
      <p className="text-xs text-muted-foreground">
        Repuesto usado (opcional) — descuenta stock de Inventario.
      </p>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        ID del artículo (repuesto)
        <input name="repuesto_articulo_id" placeholder="uuid del artículo" />
      </label>
      <div className="flex gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Cantidad
          <input name="repuesto_cantidad" type="number" step="0.001" min={0} />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Almacén de salida
          <input name="almacen_id" placeholder="uuid del almacén" />
        </label>
      </div>
    </DialogoFormulario>
  );
}

/** Acciones disponibles de una orden — separado del listado para que el
 * `.map()` que la dibuja no acumule toda la ramificación de estados. */
function AccionesOrden({ orden, activo, hoy }: { orden: OrdenMantenimiento; activo: Activo; hoy: string }) {
  const abierta = orden.estado === "programada" || orden.estado === "en_curso";
  if (!abierta) return null;
  return (
    <>
      {orden.estado === "programada" && (
        <BotonAccion
          ocultos={{ orden_id: orden.id, activo_id: activo.id }}
          accion={iniciarOrdenAction}
          etiqueta="Iniciar"
        />
      )}
      <DialogoRealizarOrden orden={orden} activo={activo} hoy={hoy} />
      <BotonAccion
        ocultos={{ orden_id: orden.id, activo_id: activo.id, motivo: "Cancelada desde la ficha" }}
        accion={cancelarOrdenAction}
        etiqueta="Cancelar"
        confirmacion="¿Cancelar esta orden de mantenimiento?"
      />
    </>
  );
}

function FilaOrden({ orden, activo, hoy }: { orden: OrdenMantenimiento; activo: Activo; hoy: string }) {
  return (
    <li className="flex items-center justify-between gap-2 text-sm">
      <span>
        {orden.tipo} · {orden.descripcion ?? "sin descripción"}
        {orden.fecha_realizada && ` · realizada ${orden.fecha_realizada}`}
      </span>
      <div className="flex items-center gap-2">
        <EstadoOrdenInsignia estado={orden.estado} />
        <AccionesOrden orden={orden} activo={activo} hoy={hoy} />
      </div>
    </li>
  );
}

function SeccionOrdenes({
  activo,
  planes,
  ordenes,
  hoy,
}: {
  activo: Activo;
  planes: PlanMantenimiento[];
  ordenes: OrdenMantenimiento[];
  hoy: string;
}) {
  return (
    <Seccion
      titulo="Órdenes de mantenimiento"
      accion={<DialogoNuevaOrden activoId={activo.id} planes={planes} />}
    >
      {ordenes.length === 0 ? (
        <p className="text-sm text-muted-foreground">Sin órdenes registradas.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {ordenes.map((o) => (
            <FilaOrden key={o.id} orden={o} activo={activo} hoy={hoy} />
          ))}
        </ul>
      )}
    </Seccion>
  );
}

function DialogoNuevoRepuesto({ activoId }: { activoId: string }) {
  return (
    <DialogoFormulario
      titulo="Repuesto compatible"
      disparador="+ Repuesto"
      accion={agregarRepuestoCompatibleAction}
    >
      <input type="hidden" name="activo_id" value={activoId} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        ID del artículo (Inventario)
        <input name="articulo_id" required placeholder="uuid del artículo" />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Notas
        <input name="notas" maxLength={255} />
      </label>
    </DialogoFormulario>
  );
}

function SeccionRepuestos({
  activo,
  repuestos,
}: {
  activo: Activo;
  repuestos: RepuestoCompatible[];
}) {
  return (
    <Seccion
      titulo="Repuestos compatibles"
      accion={<DialogoNuevoRepuesto activoId={activo.id} />}
    >
      {repuestos.length === 0 ? (
        <p className="text-sm text-muted-foreground">Sin repuestos sugeridos todavía.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {repuestos.map((r) => (
            <li key={r.id} className="flex items-center justify-between gap-2 text-sm">
              <span>
                {r.articulo_id}
                {r.notas && ` · ${r.notas}`}
              </span>
              <BotonAccion
                ocultos={{ activo_id: activo.id, repuesto_id: r.id }}
                accion={quitarRepuestoCompatibleAction}
                etiqueta="Quitar"
              />
            </li>
          ))}
        </ul>
      )}
    </Seccion>
  );
}

function DialogoNuevoDocumento({ activoId }: { activoId: string }) {
  return (
    <DialogoFormulario titulo="Nuevo documento" disparador="+ Documento" accion={crearDocumentoAction}>
      <input type="hidden" name="activo_id" value={activoId} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Tipo de documento
        <select name="tipo_documento" required defaultValue="">
          <option value="" disabled>
            Elegir…
          </option>
          {TIPOS_DOCUMENTO.map(([valor, etiqueta]) => (
            <option key={valor} value={valor}>
              {etiqueta}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Número
        <input name="numero" maxLength={60} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Emisor
        <input name="emisor" maxLength={120} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Fecha de vencimiento
        <input name="fecha_vencimiento" type="date" required />
      </label>
    </DialogoFormulario>
  );
}

function FilaDocumento({ documento, activoId }: { documento: Documento; activoId: string }) {
  return (
    <li className="flex items-center justify-between gap-2 text-sm">
      <span>
        {TIPOS_DOCUMENTO.find(([v]) => v === documento.tipo_documento)?.[1] ??
          documento.tipo_documento}
        {documento.numero && ` · ${documento.numero}`} · vence {documento.fecha_vencimiento}
      </span>
      <div className="flex items-center gap-2">
        <EstadoDerivadoInsignia estado={documento.estado} />
        {!documento.renovado_por_id && (
          <DialogoFormulario
            titulo="Renovar documento"
            disparador="Renovar"
            claseDisparador="rounded-md border border-border px-2 py-1 text-xs font-medium text-foreground transition-colors hover:bg-muted"
            accion={renovarDocumentoAction}
          >
            <input type="hidden" name="documento_id" value={documento.id} />
            <input type="hidden" name="activo_id" value={activoId} />
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Número nuevo (opcional)
              <input name="numero" maxLength={60} />
            </label>
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Nueva fecha de vencimiento
              <input name="fecha_vencimiento" type="date" required />
            </label>
          </DialogoFormulario>
        )}
      </div>
    </li>
  );
}

function SeccionDocumentos({ activo, documentos }: { activo: Activo; documentos: Documento[] }) {
  return (
    <Seccion titulo="Documentos con vencimiento" accion={<DialogoNuevoDocumento activoId={activo.id} />}>
      {documentos.length === 0 ? (
        <p className="text-sm text-muted-foreground">Sin documentos registrados.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {documentos.map((d) => (
            <FilaDocumento key={d.id} documento={d} activoId={activo.id} />
          ))}
        </ul>
      )}
    </Seccion>
  );
}

export function FichaActivoCliente({
  activo,
  planes,
  ordenes,
  documentos,
  lecturas,
  cargas,
  consumo,
  comprobantesDisponibles,
  repuestosCompatibles,
}: {
  activo: Activo;
  planes: PlanMantenimiento[];
  ordenes: OrdenMantenimiento[];
  documentos: Documento[];
  lecturas: LecturaOdometro[];
  cargas: CargaCombustible[];
  consumo: ResumenConsumo | null;
  comprobantesDisponibles: ComprobanteDisponible[];
  repuestosCompatibles: RepuestoCompatible[];
}) {
  const hoy = new Date().toISOString().slice(0, 10);

  return (
    <div className="flex flex-col gap-4">
      <CabeceraActivo activo={activo} />
      {activo.tipo === "vehiculo" && (
        <SeccionCombustible
          activo={activo}
          lecturas={lecturas}
          cargas={cargas}
          consumo={consumo}
          comprobantesDisponibles={comprobantesDisponibles}
          hoy={hoy}
        />
      )}
      <SeccionPlanes activo={activo} planes={planes} />
      <SeccionOrdenes activo={activo} planes={planes} ordenes={ordenes} hoy={hoy} />
      <SeccionRepuestos activo={activo} repuestos={repuestosCompatibles} />
      <SeccionDocumentos activo={activo} documentos={documentos} />
    </div>
  );
}
