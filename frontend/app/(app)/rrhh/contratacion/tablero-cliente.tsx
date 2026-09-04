"use client";

import { useState, useTransition } from "react";

import { BuscarDocumento } from "@/components/consulta/buscar-documento";
import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";

import {
  avanzarPostulanteAction,
  cerrarConvocatoriaAction,
  contratarPostulanteAction,
  crearConvocatoriaAction,
  descartarPostulanteAction,
  publicarConvocatoriaAction,
  type EstadoRrhh,
} from "./actions";
import { Combobox } from "@/components/ui/combobox";
import { ETIQUETA_DOCUMENTO, TIPOS_DOCUMENTO } from "@/lib/documento";

export type Convocatoria = {
  id: string;
  sucursal_id: string | null;
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
export type Sucursal = { id: string; nombre: string };

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

/**
 * El diálogo del tablero: el molde común más los dos rasgos propios de esta
 * pantalla —campos ocultos por lote y un disparador destructivo—, que sus
 * cuatro llamadores dan por sentados.
 *
 * Era una copia entera del molde **con el mismo nombre**, `DialogoFormulario`,
 * y su propio `EstadoRrhh` en vez de `EstadoFormulario`: dos componentes
 * distintos llamados igual en el mismo repositorio, y el de acá sin el
 * arreglo de React 19 ni el marcado de campos del 422.
 */
function DialogoTablero({
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
  return (
    <DialogoFormulario
      titulo={titulo}
      disparador={etiqueta}
      claseDisparador={`text-xs font-bold hover:underline ${
        destructivo ? "text-status-danger" : "text-primary"
      }`}
      etiquetaEnvio={textoBoton}
      accion={accion}
      ayuda={descripcion}
    >
      {Object.entries(ocultos ?? {}).map(([nombre, valor]) => (
        <input key={nombre} type="hidden" name={nombre} value={valor} />
      ))}
      {children}
    </DialogoFormulario>
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

function Ficha({
  postulante,
  permisos,
  sucursales,
  sucursalConvocatoria,
}: {
  postulante: Postulante;
  permisos: string[];
  sucursales: Sucursal[];
  sucursalConvocatoria: string | null;
}) {
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
            <DialogoContratar
              postulante={postulante}
              permisos={permisos}
              sucursales={sucursales}
              sucursalConvocatoria={sucursalConvocatoria}
            />
          )}
          <DialogoTablero
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
          </DialogoTablero>
        </div>
      )}
    </li>
  );
}

function DialogoContratar({
  postulante,
  permisos,
  sucursales,
  sucursalConvocatoria,
}: {
  postulante: Postulante;
  permisos: string[];
  sucursales: Sucursal[];
  sucursalConvocatoria: string | null;
}) {
  return (
    <DialogoTablero
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
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Sucursal donde trabaja
        <Combobox
          name="sucursal_id"
          etiqueta="Sucursal"
          defaultValue={sucursalConvocatoria}
          marcador="Sin sucursal asignada"
          opciones={sucursales.map((s) => ({ valor: s.id, etiqueta: s.nombre }))}
        />
        <span className="text-xs font-normal text-gray">
          Sin esto no aparece en el pad de asistencia de ningún local.
        </span>
      </label>
      <div className="grid grid-cols-2 gap-2">
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Documento
          <select name="tipo_documento" defaultValue="dni">
            {TIPOS_DOCUMENTO.map((t) => (
              <option key={t} value={t}>
                {ETIQUETA_DOCUMENTO[t]}
              </option>
            ))}
          </select>
        </label>
        <Campo etiqueta="Número" nombre="numero_documento" maxLength={20} />
      </div>
      {/* El nombre viene precargado con lo que el postulante escribió de sí
          mismo en el formulario público, y con ese nombre se firma el
          contrato y se declara a SUNAT: acá se contrasta contra RENIEC antes
          de que nazca la ficha. El servidor aplica el mismo criterio aunque
          nadie apriete el botón (RN-PTS-004); esto deja **verlo** antes. */}
      <div className="grid grid-cols-2 gap-2">
        <Campo
          etiqueta="Nombres"
          nombre="nombres"
          maxLength={100}
          defaultValue={postulante.nombres}
        />
        <Campo
          etiqueta="Apellidos"
          nombre="apellidos"
          maxLength={100}
          defaultValue={postulante.apellidos}
        />
      </div>
      <BuscarDocumento
        permisos={permisos}
        tipo="dni"
        campo="numero_documento"
        rellena={{ nombres: "nombres", apellidos: "apellidos" }}
      />
      <Campo
        etiqueta="Remuneración base"
        nombre="remuneracion_base"
        type="number"
        min={0}
        step="0.10"
      />
    </DialogoTablero>
  );
}

