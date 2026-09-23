"use client";

/**
 * Kardex gráfico de un artículo: a cuánto se compró, qué entró y qué salió
 * cada semana, cómo quedó el saldo y cuándo toca volver a comprar.
 *
 * Tres gráficos y no uno con dos ejes: precio (soles) y cantidades (unidades
 * del artículo) no comparten escala, y un doble eje hace que cualquier cruce
 * de líneas parezca significar algo. Las cantidades sí comparten eje entre sí.
 *
 * Entradas en azul y salidas en el color de marca, validados para daltonismo
 * en claro y en oscuro (`--kardex-entrada` en `globals.css`). Cada serie lleva
 * además su nombre en la leyenda: el color nunca es la única pista.
 */

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  XAxis,
  YAxis,
} from "recharts";

import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import {
  diasHasta,
  frecuenciaCompra,
  variacionPrecio,
  type Kardex,
  type PrecioHistorico,
} from "@/lib/kardex";

/** Un día de calendario (`YYYY-MM-DD`) sin que la zona lo corra al anterior. */
function dia(
  iso: string,
  opciones: Intl.DateTimeFormatOptions = { day: "2-digit", month: "short" },
) {
  return new Date(`${iso.slice(0, 10)}T12:00:00Z`).toLocaleDateString("es-PE", {
    timeZone: "UTC",
    ...opciones,
  });
}

const num = (v: string | null | undefined) => (v == null ? 0 : Number(v));
const cifra = (v: number, decimales = 2) =>
  v.toLocaleString("es-PE", { maximumFractionDigits: decimales });

const CONFIG_PRECIO: ChartConfig = {
  costo: { label: "Costo unitario", color: "var(--primary)" },
};
const CONFIG_MOVIMIENTOS: ChartConfig = {
  entradas: { label: "Entradas", color: "var(--kardex-entrada)" },
  salidas: { label: "Salidas", color: "var(--primary)" },
};
const CONFIG_SALDO: ChartConfig = {
  saldo: { label: "Saldo", color: "var(--kardex-entrada)" },
};

function Dato({
  titulo,
  valor,
  detalle,
}: {
  titulo: string;
  valor: string;
  detalle?: string;
}) {
  return (
    <div className="flex flex-col gap-0.5 rounded-lg border border-border bg-card p-3">
      <span className="text-xs font-semibold uppercase text-muted-foreground">
        {titulo}
      </span>
      <span className="cifra text-lg font-semibold text-foreground">
        {valor}
      </span>
      {detalle && (
        <span className="text-xs text-muted-foreground">{detalle}</span>
      )}
    </div>
  );
}

function Tarjeta({
  titulo,
  children,
}: {
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <figure className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
      <figcaption className="text-sm font-semibold text-foreground">
        {titulo}
      </figcaption>
      {children}
    </figure>
  );
}

function Vacio({ texto }: { texto: string }) {
  return (
    <p className="py-10 text-center text-sm text-muted-foreground">{texto}</p>
  );
}

function textoProximaCompra(
  kardex: Kardex,
  hoy: string,
): { valor: string; detalle: string } {
  if (!kardex.proxima_compra) {
    return {
      valor: "—",
      detalle: kardex.consumo_diario
        ? "No se está consumiendo"
        : "Falta una semana de historia",
    };
  }
  const faltan = diasHasta(kardex.proxima_compra, hoy);
  return {
    valor: dia(kardex.proxima_compra, {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }),
    detalle:
      faltan <= 0
        ? "Ya está en el mínimo: comprar hoy"
        : `En ${faltan} día(s), al ritmo actual${kardex.stock_minimo ? "" : " (sin mínimo, contra cero)"}`,
  };
}

