import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN, decodificarClaims } from "@/lib/auth";

import { logoutAction } from "./actions";

type DashboardResumen = {
  ventas_hoy: { fecha: string; cantidad: number; total: string };
  stock_bajo_minimo: number;
  cajas_abiertas: Array<{
    apertura_caja_id: string;
    punto_venta_id: string;
    cajero_id: string;
    monto_apertura: string;
    abierta_desde: string;
  }>;
};

type ResultadoResumen =
  | { ok: true; resumen: DashboardResumen }
  | { ok: false; mensaje: string };

/** Separado del componente para no acumular ramas de error dentro del
 * cuerpo de la página (regla de complejidad de ESLint) — cada motivo de
 * fallo es un mensaje, no una decisión de layout. */
async function obtenerResumen(empresaId: string, token: string): Promise<ResultadoResumen> {
  try {
    const resumen = await apiFetch<DashboardResumen>(
      `/api/v1/dashboard/resumen?empresa_id=${empresaId}`,
      { token },
    );
    return { ok: true, resumen };
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      redirect("/login");
    }
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver el dashboard."
        : "No se pudo cargar el dashboard. Intentar de nuevo.";
    return { ok: false, mensaje };
  }
}

function CabeceraDashboard() {
  return (
    <header className="dashboard-header">
      <h1>Dashboard</h1>
      <form action={logoutAction}>
        <button type="submit" className="logout-button">
          Cerrar sesión
        </button>
      </form>
    </header>
  );
}

function PaginaConError({ mensaje }: { mensaje: string }) {
  return (
    <main className="dashboard-page">
      <CabeceraDashboard />
      <p className="dashboard-error">{mensaje}</p>
    </main>
  );
}

function TarjetaVentas({ resumen }: { resumen: DashboardResumen }) {
  return (
    <article className="dashboard-card">
      <h2>Ventas de hoy</h2>
      <p className="dashboard-metric">{resumen.ventas_hoy.cantidad}</p>
      <p className="dashboard-submetric">S/ {resumen.ventas_hoy.total}</p>
    </article>
  );
}

function TarjetaStock({ resumen }: { resumen: DashboardResumen }) {
  const hayAlerta = resumen.stock_bajo_minimo > 0;
  return (
    <article className="dashboard-card">
      <h2>Stock bajo mínimo</h2>
      <p className={hayAlerta ? "dashboard-metric dashboard-metric--alerta" : "dashboard-metric"}>
        {resumen.stock_bajo_minimo}
      </p>
    </article>
  );
}

function TarjetaCajas({ resumen }: { resumen: DashboardResumen }) {
  return (
    <article className="dashboard-card">
      <h2>Cajas abiertas</h2>
      <p className="dashboard-metric">{resumen.cajas_abiertas.length}</p>
      {resumen.cajas_abiertas.length > 0 && (
        <ul className="dashboard-list">
          {resumen.cajas_abiertas.map((c) => (
            <li key={c.apertura_caja_id}>
              S/ {c.monto_apertura} — desde{" "}
              {new Date(c.abierta_desde).toLocaleTimeString("es-PE", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

export default async function DashboardPage() {
  const store = await cookies();
  const token = store.get(COOKIE_TOKEN)?.value;
  if (!token) redirect("/login");

  const claims = decodificarClaims(token);
  if (!claims?.empresa_id) {
    return (
      <PaginaConError mensaje="Tu usuario no tiene una empresa asignada — no se puede cargar el dashboard." />
    );
  }

  const resultado = await obtenerResumen(claims.empresa_id, token);
  if (!resultado.ok) {
    return <PaginaConError mensaje={resultado.mensaje} />;
  }

  return (
    <main className="dashboard-page">
      <CabeceraDashboard />
      <section className="dashboard-grid">
        <TarjetaVentas resumen={resultado.resumen} />
        <TarjetaStock resumen={resultado.resumen} />
        <TarjetaCajas resumen={resultado.resumen} />
      </section>
    </main>
  );
}
