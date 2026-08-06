import { Tablero } from "@/components/reportes/tablero";
import { ApiError, apiFetch } from "@/lib/api";
import type {
  Catalogo,
  Rol,
  Sucursal,
  Tablero as TableroGuardado,
} from "@/lib/reportes";
import { obtenerSesion } from "@/lib/sesion";

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

/** Cada bloque falla por su cuenta: que el usuario no tenga `sales.leer` no
 * puede dejar el tablero entero en blanco. `null` = no disponible. */
async function opcional<T>(promesa: Promise<T>): Promise<T | null> {
  try {
    return await promesa;
  } catch (e) {
    if (e instanceof ApiError) return null;
    throw e;
  }
}

function Kpi({
  titulo,
  valor,
  detalle,
  alerta,
}: {
  titulo: string;
  valor: string | number;
  detalle?: string;
  alerta?: boolean;
}) {
  return (
    <article className="rounded border border-foreground/10 bg-background p-4 shadow-sm">
      <h2 className="text-xs font-medium uppercase tracking-wide text-gray">{titulo}</h2>
      <p
        className={`mt-1 font-heading text-3xl font-semibold ${alerta ? "text-accent" : ""}`}
      >
        {valor}
      </p>
      {detalle && <p className="text-sm text-gray">{detalle}</p>}
    </article>
  );
}

export default async function DashboardPage() {
  // `empresa_id` sale de `/users/me` (verificado por la API), ya no del JWT
  // decodificado sin firma en el cliente.
  const { token, usuario } = await obtenerSesion();
  if (!usuario.empresa_id) {
    return (
      <p className="rounded border border-accent/40 bg-accent/5 p-4 text-sm text-accent">
        Tu usuario no tiene una empresa asignada — no se puede cargar el dashboard.
      </p>
    );
  }

  const [resumen, catalogo, sucursales, tableros, roles] = await Promise.all([
    opcional(
      apiFetch<DashboardResumen>(
        `/api/v1/dashboard/resumen?empresa_id=${usuario.empresa_id}`,
        { token },
      ),
    ),
    opcional(apiFetch<Catalogo>("/api/v1/reportes", { token })),
    opcional(apiFetch<Sucursal[]>("/api/v1/sucursales", { token })),
    opcional(apiFetch<TableroGuardado[]>("/api/v1/tableros", { token })),
    opcional(apiFetch<Rol[]>("/api/v1/tableros/roles", { token })),
  ]);

  if (!catalogo) {
    return (
      <p className="rounded border border-accent/40 bg-accent/5 p-4 text-sm text-accent">
        Tu usuario no tiene permiso para ver el dashboard.
      </p>
    );
  }

  // Un usuario solo filtra por las sucursales de su alcance: pedir otra
  // devuelve 403 igual, pero ofrecérsela en el checkbox sería mentirle.
  const visibles = (sucursales ?? []).filter(
    (s) => usuario.sucursales.length === 0 || usuario.sucursales.includes(s.id),
  );

  return (
    <div className="flex flex-col gap-6">
      {resumen && (
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Kpi
            titulo="Ventas de hoy"
            valor={resumen.ventas_hoy.cantidad}
            detalle={`S/ ${resumen.ventas_hoy.total}`}
          />
          <Kpi
            titulo="Stock bajo mínimo"
            valor={resumen.stock_bajo_minimo}
            alerta={resumen.stock_bajo_minimo > 0}
          />
          <Kpi
            titulo="Cajas abiertas"
            valor={resumen.cajas_abiertas.length}
            detalle={
              resumen.cajas_abiertas.length > 0
                ? `Apertura S/ ${resumen.cajas_abiertas[0].monto_apertura}`
                : undefined
            }
          />
        </section>
      )}

      <Tablero
        catalogo={catalogo}
        sucursales={visibles}
        tableros={tableros ?? []}
        roles={roles ?? []}
      />
    </div>
  );
}