function textoCompras(precios: PrecioHistorico[] | null) {
  if (!precios) {
    return {
      frecuencia: { valor: "—", detalle: "Sin acceso a compras" },
      precio: { valor: "—" },
    };
  }
  const frecuencia = frecuenciaCompra(precios.map((p) => p.fecha));
  const variacion = variacionPrecio(precios);
  const ultimo = precios.at(-1);
  return {
    frecuencia: {
      valor: frecuencia ? `Cada ${frecuencia} día(s)` : "—",
      detalle: `${precios.length} recepción(es)`,
    },
    precio: {
      valor: ultimo ? `S/ ${cifra(num(ultimo.costo_unitario), 4)}` : "—",
      detalle:
        variacion === null
          ? undefined
          : `${variacion > 0 ? "+" : ""}${variacion}% vs. la compra anterior`,
    },
  };
}

function Resumen({
  kardex,
  precios,
  unidad,
  hoy,
}: {
  kardex: Kardex;
  precios: PrecioHistorico[] | null;
  unidad: string;
  hoy: string;
}) {
  const proxima = textoProximaCompra(kardex, hoy);
  const compras = textoCompras(precios);
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      <Dato
        titulo="Stock"
        valor={`${cifra(num(kardex.stock))} ${unidad}`}
        detalle={
          kardex.stock_minimo
            ? `Mínimo ${cifra(num(kardex.stock_minimo))}`
            : "Sin mínimo declarado"
        }
      />
      <Dato
        titulo="Consumo diario"
        valor={
          kardex.consumo_diario
            ? `${cifra(num(kardex.consumo_diario))} ${unidad}`
            : "—"
        }
        detalle="Promedio de los últimos 90 días"
      />
      <Dato
        titulo="Próxima compra"
        valor={proxima.valor}
        detalle={proxima.detalle}
      />
      <Dato titulo="Frecuencia de compra" {...compras.frecuencia} />
      <Dato titulo="Último precio" {...compras.precio} />
    </div>
  );
}