function ColumnaTablero({
  etapa,
  postulantes,
  permisos,
  sucursales,
  sucursalConvocatoria,
}: {
  etapa: (typeof ETAPAS)[number];
  postulantes: Postulante[];
  permisos: string[];
  sucursales: Sucursal[];
  sucursalConvocatoria: string | null;
}) {
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
            <Ficha
              key={p.id}
              postulante={p}
              permisos={permisos}
              sucursales={sucursales}
              sucursalConvocatoria={sucursalConvocatoria}
            />
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
        <h2 className="font-heading text-lg text-dark">Convocatorias</h2>
        <DialogoTablero
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
        </DialogoTablero>
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
                        <DialogoTablero
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
                        </DialogoTablero>
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

/**
 * El enlace que se pega en el aviso, con su botón de copiar.
 *
 * La URL absoluta se arma al hacer clic y no al renderizar: el servidor no
 * conoce el dominio por el que entró el navegador, y calcularla durante el
 * render rompería la hidratación.
 */
function EnlaceFormulario({ ruta }: { ruta: string }) {
  const [copiado, setCopiado] = useState(false);

  return (
    <p className="flex flex-wrap items-center gap-2 text-sm text-gray">
      Formulario público de postulación:{" "}
      <a className="text-primary hover:underline" href={ruta} target="_blank" rel="noreferrer">
        {ruta}
      </a>
      <button
        type="button"
        className="rounded bg-cream px-2 py-0.5 text-xs"
        onClick={async () => {
          await navigator.clipboard.writeText(`${window.location.origin}${ruta}`);
          setCopiado(true);
        }}
      >
        {copiado ? "Copiado" : "Copiar enlace"}
      </button>
    </p>
  );
}

export function TableroCliente({
  convocatorias,
  columnas,
  seleccionada,
  enlaceFormulario,
  permisos,
  sucursales,
}: {
  convocatorias: Convocatoria[];
  columnas: Columna[];
  seleccionada: string | null;
  enlaceFormulario: string | null;
  /** Los de la sesión. Solo deciden si se ofrece traer el nombre de RENIEC
   * al contratar: cada consulta gasta cuota de Factiliza. */
  permisos: string[];
  sucursales: Sucursal[];
}) {
  const [verDescartados, setVerDescartados] = useState(false);
  const porEstado = new Map(columnas.map((c) => [c.estado, c.postulantes]));
  const descartados = porEstado.get(DESCARTADO) ?? [];
  // Por defecto, contratar deja la sucursal de la convocatoria: es donde
  // el postulante aplicó, y sin sucursal no aparece en ningún pad.
  const sucursalConvocatoria =
    convocatorias.find((c) => c.id === seleccionada)?.sucursal_id ?? null;

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
        <h1 className="font-heading text-xl text-dark">Contratación</h1>
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
          {enlaceFormulario && <EnlaceFormulario ruta={enlaceFormulario} />}
          <div className="flex gap-4 overflow-x-auto pb-2">
            {ETAPAS.map((etapa) => (
              <ColumnaTablero
                key={etapa.clave}
                etapa={etapa}
                postulantes={porEstado.get(etapa.clave) ?? []}
                permisos={permisos}
                sucursales={sucursales}
                sucursalConvocatoria={sucursalConvocatoria}
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
                    <Ficha
                      postulante={p}
                      permisos={permisos}
                      sucursales={sucursales}
                      sucursalConvocatoria={sucursalConvocatoria}
                    />
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
