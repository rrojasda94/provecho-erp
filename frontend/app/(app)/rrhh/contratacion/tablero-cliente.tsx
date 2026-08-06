"use client";

import { useActionState, useEffect, useRef, useState, useTransition } from "react";

import {
  avanzarPostulanteAction,
  cerrarConvocatoriaAction,
  contratarPostulanteAction,
  crearConvocatoriaAction,
  descartarPostulanteAction,
  publicarConvocatoriaAction,
  type EstadoRrhh,
} from "./actions";

export type Convocatoria = {
  id: string;
  puesto: string;
  motivo: string;
  perfil_puesto: string | null;
  vacantes: number;
  remuneracion_min: string | null;
  remuneracion_max: string | null;
  fecha_objetivo: string | null;
  fecha_limite: string | null;
  fecha_publicacion: string | null;
  token_publico: string | null;
  estado: string;
};

export type Postulante = {
  id: string;
  nombres: string;
  apellidos: string;
  telefono: string | null;
  email: string | null;
  puesto_postulado: string;
  fecha_postulacion: string;
  canal_origen: string | null;
  motivo_descarte: string | null;
  estado: string;
};

export type Columna = { estado: string; postulantes: Postulante[] };

const ESTADO_INICIAL: EstadoRrhh = { error: "", ok: false };

/** Las ocho etapas en orden, con el nombre que usa quien contrata — no el
 * del enum. El orden es el del dominio (`rules.ETAPAS_POSTULANTE`) y de él
 * sale cuál es "la siguiente": el tablero avanza **de a una columna**. */
const ETAPAS: { clave: string; titulo: string; ayuda: string }[] = [
  { clave: "recibido", titulo: "Recibido", ayuda: "Llegó la postulación" },
  { clave: "preseleccionado", titulo: "Preseleccionado", ayuda: "Cumple el perfil" },
  { clave: "entrevistado", titulo: "Entrevistado", ayuda: "Ficha puntuada 1-4" },
  { clave: "verificado", titulo: "Verificado", ayuda: "Referencias y documentos" },
  { clave: "oferta_enviada", titulo: "Oferta enviada", ayuda: "Espera respuesta" },
  { clave: "contratado", titulo: "Contratado", ayuda: "Contrato firmado y alta" },
  { clave: "inducido", titulo: "Inducido", ayuda: "Grupo, marca y puesto" },
  { clave: "confirmado", titulo: "Confirmado", ayuda: "Superó el periodo de prueba" },
];

const DESCARTADO = "descartado";

function siguienteEtapa(estado: string): { clave: string; titulo: string } | null {
  const indice = ETAPAS.findIndex((e) => e.clave === estado);
  if (indice < 0 || indice === ETAPAS.length - 1) return null;
  return ETAPAS[indice + 1];
}

