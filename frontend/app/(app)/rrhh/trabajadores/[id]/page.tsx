import Link from "next/link";

import { Insignia } from "@/components/estado/insignia";
import { ApiError, apiFetch } from "@/lib/api";
import { hoyEnZonaDelNegocio } from "@/lib/fechas";
import { obtenerSesion } from "@/lib/sesion";

import { AccionesLegajo } from "./legajo-cliente";

type Contrato = {
  id: string;
  modalidad: string;
  remuneracion: string;
  fecha_inicio: string;
  fecha_fin: string | null;
  estado: string;
  fecha_firma: string | null;
};
type Amonestacion = { id: string; tipo: string; fecha_emision: string };
type Memorandum = { id: string; asunto: string; fecha: string };
type Certificado = {
  id: string;
  fecha_emision: string;
  tiempo_servicios_meses: number;
  dentro_de_plazo: boolean;
};
type Permiso = {
  id: string;
  tipo: string;
  fecha_desde: string;
  fecha_hasta: string | null;
  estado: string;
};
type Pacto = { id: string; costo_financiado: string; plazo_permanencia_meses: number };
type Boleta = { id: string; periodo: string; neto_pagar: string; fecha_pago: string };
type Liquidacion = {
  id: string;
  total: string;
  fecha_pago: string;
  dentro_de_plazo: boolean;
};
type Trabajador = {
  id: string;
  persona_id: string;
  cargo: string;
  area: string;
  tipo_vinculo: string;
  fecha_ingreso: string;
  fecha_cese: string | null;
  remuneracion_base: string | null;
  estado: string;
};
type Legajo = {
  trabajador: Trabajador;
  contratos: Contrato[];
  amonestaciones: Amonestacion[];
  memorandums: Memorandum[];
  certificados: Certificado[];
  permisos: Permiso[];
  pactos_permanencia: Pacto[];
  nomina_visible: boolean;
  boletas: Boleta[];
  liquidaciones: Liquidacion[];
};

function Seccion({
  titulo,
  vacio,
  children,
}: {
  titulo: string;
  vacio: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="font-heading text-lg italic uppercase text-dark">{titulo}</h2>
      {Array.isArray(children) && children.length === 0 ? (
        <p className="rounded bg-cream px-3 py-2 text-sm text-gray">{vacio}</p>
      ) : (
        <ul className="flex flex-col gap-1 text-sm">{children}</ul>
      )}
    </section>
  );
}

function Fila({ children }: { children: React.ReactNode }) {
  return <li className="flex flex-wrap gap-x-4 border-b border-gray/15 py-1.5">{children}</li>;
}

/**
 * El legajo del trabajador: todo su expediente en una sola lectura.
 *
 * `GET /rrhh/trabajadores/{id}/legajo` devolvía contratos, sanciones,
 * memorandos, certificados, permisos, pactos, boletas y liquidaciones **en una
 * sola respuesta**, y no lo llamaba ninguna pantalla: RRHH tenía ocho familias
 * de endpoints entregadas y probadas, y la única pantalla del módulo era la
 * lista de trabajadores.
 */
