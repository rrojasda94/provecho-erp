"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { pedir } from "@/lib/cliente-api";
import { etiquetaDestino, rutaDestino } from "@/lib/destinos";
import { tienePermiso } from "@/lib/permisos";
import {
  CLASE_NIVEL,
  ETIQUETA_ESTADO,
  ETIQUETA_MOTIVO,
  ETIQUETA_NIVEL,
  MOTIVOS_ESCALAMIENTO,
  terminado,
  type Destino,
  type Emision,
  type Escalamiento,
  type ReporteEmitidoDetalle,
} from "@/lib/reports";

/** El motivo se persiste con el id crudo (`area:<uuid>`), no con el código
 * legible. Mostrar el uuid no le dice nada a nadie; el tipo sí explica por
 * qué llegó, que es la pregunta que contesta esta línea. */
const ETIQUETA_MOTIVO_ENTREGA: Record<string, string> = {
  area: "por su área",
  rol: "por su rol",
  usuario: "por nombre propio",
  dinamico: "por estar a cargo",
};

function motivoLegible(motivo: string): string {
  const [tipo] = motivo.split(":");
  return ETIQUETA_MOTIVO_ENTREGA[tipo] ?? motivo;
}

function Dato({ etiqueta, children }: { etiqueta: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs font-bold uppercase text-gray">{etiqueta}</dt>
      <dd className="text-sm text-dark">{children}</dd>
    </div>
  );
}

export function FichaReporte({
  reporte,
  emision,
  destino,
  escalamientos,
  permisos,
}: {
  reporte: ReporteEmitidoDetalle;
  emision: Emision | null;
  destino: Destino | null;
  escalamientos: Escalamiento[];
  permisos: string[];
}) {
  const router = useRouter();
  const abierto = escalamientos.find((e) => !terminado(e.estado));

  return (
    <section className="flex flex-col gap-6">
      <Link href="/reportes" className="text-sm font-semibold text-primary hover:underline">
        ← Mis reportes
      </Link>

      <Encabezado reporte={reporte} destino={destino} permisos={permisos} />

      <dl className="grid gap-4 rounded border border-gray/20 p-4 sm:grid-cols-3">
        <Dato etiqueta="Quién">
          {reporte.actor}
          {reporte.actor_id === null && (
            <span className="block text-xs text-gray">
              Lo detectó el ERP, no una persona.
            </span>
          )}
        </Dato>
        <Dato etiqueta="Hecho">{emision?.nombre ?? reporte.codigo_emision}</Dato>
        <Dato etiqueta="Cuándo">
          {new Date(reporte.emitido_at).toLocaleString("es-PE")}
        </Dato>
      </dl>

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-bold uppercase text-gray">Datos del hecho</h2>
        <dl className="grid gap-3 rounded border border-gray/20 p-4 sm:grid-cols-2">
          {Object.entries(reporte.datos).map(([clave, valor]) => (
            <Dato key={clave} etiqueta={clave.replace(/_/g, " ")}>
              {valor === null || valor === "" ? "—" : String(valor)}
            </Dato>
          ))}
        </dl>
      </section>

      <Entregas entregas={reporte.entregas} />

      <PanelEscalamiento
        reporteId={reporte.id}
        abierto={abierto ?? null}
        historial={escalamientos}
        permisos={permisos}
        onCambio={() => router.refresh()}
      />
    </section>
  );
}

function Encabezado({
  reporte,
  destino,
  permisos,
}: {
  reporte: ReporteEmitidoDetalle;
  destino: Destino | null;
  permisos: string[];
}) {
  // Un reporte de la propia cadena no ofrece botón: el escalamiento ya se ve
  // más abajo, en esta misma ficha. Además su permiso no se puede anticipar
  // —la lectura se gatea contra el módulo del reporte de origen, no contra
  // `reports.leer`— así que el botón sería el único enlace ciego que queda.
  const ruta =
    reporte.referencia_tipo === "escalamiento"
      ? null
      : rutaDestino(reporte.referencia_tipo, reporte.referencia_id);
  // Un botón visible para todos lleva a un 403: ser destinatario no da acceso
  // al dato del módulo dueño (RN-REP-002, ADR-033).
  const puedeIr = ruta !== null && (!destino || tienePermiso(permisos, destino.permiso));

  return (
    <header className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-3">
        <span
          className={`rounded px-2 py-0.5 text-xs font-bold ${
            CLASE_NIVEL[reporte.nivel] ?? ""
          }`}
        >
          {reporte.nivel}
        </span>
        <h1 className="font-heading text-xl italic uppercase text-dark">
          {reporte.titulo}
        </h1>
      </div>
      {reporte.cuerpo && <p className="text-secondary">{reporte.cuerpo}</p>}
      <BotonDestino
        ruta={ruta}
        puedeIr={puedeIr}
        etiqueta={destino?.etiqueta ?? etiquetaDestino(reporte.referencia_tipo)}
      />
    </header>
  );
}

/** El botón que faltaba: sin él el reporte cuenta qué pasó y deja al lector
 * saliendo a buscar dónde arreglarlo. */