function DialogoFormulario({
  etiqueta,
  titulo,
  descripcion,
  accion,
  ocultos,
  children,
  destructivo,
  textoBoton = "Guardar",
}: {
  etiqueta: string;
  titulo: string;
  descripcion?: React.ReactNode;
  accion: (previo: EstadoRrhh, datos: FormData) => Promise<EstadoRrhh>;
  ocultos?: Record<string, string>;
  children: React.ReactNode;
  destructivo?: boolean;
  textoBoton?: string;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [estado, formAction, pendiente] = useActionState(accion, ESTADO_INICIAL);

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
        className={`text-xs font-bold hover:underline ${
          destructivo ? "text-secondary" : "text-primary"
        }`}
      >
        {etiqueta}
      </button>
      <dialog ref={dialogRef} className="w-full max-w-md rounded-lg p-0 backdrop:bg-dark/40">
        <form ref={formRef} action={formAction} className="flex flex-col gap-3 p-6">
          {Object.entries(ocultos ?? {}).map(([nombre, valor]) => (
            <input key={nombre} type="hidden" name={nombre} value={valor} />
          ))}
          <h2 className="font-heading text-lg italic uppercase text-dark">{titulo}</h2>
          {descripcion && <p className="text-sm text-gray">{descripcion}</p>}
          {children}
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
              {pendiente ? "Guardando..." : textoBoton}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

function Campo({
  etiqueta,
  nombre,
  ...props
}: { etiqueta: string; nombre: string } & React.ComponentProps<"input">) {
  return (
    <label className="flex flex-col gap-1 text-sm font-semibold">
      {etiqueta}
      <input name={nombre} {...props} />
    </label>
  );
}

function Ficha({ postulante }: { postulante: Postulante }) {
  const [pendiente, startTransition] = useTransition();
  const siguiente = siguienteEtapa(postulante.estado);
  const descartado = postulante.estado === DESCARTADO;

  return (
    <li className="rounded border border-gray/25 bg-white p-2.5 text-sm">
      <p className="font-semibold text-dark">
        {postulante.nombres} {postulante.apellidos}
      </p>
      <p className="text-xs text-gray">{postulante.puesto_postulado}</p>
      <p className="text-xs text-gray">
        {postulante.fecha_postulacion}
        {postulante.canal_origen ? ` · ${postulante.canal_origen}` : ""}
      </p>
      {postulante.telefono && (
        <p className="text-xs text-gray">{postulante.telefono}</p>
      )}
      {descartado ? (
        <p className="mt-1 text-xs italic text-secondary">
          {postulante.motivo_descarte ?? "sin motivo registrado"}
        </p>
      ) : (
        <div className="mt-2 flex flex-wrap items-center gap-3">
          {siguiente && siguiente.clave !== "contratado" && (
            <button
              type="button"
              disabled={pendiente}
              onClick={() =>
                startTransition(() =>
                  void avanzarPostulanteAction(postulante.id, siguiente.clave),
                )
              }
              className="text-xs font-bold text-primary hover:underline"
            >
              → {siguiente.titulo}
            </button>
          )}
          {siguiente?.clave === "contratado" && (
            <DialogoContratar postulante={postulante} />
          )}
          <DialogoFormulario
            etiqueta="Descartar"
            titulo="Descartar postulante"
            descripcion={
              <>
                El motivo queda en el expediente y no se puede dejar vacío: ante un
                reclamo por discriminación (Ley 26772), un descarte sin motivo
                registrado es la empresa sin defensa.
              </>
            }
            accion={descartarPostulanteAction}
            ocultos={{ postulante_id: postulante.id }}
            destructivo
            textoBoton="Descartar"
          >
            <Campo
              etiqueta="Motivo"
              nombre="motivo"
              required
              maxLength={255}
              placeholder="No cumple el requisito de experiencia en cocina"
            />
          </DialogoFormulario>
        </div>
      )}
    </li>
  );
}

function DialogoContratar({ postulante }: { postulante: Postulante }) {
  return (
    <DialogoFormulario
      etiqueta="→ Contratar"
      titulo={`Contratar a ${postulante.nombres}`}
      descripcion={
        <>
          Acá nace la persona en el grupo: se crean su ficha y su vínculo laboral.
          Si es un recontratado, el servidor reusa la persona que ya existe en vez
          de duplicarla.
        </>
      }
      accion={contratarPostulanteAction}
      ocultos={{ postulante_id: postulante.id }}
      textoBoton="Contratar"
    >
      <Campo etiqueta="Cargo" nombre="cargo" required maxLength={100} />
      <Campo etiqueta="Área" nombre="area" required maxLength={100} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Tipo de vínculo
        <select name="tipo_vinculo" defaultValue="planilla">
          <option value="planilla">Planilla</option>
          <option value="locacion_servicios">Locación de servicios</option>
          <option value="practicante">Practicante</option>
        </select>
      </label>
      <Campo etiqueta="Fecha de ingreso" nombre="fecha_ingreso" type="date" required />
      <div className="grid grid-cols-2 gap-2">
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Documento
          <select name="tipo_documento" defaultValue="dni">
            <option value="dni">DNI</option>
            <option value="carne_extranjeria">Carné de extranjería</option>
            <option value="pasaporte">Pasaporte</option>
          </select>
        </label>
        <Campo etiqueta="Número" nombre="numero_documento" maxLength={20} />
      </div>
      <Campo
        etiqueta="Remuneración base"
        nombre="remuneracion_base"
        type="number"
        min={0}
        step="0.10"
      />
    </DialogoFormulario>
  );
}

function ColumnaTablero({ etapa, postulantes }: { etapa: (typeof ETAPAS)[number]; postulantes: Postulante[] }) {
  return (
    <div className="flex w-64 shrink-0 flex-col gap-2">
      <div className="border-b-2 border-dark pb-1">
        <p className="text-xs font-bold uppercase text-dark">
          {etapa.titulo} <span className="text-gray">({postulantes.length})</span>
        </p>
        <p className="text-[11px] text-gray">{etapa.ayuda}</p>
      </div>
      {postulantes.length === 0 ? (
        <p className="rounded bg-cream px-2 py-3 text-xs text-gray">Vacío</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {postulantes.map((p) => (
            <Ficha key={p.id} postulante={p} />
          ))}
        </ul>
      )}
    </div>
  );
}

function Convocatorias({
  convocatorias,
  seleccionada,
  onSeleccionar,
}: {
  convocatorias: Convocatoria[];
  seleccionada: string | null;
  onSeleccionar: (id: string) => void;
}) {
  const [pendiente, startTransition] = useTransition();
  const hoy = new Date().toISOString().slice(0, 10);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-lg italic uppercase text-dark">Convocatorias</h2>
        <DialogoFormulario
          etiqueta="+ Nueva convocatoria"
          titulo="Nueva convocatoria"
          descripcion="La búsqueda arranca en borrador. No se publica sin perfil de puesto."
          accion={crearConvocatoriaAction}
          textoBoton="Crear"
        >
          <Campo etiqueta="Puesto" nombre="puesto" required maxLength={150} />
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Motivo
            <select name="motivo" defaultValue="reemplazo">
              <option value="reemplazo">Reemplazo</option>
              <option value="refuerzo">Refuerzo</option>
              <option value="puesto_nuevo">Puesto nuevo</option>
            </select>
          </label>
          <Campo
            etiqueta="Perfil de puesto"
            nombre="perfil_puesto"
            maxLength={100}
            placeholder="docs/rrhh/perfiles/cocina.md"
          />
          <div className="grid grid-cols-3 gap-2">
            <Campo etiqueta="Vacantes" nombre="vacantes" type="number" min={1} defaultValue={1} />
            <Campo etiqueta="Sueldo mín." nombre="remuneracion_min" type="number" min={0} step="0.10" />
            <Campo etiqueta="Sueldo máx." nombre="remuneracion_max" type="number" min={0} step="0.10" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Campo etiqueta="Se necesita para" nombre="fecha_objetivo" type="date" />
            <Campo etiqueta="Cierra el" nombre="fecha_limite" type="date" />
          </div>
        </DialogoFormulario>
      </div>

      {convocatorias.length === 0 ? (
        <p className="rounded bg-cream px-3 py-2 text-sm text-gray">
          Ninguna convocatoria abierta.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[52rem] border-collapse text-sm">
            <thead>
              <tr className="border-b border-gray/30 text-left text-xs uppercase text-gray">
                <th className="py-2 pr-4 font-semibold">Puesto</th>
                <th className="py-2 pr-4 font-semibold">Motivo</th>
                <th className="py-2 pr-4 font-semibold">Vacantes</th>
                <th className="py-2 pr-4 font-semibold">Perfil</th>
                <th className="py-2 pr-4 font-semibold">Estado</th>
                <th className="py-2 font-semibold"></th>
              </tr>
            </thead>
            <tbody>
              {convocatorias.map((c) => (
                <tr
                  key={c.id}
                  className={`border-b border-gray/15 ${
                    c.id === seleccionada ? "bg-cream" : ""
                  }`}
                >
                  <td className="py-2 pr-4">
                    <button
                      type="button"
                      onClick={() => onSeleccionar(c.id)}
                      className="font-semibold text-dark hover:underline"
                    >
                      {c.puesto}
                    </button>
                  </td>
                  <td className="py-2 pr-4 text-gray">{c.motivo}</td>
                  <td className="py-2 pr-4 tabular-nums">{c.vacantes}</td>
                  <td className="py-2 pr-4">
                    {c.perfil_puesto ?? (
                      <span className="text-secondary">falta</span>
                    )}
                  </td>
                  <td className="py-2 pr-4">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                        c.estado === "publicada"
                          ? "bg-accent/30 text-dark"
                          : "bg-gray/20 text-gray"
                      }`}
                    >
                      {c.estado}
                    </span>
                  </td>
                  <td className="py-2">
                    <div className="flex items-center gap-3">
                      {c.estado === "borrador" && (
                        <DialogoFormulario
                          etiqueta="Publicar"
                          titulo={`Publicar: ${c.puesto}`}
                          descripcion={
                            <>
                              Sin perfil de puesto no se publica (RN-RRHH-013): una
                              búsqueda sin perfil no sabe a quién busca.
                            </>
                          }
                          accion={publicarConvocatoriaAction}
                          ocultos={{ convocatoria_id: c.id }}
                          textoBoton="Publicar"
                        >
                          <Campo
                            etiqueta="Fecha de publicación"
                            nombre="fecha_publicacion"
                            type="date"
                            defaultValue={hoy}
                            required
                          />
                          {!c.perfil_puesto && (
                            <Campo
                              etiqueta="Perfil de puesto"
                              nombre="perfil_puesto"
                              required
                              maxLength={100}
                              placeholder="docs/rrhh/perfiles/cocina.md"
                            />
                          )}
                        </DialogoFormulario>
                      )}
                      {c.estado === "publicada" && (
                        <button
                          type="button"
                          disabled={pendiente}
                          onClick={() =>
                            startTransition(() => void cerrarConvocatoriaAction(c.id))
                          }
                          className="text-xs font-semibold text-secondary hover:underline"
                        >
                          Cerrar
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function TableroCliente({
  convocatorias,
  columnas,
  seleccionada,
  enlaceFormulario,
}: {
  convocatorias: Convocatoria[];
  columnas: Columna[];
  seleccionada: string | null;
  enlaceFormulario: string | null;
}) {
  const [verDescartados, setVerDescartados] = useState(false);
  const porEstado = new Map(columnas.map((c) => [c.estado, c.postulantes]));
  const descartados = porEstado.get(DESCARTADO) ?? [];

  function seleccionar(id: string) {
    // Query param y no estado local: así el tablero de una convocatoria es
    // una URL que se puede compartir o dejar abierta en la pantalla del
    // administrador.
    const url = new URL(window.location.href);
    url.searchParams.set("convocatoria", id);
    window.location.href = url.toString();
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-heading text-xl italic uppercase text-dark">Contratación</h1>
        <p className="text-sm text-gray">
          Un solo tablero para los 13 pasos del proceso: de la postulación recibida
          hasta el fin del periodo de prueba. Se avanza de a una columna — el
          historial es lo que sostiene la decisión.
        </p>
      </div>

      <Convocatorias
        convocatorias={convocatorias}
        seleccionada={seleccionada}
        onSeleccionar={seleccionar}
      />

      {seleccionada === null ? (
        <p className="rounded bg-cream px-3 py-2 text-sm text-gray">
          Elegí una convocatoria para ver su tablero.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {enlaceFormulario && (
            <p className="text-sm text-gray">
              Formulario público de postulación:{" "}
              <code className="rounded bg-cream px-1.5 py-0.5 text-xs">
                {enlaceFormulario}
              </code>
            </p>
          )}
          <div className="flex gap-4 overflow-x-auto pb-2">
            {ETAPAS.map((etapa) => (
              <ColumnaTablero
                key={etapa.clave}
                etapa={etapa}
                postulantes={porEstado.get(etapa.clave) ?? []}
              />
            ))}
          </div>

          {/* Los descartados van aparte y plegados: no son parte del flujo,
              pero borrarlos de la vista borraría la evidencia de por qué se
              descartó a alguien. */}
          <div className="border-t border-gray/20 pt-3">
            <button
              type="button"
              onClick={() => setVerDescartados((v) => !v)}
              className="text-sm font-semibold text-dark hover:underline"
            >
              Descartados ({descartados.length}) {verDescartados ? "▾" : "▸"}
            </button>
            {verDescartados && (
              <ul className="mt-2 flex flex-wrap gap-2">
                {descartados.map((p) => (
                  <li key={p.id} className="w-64">
                    <Ficha postulante={p} />
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