export default async function LegajoPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { token, usuario } = await obtenerSesion();

  let legajo: Legajo;
  let nombre = "Trabajador";
  try {
    legajo = await apiFetch<Legajo>(`/api/v1/rrhh/trabajadores/${id}/legajo`, { token });
    const personas = await apiFetch<{ id: string; nombres: string; apellidos: string }[]>(
      "/api/v1/personas/buscar",
      { token },
    ).catch(() => []);
    const persona = personas.find((p) => p.id === legajo.trabajador.persona_id);
    if (persona) nombre = `${persona.nombres} ${persona.apellidos}`.trim();
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      return <p className="text-secondary">Ese trabajador no existe.</p>;
    }
    return (
      <p className="text-secondary">
        {e instanceof ApiError && e.status === 403
          ? "Tu usuario no tiene permiso para ver este legajo."
          : "No se pudo cargar el legajo."}
      </p>
    );
  }

  const t = legajo.trabajador;

  return (
    <div className="flex flex-col gap-5">
      <Link href="/rrhh/trabajadores" className="text-sm font-semibold text-primary hover:underline">
        ← Trabajadores
      </Link>

      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="font-heading text-xl text-dark">{nombre}</h1>
        <Insignia tono={t.estado === "cesado" ? "neutro" : "exito"}>{t.estado}</Insignia>
      </div>

      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 rounded bg-cream px-4 py-3 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-xs uppercase text-gray">Cargo</dt>
          <dd className="font-semibold">{t.cargo}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-gray">Área</dt>
          <dd className="font-semibold">{t.area}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-gray">Vínculo</dt>
          <dd className="font-semibold">{t.tipo_vinculo.replaceAll("_", " ")}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-gray">Ingreso</dt>
          <dd className="cifra font-semibold">{t.fecha_ingreso}</dd>
        </div>
      </dl>

      <AccionesLegajo
        trabajadorId={t.id}
        hoy={hoyEnZonaDelNegocio()}
        permisos={usuario.permisos}
      />

      <Seccion titulo="Contratos" vacio="Sin contratos registrados.">
        {legajo.contratos.map((c) => (
          <Fila key={c.id}>
            <span className="font-semibold text-dark">{c.modalidad}</span>
            <span className="cifra">
              {c.fecha_inicio} → {c.fecha_fin ?? "indefinido"}
            </span>
            <span className="cifra">S/ {c.remuneracion}</span>
            <span className="text-gray">{c.estado}</span>
          </Fila>
        ))}
      </Seccion>

      <Seccion titulo="Permisos" vacio="Sin permisos solicitados.">
        {legajo.permisos.map((p) => (
          <Fila key={p.id}>
            <span className="font-semibold text-dark">{p.tipo.replaceAll("_", " ")}</span>
            <span className="cifra">
              {p.fecha_desde}
              {p.fecha_hasta ? ` → ${p.fecha_hasta}` : ""}
            </span>
            <span className="text-gray">{p.estado}</span>
          </Fila>
        ))}
      </Seccion>

      <Seccion titulo="Disciplina" vacio="Sin amonestaciones ni memorandos.">
        {[
          ...legajo.amonestaciones.map((a) => (
            <Fila key={a.id}>
              <span className="font-semibold text-secondary">amonestación {a.tipo}</span>
              <span className="cifra">{a.fecha_emision}</span>
            </Fila>
          )),
          ...legajo.memorandums.map((m) => (
            <Fila key={m.id}>
              <span className="font-semibold text-dark">memorándum</span>
              <span>{m.asunto}</span>
              <span className="cifra">{m.fecha}</span>
            </Fila>
          )),
        ]}
      </Seccion>

      <Seccion titulo="Certificados" vacio="Sin certificados emitidos.">
        {legajo.certificados.map((c) => (
          <Fila key={c.id}>
            <span className="cifra">{c.fecha_emision}</span>
            <span>{c.tiempo_servicios_meses} meses de servicio</span>
            {/* Fuera de plazo no es un detalle: el certificado se entrega
                dentro de las 48 horas del cese (RN-RRHH-007). */}
            {!c.dentro_de_plazo && (
              <span className="font-semibold text-secondary">fuera de plazo</span>
            )}
          </Fila>
        ))}
      </Seccion>

      <Seccion titulo="Pactos de permanencia" vacio="Sin pactos de permanencia.">
        {legajo.pactos_permanencia.map((p) => (
          <Fila key={p.id}>
            <span className="cifra">S/ {p.costo_financiado}</span>
            <span>{p.plazo_permanencia_meses} meses de permanencia</span>
          </Fila>
        ))}
      </Seccion>

      {/* `nomina_visible` no es decoración: dice si estas listas vinieron
          vacías porque no hay nada o porque quien pregunta no tiene
          `rrhh.nomina_gestionar`. Sin distinguirlo, un legajo sin sueldos se
          lee igual que uno censurado. */}
      {legajo.nomina_visible ? (
        <>
          <Seccion titulo="Boletas de pago" vacio="Sin boletas registradas.">
            {legajo.boletas.map((b) => (
              <Fila key={b.id}>
                <span className="cifra font-semibold text-dark">{b.periodo}</span>
                <span className="cifra">S/ {b.neto_pagar}</span>
                <span className="cifra text-gray">pagada {b.fecha_pago}</span>
              </Fila>
            ))}
          </Seccion>

          <Seccion titulo="Liquidaciones" vacio="Sin liquidaciones.">
            {legajo.liquidaciones.map((l) => (
              <Fila key={l.id}>
                <span className="cifra font-semibold text-dark">S/ {l.total}</span>
                <span className="cifra">{l.fecha_pago}</span>
                {!l.dentro_de_plazo && (
                  <span className="font-semibold text-secondary">fuera de plazo</span>
                )}
              </Fila>
            ))}
          </Seccion>
        </>
      ) : (
        <p className="rounded bg-cream px-3 py-2 text-sm text-gray">
          Las boletas y liquidaciones no se muestran: hacen falta permisos de
          nómina. No es que no existan.
        </p>
      )}
    </div>
  );
}