function BotonDestino({
  ruta,
  puedeIr,
  etiqueta,
}: {
  ruta: string | null;
  puedeIr: boolean;
  etiqueta: string;
}) {
  if (ruta === null) return null;
  if (!puedeIr) {
    return (
      <p className="text-sm text-gray">
        Este reporte apunta a un dato que tu usuario no tiene permiso de abrir.
      </p>
    );
  }
  return (
    <Link
      href={ruta}
      className="w-fit rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
    >
      {etiqueta} →
    </Link>
  );
}

function Entregas({ entregas }: { entregas: ReporteEmitidoDetalle["entregas"] }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-bold uppercase text-gray">A quién le llegó</h2>
      {entregas.length === 0 ? (
        <p className="text-sm text-secondary">
          A nadie: no había ninguna regla de distribución que lo cubriera. Sale
          como hueco en la matriz.
        </p>
      ) : (
        <ul className="flex flex-col gap-1 rounded border border-gray/20 p-4">
          {entregas.map((e) => (
            <li key={e.usuario_id} className="text-sm">
              <span className="font-semibold">{e.usuario}</span>{" "}
              <span className="text-gray">{motivoLegible(e.motivo)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function PanelEscalamiento({
  reporteId,
  abierto,
  historial,
  permisos,
  onCambio,
}: {
  reporteId: string;
  abierto: Escalamiento | null;
  historial: Escalamiento[];
  permisos: string[];
  onCambio: () => void;
}) {
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const puedeEscalar = tienePermiso(permisos, "reports.escalar");
  const puedeResolver = tienePermiso(permisos, "reports.escalamiento_resolver");

  async function enviar(fn: () => Promise<unknown>) {
    setEnviando(true);
    setError("");
    try {
      await fn();
      onCambio();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo completar la acción.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-bold uppercase text-gray">Escalamiento</h2>

      {abierto ? (
        <CadenaAbierta
          escalamiento={abierto}
          puedeEscalar={puedeEscalar}
          puedeResolver={puedeResolver}
          enviando={enviando}
          onAccion={(ruta, descripcion) =>
            enviar(() => pedir(rutaAccion(abierto.id, ruta), {
              metodo: "POST",
              cuerpo: { descripcion },
            }))
          }
        />
      ) : puedeEscalar ? (
        <FormularioApertura
          enviando={enviando}
          onAbrir={(motivo, descripcion) =>
            enviar(() =>
              pedir(`/reports/emitidos/${reporteId}/escalamientos`, {
                metodo: "POST",
                cuerpo: { motivo, descripcion },
              }),
            )
          }
        />
      ) : (
        <p className="text-sm text-secondary">
          Sin escalamiento abierto. Tu usuario no tiene permiso para elevarlo.
        </p>
      )}

      {error && (
        <p role="alert" className="text-sm font-semibold text-secondary">
          {error}
        </p>
      )}

      {historial.filter((e) => terminado(e.estado)).length > 0 && (
        <details className="rounded border border-gray/20 p-4">
          <summary className="cursor-pointer text-sm font-semibold">
            Escalamientos anteriores (
            {historial.filter((e) => terminado(e.estado)).length})
          </summary>
          <ul className="mt-3 flex flex-col gap-3">
            {historial
              .filter((e) => terminado(e.estado))
              .map((e) => (
                <li key={e.id} className="text-sm">
                  <span className="font-semibold">
                    {ETIQUETA_MOTIVO[e.motivo] ?? e.motivo}
                  </span>{" "}
                  <span className="text-gray">
                    — {ETIQUETA_ESTADO[e.estado] ?? e.estado}
                  </span>
                  <Historial acciones={e.acciones ?? []} />
                </li>
              ))}
          </ul>
        </details>
      )}
    </section>
  );
}

/** Las tres rutas escritas enteras y no armadas con un `${accion}`: el check
 * de contrato (`lib/contrato.test.ts`) coteja cada ruta literal contra el
 * OpenAPI, y un segmento armado en runtime se le escapa. */
function rutaAccion(id: string, accion: Accion): string {
  if (accion === "elevar") return `/reports/escalamientos/${id}/elevar`;
  if (accion === "resolver") return `/reports/escalamientos/${id}/resolver`;
  return `/reports/escalamientos/${id}/acciones`;
}

type Accion = "acciones" | "elevar" | "resolver";

function CadenaAbierta({
  escalamiento,
  puedeEscalar,
  puedeResolver,
  enviando,
  onAccion,
}: {
  escalamiento: Escalamiento;
  puedeEscalar: boolean;
  puedeResolver: boolean;
  enviando: boolean;
  onAccion: (accion: Accion, descripcion: string) => void;
}) {
  const [texto, setTexto] = useState("");
  const enGerencia = escalamiento.nivel_actual === "gerencia";

  return (
    <div className="flex flex-col gap-3 rounded border border-gray/20 p-4">
      <Cabecera escalamiento={escalamiento} />
      <p className="text-sm text-secondary">{escalamiento.descripcion}</p>

      <Responsables destinatarios={escalamiento.destinatarios} />

      <Historial acciones={escalamiento.acciones ?? []} />

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Qué hiciste o por qué lo elevás
        <textarea
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          rows={2}
          maxLength={2000}
          className="rounded border border-gray/40 p-2 font-normal"
        />
      </label>
      <div className="flex flex-wrap gap-2">
        <Accion
          visible={puedeResolver}
          deshabilitada={enviando || !texto.trim()}
          onClick={() => onAccion("acciones", texto.trim())}
          clase="rounded border border-gray px-3 py-1.5 text-sm font-semibold text-dark disabled:opacity-50"
        >
          Registrar acción
        </Accion>
        <Accion
          visible={puedeEscalar && !enGerencia}
          deshabilitada={enviando || !texto.trim()}
          onClick={() => onAccion("elevar", texto.trim())}
          clase="rounded bg-secondary px-3 py-1.5 text-sm font-bold text-white disabled:opacity-50"
        >
          Elevar al siguiente nivel
        </Accion>
        <Accion
          visible={puedeResolver}
          deshabilitada={enviando || !texto.trim()}
          onClick={() => onAccion("resolver", texto.trim())}
          clase="rounded bg-primary px-3 py-1.5 text-sm font-bold text-white disabled:opacity-50"
        >
          Dar por resuelto
        </Accion>
      </div>
      {enGerencia && (
        <p className="text-xs text-gray">
          Gerencia es el último nivel: desde acá solo se resuelve.
        </p>
      )}
    </div>
  );
}

function Cabecera({ escalamiento }: { escalamiento: Escalamiento }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-900">
        {ETIQUETA_NIVEL[escalamiento.nivel_actual] ?? escalamiento.nivel_actual}
      </span>
      <span className="font-semibold">
        {ETIQUETA_MOTIVO[escalamiento.motivo] ?? escalamiento.motivo}
      </span>
      <span className="text-gray">
        {ETIQUETA_ESTADO[escalamiento.estado] ?? escalamiento.estado}
      </span>
    </div>
  );
}

function Accion({
  visible,
  deshabilitada,
  onClick,
  clase,
  children,
}: {
  visible: boolean;
  deshabilitada: boolean;
  onClick: () => void;
  clase: string;
  children: React.ReactNode;
}) {
  if (!visible) return null;
  return (
    <button type="button" disabled={deshabilitada} onClick={onClick} className={clase}>
      {children}
    </button>
  );
}

function Responsables({ destinatarios }: { destinatarios: string[] | undefined }) {
  if (destinatarios === undefined) return null;
  // Vacío no es un error: la emisión se guarda igual y sale como fuga en la
  // matriz (RN-REP-005). Decirlo es el punto — quien eleva no puede suponer
  // que llegó.
  return (
    <p className="text-sm">
      {destinatarios.length === 0 ? (
        <span className="text-secondary">
          Nadie responde por este nivel hoy: el aviso se guardó pero no llegó a
          ninguna persona.
        </span>
      ) : (
        <>
          <span className="text-gray">Responde: </span>
          {destinatarios.join(", ")}
        </>
      )}
    </p>
  );
}

function FormularioApertura({
  enviando,
  onAbrir,
}: {
  enviando: boolean;
  onAbrir: (motivo: string, descripcion: string) => void;
}) {
  const [motivo, setMotivo] = useState<string>(MOTIVOS_ESCALAMIENTO[0]);
  const [texto, setTexto] = useState("");

  return (
    <div className="flex flex-col gap-3 rounded border border-gray/20 p-4">
      <p className="text-sm text-secondary">
        Si no podés resolverlo vos, elevalo. Arranca en el supervisor y sube de a
        un nivel para que quede quién intentó qué.
      </p>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Motivo
        <select value={motivo} onChange={(e) => setMotivo(e.target.value)}>
          {MOTIVOS_ESCALAMIENTO.map((m) => (
            <option key={m} value={m}>
              {ETIQUETA_MOTIVO[m]}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Qué pasó
        <textarea
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          rows={3}
          maxLength={2000}
          className="rounded border border-gray/40 p-2 font-normal"
        />
      </label>
      <button
        type="button"
        disabled={enviando || !texto.trim()}
        onClick={() => onAbrir(motivo, texto.trim())}
        className="w-fit rounded bg-secondary px-4 py-2 text-sm font-bold text-white disabled:opacity-50"
      >
        Elevar este reporte
      </button>
    </div>
  );
}

function Historial({ acciones }: { acciones: Escalamiento["acciones"] }) {
  if (!acciones || acciones.length === 0) return null;
  return (
    <ol className="flex flex-col gap-1 border-l-2 border-gray/20 pl-3">
      {acciones.map((a, i) => (
        <li key={`${a.ts}-${i}`} className="text-sm">
          <span className="text-xs font-bold uppercase text-gray">
            {ETIQUETA_NIVEL[a.nivel] ?? a.nivel} · {a.accion}
          </span>
          <p>{a.descripcion}</p>
          <span className="text-[11px] text-gray">
            {new Date(a.ts).toLocaleString("es-PE")}
          </span>
        </li>
      ))}
    </ol>
  );
}
