import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { TableroCliente, type Columna, type Convocatoria } from "./tablero-cliente";

type Params = Promise<{ convocatoria?: string }>;

/** Cuál convocatoria mostrar: la del query param, o la primera publicada.
 * Abrir la pantalla en blanco obliga a un click que siempre es el mismo. */
function elegirConvocatoria(
  convocatorias: Convocatoria[],
  pedida: string | undefined,
): string | null {
  if (pedida) return pedida;
  const publicada = convocatorias.find((c) => c.estado === "publicada");
  return publicada?.id ?? convocatorias[0]?.id ?? null;
}

/** El enlace del formulario público solo existe si la convocatoria está
 * publicada: el token nace al publicar. */
function enlaceDe(convocatoria: Convocatoria | undefined): string | null {
  if (!convocatoria?.token_publico) return null;
  return `/api/v1/rrhh/postulaciones/${convocatoria.token_publico}`;
}

export default async function ContratacionPage({
  searchParams,
}: {
  searchParams: Params;
}) {
  const { token } = await obtenerSesion();
  const filtros = await searchParams;

  let convocatorias: Convocatoria[];
  try {
    convocatorias = await apiFetch<Convocatoria[]>("/api/v1/rrhh/convocatorias", {
      token,
    });
  } catch (e) {
    return (
      <p className="text-secondary">
        {e instanceof ApiError && e.status === 403
          ? "Tu usuario no tiene permiso para ver convocatorias."
          : "No se pudieron cargar las convocatorias."}
      </p>
    );
  }

  const seleccionada = elegirConvocatoria(convocatorias, filtros.convocatoria);

  let columnas: Columna[] = [];
  if (seleccionada) {
    // El tablero de una convocatoria que ya no existe no es un error de la
    // pantalla: se muestra la lista y listo.
    columnas = await apiFetch<Columna[]>(
      `/api/v1/rrhh/convocatorias/${seleccionada}/tablero`,
      { token },
    ).catch(() => []);
  }

  return (
    <TableroCliente
      convocatorias={convocatorias}
      columnas={columnas}
      seleccionada={seleccionada}
      enlaceFormulario={enlaceDe(convocatorias.find((c) => c.id === seleccionada))}
    />
  );
}
