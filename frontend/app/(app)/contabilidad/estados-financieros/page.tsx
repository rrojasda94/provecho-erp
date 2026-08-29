import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import {
  EstadosFinancierosCliente,
  type Balance,
  type EstadoResultados,
  type EstadoSituacion,
} from "./estados-financieros-cliente";

/** Hoy en la zona del negocio (`America/Lima`), como `YYYY-MM-DD`.
 *
 * `toISOString()` da la fecha **en UTC**, que en Perú es la de mañana desde
 * las 19:00. El último día del mes eso movía el "desde" al mes siguiente y el
 * estado salía vacío justo la noche en que se cierra el mes. `en-CA` es el
 * locale cuyo formato corto ya es ISO — no hace falta armar el string a mano.
 */
function hoyEnLima(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Lima",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

/** Primer día del mes en curso y hoy: el rango que se mira el 99% de las
 * veces. Se calculan en el servidor para que el reloj del navegador del
 * cajero no decida qué mes se contabiliza. */
function rangoPorDefecto(): { desde: string; hasta: string } {
  const hasta = hoyEnLima();
  return { desde: `${hasta.slice(0, 8)}01`, hasta };
}

export default async function EstadosFinancierosPage({
  searchParams,
}: {
  searchParams: Promise<{ desde?: string; hasta?: string }>;
}) {
  const { token } = await obtenerSesion();
  const params = await searchParams;
  const porDefecto = rangoPorDefecto();
  const desde = params.desde || porDefecto.desde;
  const hasta = params.hasta || porDefecto.hasta;

  try {
    // El balance va a una fecha (acumulado) y el resultado a un rango: son
    // dos preguntas distintas y por eso no comparten parámetros.
    const [situacion, resultados, balance] = await Promise.all([
      apiFetch<EstadoSituacion>(
        `/api/v1/accounting/reportes/estado-situacion-financiera?hasta=${hasta}`,
        { token },
      ),
      apiFetch<EstadoResultados>(
        `/api/v1/accounting/reportes/estado-resultados?desde=${desde}&hasta=${hasta}`,
        { token },
      ),
      apiFetch<Balance>(
        `/api/v1/accounting/reportes/balance-comprobacion?desde=${desde}&hasta=${hasta}`,
        { token },
      ),
    ]);
    return (
      <EstadosFinancierosCliente
        desde={desde}
        hasta={hasta}
        situacion={situacion}
        resultados={resultados}
        balance={balance}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los estados financieros."
        : "No se pudieron cargar los estados financieros.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