function GraficoPrecio({ precios }: { precios: PrecioHistorico[] }) {
  if (precios.length === 0)
    return <Vacio texto="Todavía no se recibió ninguna compra." />;
  const datos = precios.map((p) => ({
    fecha: dia(p.fecha),
    costo: num(p.costo_unitario),
    proveedor: p.proveedor ?? "Proveedor natural",
    cantidad: p.cantidad,
  }));
  return (
    <ChartContainer config={CONFIG_PRECIO} className="h-56 w-full">
      <LineChart
        accessibilityLayer
        data={datos}
        margin={{ left: 4, right: 12, top: 8 }}
      >
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="fecha"
          tickLine={false}
          axisLine={false}
          minTickGap={24}
        />
        <YAxis
          tickLine={false}
          axisLine={false}
          width={48}
          domain={["auto", "auto"]}
        />
        <ChartTooltip
          content={
            <ChartTooltipContent
              formatter={(valor, _n, item) =>
                `S/ ${cifra(Number(valor), 4)} · ${item.payload.proveedor} · ${item.payload.cantidad}`
              }
            />
          }
        />
        <Line
          dataKey="costo"
          type="linear"
          stroke="var(--color-costo)"
          strokeWidth={2}
          dot={{ r: 4, strokeWidth: 2, fill: "var(--card)" }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ChartContainer>
  );
}

function GraficoMovimientos({ kardex }: { kardex: Kardex }) {
  const datos = kardex.semanas.map((s) => ({
    semana: dia(s.semana),
    entradas: num(s.entradas),
    salidas: num(s.salidas),
  }));
  if (datos.every((d) => d.entradas === 0 && d.salidas === 0)) {
    return <Vacio texto="Sin movimientos en el período." />;
  }
  return (
    <ChartContainer config={CONFIG_MOVIMIENTOS} className="h-56 w-full">
      <BarChart
        accessibilityLayer
        data={datos}
        margin={{ left: 4, right: 12, top: 8 }}
        barGap={2}
      >
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="semana"
          tickLine={false}
          axisLine={false}
          minTickGap={24}
        />
        <YAxis tickLine={false} axisLine={false} width={48} />
        <ChartTooltip
          content={
            <ChartTooltipContent labelFormatter={(l) => `Semana del ${l}`} />
          }
        />
        <ChartLegend content={<ChartLegendContent />} />
        <Bar
          dataKey="entradas"
          fill="var(--color-entradas)"
          radius={[4, 4, 0, 0]}
        />
        <Bar
          dataKey="salidas"
          fill="var(--color-salidas)"
          radius={[4, 4, 0, 0]}
        />
      </BarChart>
    </ChartContainer>
  );
}

function GraficoSaldo({ kardex }: { kardex: Kardex }) {
  const datos = kardex.semanas.map((s) => ({
    semana: dia(s.semana),
    saldo: num(s.saldo),
  }));
  const minimo = kardex.stock_minimo ? num(kardex.stock_minimo) : null;
  return (
    <ChartContainer config={CONFIG_SALDO} className="h-56 w-full">
      <AreaChart
        accessibilityLayer
        data={datos}
        margin={{ left: 4, right: 12, top: 8 }}
      >
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="semana"
          tickLine={false}
          axisLine={false}
          minTickGap={24}
        />
        <YAxis tickLine={false} axisLine={false} width={48} />
        <ChartTooltip
          content={
            <ChartTooltipContent
              labelFormatter={(l) => `Cierre de la semana del ${l}`}
            />
          }
        />
        <Area
          dataKey="saldo"
          type="stepAfter"
          stroke="var(--color-saldo)"
          strokeWidth={2}
          fill="var(--color-saldo)"
          fillOpacity={0.12}
        />
        {minimo !== null && (
          <ReferenceLine
            y={minimo}
            stroke="var(--muted-foreground)"
            strokeDasharray="4 4"
            label={{
              value: "Mínimo",
              position: "insideTopRight",
              fill: "var(--muted-foreground)",
              fontSize: 12,
            }}
          />
        )}
      </AreaChart>
    </ChartContainer>
  );
}

/** Las semanas en tabla: el mismo dato sin depender de ver el gráfico. */
function Tabla({ kardex }: { kardex: Kardex }) {
  return (
    <details className="rounded-lg border border-border bg-card p-3 text-sm">
      <summary className="cursor-pointer font-semibold text-foreground">
        Ver como tabla
      </summary>
      <table className="mt-3 w-full">
        <thead className="text-left text-xs uppercase text-muted-foreground">
          <tr>
            <th className="py-1">Semana del</th>
            <th className="py-1 text-right">Entradas</th>
            <th className="py-1 text-right">Salidas</th>
            <th className="py-1 text-right">Saldo</th>
          </tr>
        </thead>
        <tbody className="cifra">
          {[...kardex.semanas].reverse().map((s) => (
            <tr key={s.semana} className="border-t border-border">
              <td className="py-1">
                {dia(s.semana, {
                  day: "2-digit",
                  month: "short",
                  year: "numeric",
                })}
              </td>
              <td className="py-1 text-right">{cifra(num(s.entradas))}</td>
              <td className="py-1 text-right">{cifra(num(s.salidas))}</td>
              <td className="py-1 text-right">{cifra(num(s.saldo))}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

export function KardexArticulo({
  kardex,
  precios,
  unidad,
  hoy,
}: {
  kardex: Kardex;
  /** `null` si el usuario no puede leer compras: se dibuja el resto. */
  precios: PrecioHistorico[] | null;
  unidad: string;
  /** Hoy en la zona del negocio (`YYYY-MM-DD`), del servidor. */
  hoy: string;
}) {
  return (
    <section className="flex flex-col gap-4" aria-label="Kardex del artículo">
      <Resumen kardex={kardex} precios={precios} unidad={unidad} hoy={hoy} />
      <div className="grid gap-4 lg:grid-cols-2">
        {precios && (
          <Tarjeta titulo="Precio de compra">
            <GraficoPrecio precios={precios} />
          </Tarjeta>
        )}
        <Tarjeta titulo={`Entradas y salidas por semana (${unidad})`}>
          <GraficoMovimientos kardex={kardex} />
        </Tarjeta>
        <Tarjeta titulo={`Saldo al cierre de cada semana (${unidad})`}>
          <GraficoSaldo kardex={kardex} />
        </Tarjeta>
      </div>
      <Tabla kardex={kardex} />
    </section>
  );
}
