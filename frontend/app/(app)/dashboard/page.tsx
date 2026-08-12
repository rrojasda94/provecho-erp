import { Tablero } from "@/components/reportes/tablero";
import { AvisoFallo } from "@/components/shell/aviso-fallo";
import { apiFetch } from "@/lib/api";
import { esSinPermiso, fallaDe, type Falla } from "@/lib/carga";
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

type Bloque<T> = { datos: T | null; falla: Falla | null };

/**
 * Cada bloque falla por su cuenta: que el usuario no tenga `sales.leer` no
 * puede dejar el tablero entero en blanco.
 *
 * Pero **no tener permiso y no haber podido preguntar no son lo mismo**, y
 * hasta 2026-08-07 acá se trataban igual: cualquier `ApiError` devolvía
 * `null` y el bloque desaparecía sin decir nada. Un 500 o un proxy caído se
 * veían como "este tablero no es tuyo". Ahora solo el 403 se traga —el
 * servidor contestó y dijo que no—; todo lo demás viaja en `falla` para que
 * la pantalla lo muestre con su reintento.
 *
 * `datos: null` con `falla: null` es, entonces, exactamente "sin permiso".
 */
async function bloque<T>(promesa: Promise<T>, que: string): Promise<Bloque<T>> {
  try {
    return { datos: await promesa, falla: null };
  } catch (e) {
    const falla = fallaDe(e, `No se pudo cargar ${que}.`);
    return { datos: null, falla: esSinPermiso(falla) ? null : falla };
  }
}

/** Tarjeta de indicador. La cifra va en monoespaciada y a peso alto: es lo
 * único que se mira desde lejos, y tres tarjetas en fila solo se comparan si
 * los dígitos ocupan el mismo ancho.
 *
 * `alerta` pinta con `secondary` (el rojo profundo), no con `accent`: el
 * acento significa "activo/conforme" en las 30 insignias de estado del ERP.
 * Un stock bajo mínimo pintado del mismo color que "recibida" decía justo lo
 * contrario de lo que pasaba. */
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
    <article className="rounded-lg border border-border bg-card p-4 transition-shadow hover:shadow-sm">
      <h2 className="rotulo">{titulo}</h2>
      <p className={`cifra mt-2 text-3xl font-semibold ${alerta ? "text-secondary" : ""}`}>
        {valor}
      </p>
      {detalle && <p className="cifra mt-0.5 text-sm text-gray">{detalle}</p>}
    </article>
  );
}

export default async function DashboardPage() {
  // `empresa_id` sale de `/users/me` (verificado por la API), ya no del JWT
  // decodificado sin firma en el cliente.
  const { token, usuario } = await obtenerSesion();
  if (!usuario.empresa_id) {
    return (
      <p className="rounded-lg border border-secondary/30 bg-secondary/5 p-4 text-sm text-secondary">
        Tu usuario no tiene una empresa asignada — no se puede cargar el dashboard.
      </p>
    );
  }

  const [resumen, catalogo, sucursales, tableros, roles] = await Promise.all([
    bloque(
      apiFetch<DashboardResumen>(
        `/api/v1/dashboard/resumen?empresa_id=${usuario.empresa_id}`,
        { token },
      ),
      "el resumen del día",
    ),
    bloque(apiFetch<Catalogo>("/api/v1/reportes", { token }), "el catálogo de reportes"),
    bloque(apiFetch<Sucursal[]>("/api/v1/sucursales", { token }), "las sucursales"),
    bloque(apiFetch<TableroGuardado[]>("/api/v1/tableros", { token }), "los tableros"),
    bloque(apiFetch<Rol[]>("/api/v1/tableros/roles", { token }), "los roles"),
  ]);

  const fallas = [resumen, catalogo, sucursales, tableros, roles]
    .map((b) => b.falla)
    .filter((f): f is Falla => f !== null);

  // Sin catálogo no hay tablero que armar. Distinguir por qué falta es todo
  // el punto: "no es tuyo" se acepta y se explica, "no se pudo traer" se
  // reintenta.
  if (!catalogo.datos) {
    return catalogo.falla ? (
      <AvisoFallo fallas={[catalogo.falla]} />
    ) : (
      <p className="rounded border border-accent/40 bg-accent/5 p-4 text-sm text-accent">
        Tu usuario no tiene permiso para ver el dashboard.
      </p>
    );
  }

  // Un usuario solo filtra por las sucursales de su alcance: pedir otra
  // devuelve 403 igual, pero ofrecérsela en el checkbox sería mentirle.
  const visibles = (sucursales.datos ?? []).filter(
    (s) => usuario.sucursales.length === 0 || usuario.sucursales.includes(s.id),
  );

  return (
    <div className="flex flex-col gap-6">
      <AvisoFallo fallas={fallas} />

      {resumen.datos && (
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Kpi
            titulo="Ventas de hoy"
            valor={resumen.datos.ventas_hoy.cantidad}
            detalle={`S/ ${resumen.datos.ventas_hoy.total}`}
          />
          <Kpi
            titulo="Stock bajo mínimo"
            valor={resumen.datos.stock_bajo_minimo}
            alerta={resumen.datos.stock_bajo_minimo > 0}
          />
          <Kpi
            titulo="Cajas abiertas"
            valor={resumen.datos.cajas_abiertas.length}
            detalle={
              resumen.datos.cajas_abiertas.length > 0
                ? `Apertura S/ ${resumen.datos.cajas_abiertas[0].monto_apertura}`
                : undefined
            }
          />
        </section>
      )}

      <Tablero
        catalogo={catalogo.datos}
        sucursales={visibles}
        tableros={tableros.datos ?? []}
        roles={roles.datos ?? []}
      />
    </div>
  );
}
