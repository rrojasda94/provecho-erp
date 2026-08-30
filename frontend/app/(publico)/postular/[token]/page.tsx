import type { Metadata } from "next";

import { apiFetch } from "@/lib/api";

import PostularCliente from "./postular-cliente";

export const metadata: Metadata = {
  title: "Trabaja con nosotros | Grupo Majambo",
  description: "Postula a nuestras vacantes desde tu celular, en dos minutos.",
};

// El enlace se pega en un aviso impreso o en Facebook y vive semanas: cada
// visita tiene que ver el estado real de la convocatoria, no uno cacheado.
// La empresa la cierra cuando junta suficientes CVs y eso se aplica al
// instante, igual que en la landing de `reconocerte`.
export const dynamic = "force-dynamic";

type ConvocatoriaPublica = {
  puesto: string;
  vacantes: number;
  jornada_horas_semana: string | null;
  fecha_limite: string | null;
};

/** Fecha ISO → «22 de setiembre de 2026». `T00:00` fuerza hora local: sin él
 * el navegador la lee como UTC y en Perú (UTC-5) muestra el día anterior. */
function enLetras(iso: string): string {
  return new Date(`${iso}T00:00`).toLocaleDateString("es-PE", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

/**
 * La convocatoria detrás del token, o `null`.
 *
 * Cerrada, vencida y token inventado se muestran igual —«ya no recibe
 * postulaciones»— porque para el candidato son lo mismo, y explicarle la
 * diferencia solo le confirmaría a un curioso que ese token existió.
 */
async function convocatoria(token: string): Promise<ConvocatoriaPublica | null> {
  try {
    return await apiFetch<ConvocatoriaPublica>(
      `/api/v1/rrhh/postulaciones/${encodeURIComponent(token)}`,
    );
  } catch {
    return null;
  }
}

export default async function PostularPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const vacante = await convocatoria(token);

  if (!vacante) {
    return (
      <main className="publico-main">
        <header className="postular-hero">
          <p className="postular-sobretitulo">Trabaja con nosotros</p>
          <h1 className="postular-titulo">Esta convocatoria ya cerró</h1>
          <p className="postular-bajada">
            Puede que hayamos completado la vacante o que el plazo haya vencido.
            Gracias por tu interés — síguenos en redes para enterarte de la próxima.
          </p>
        </header>
      </main>
    );
  }

  return (
    <main className="publico-main">
      <header className="postular-hero">
        <p className="postular-sobretitulo">Trabaja con nosotros</p>
        <h1 className="postular-titulo">{vacante.puesto}</h1>
        <dl className="postular-datos">
          <div>
            <dt>Vacantes</dt>
            <dd>{vacante.vacantes}</dd>
          </div>
          {vacante.jornada_horas_semana ? (
            <div>
              <dt>Jornada</dt>
              <dd>{Number(vacante.jornada_horas_semana)} h semanales</dd>
            </div>
          ) : null}
          {vacante.fecha_limite ? (
            <div>
              <dt>Postula hasta</dt>
              <dd>{enLetras(vacante.fecha_limite)}</dd>
            </div>
          ) : null}
        </dl>
        <p className="postular-bajada">
          Déjanos tus datos y te llamamos. Toma dos minutos.
        </p>
      </header>

      <PostularCliente token={token} />
    </main>
  );
}
