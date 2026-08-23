"use client";

/**
 * Gráficos del tablero, sobre Recharts vía el wrapper de shadcn.
 *
 * Antes eran divs con ancho porcentual y una `<polyline>` a mano. Se
 * cambiaron al instalar Recharts porque lo que faltaba no era el dibujo
 * sino el tooltip con hit-testing: mirando una serie de 30 días, saber
 * cuánto vendió un día concreto exigía cambiar la tarjeta a tabla.
 *
 * Los colores salen de `--chart-1..5`, que en `globals.css` apuntan a la
 * marca — un gráfico no elige su paleta por su cuenta.
 */

import Link from "next/link";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  XAxis,
  YAxis,
} from "recharts";

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { rutaDestino } from "@/lib/destinos";
import { aNumero, formatear, type Columna, type Fila } from "@/lib/reportes";

type Props = {
  filas: Fila[];
  columnas: Columna[];
  etiqueta: string;
  valor: string;
};

const COLORES = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
];

function tipoDe(columnas: Columna[], clave: string) {
  return columnas.find((c) => c.clave === clave)?.tipo ?? "numero";
}

function tituloDe(columnas: Columna[], clave: string) {
  return columnas.find((c) => c.clave === clave)?.titulo ?? clave;
}

function Vacio() {
  return (
    <p className="flex h-full items-center justify-center text-sm text-muted-foreground">
      Sin datos en este rango.
    </p>
  );
}

/** Recharts necesita números; el backend manda los montos como texto exacto
 * para no perder centavos. La conversión ocurre acá y solo para dibujar —
 * el valor original se conserva para el tooltip. */
function aSerie(filas: Fila[], etiqueta: string, valor: string) {
  return filas.map((f) => ({
    etiqueta: String(f[etiqueta] ?? ""),
    valor: aNumero(f[valor]),
    crudo: f[valor],
  }));
}

function configDe(columnas: Columna[], valor: string): ChartConfig {
  return { valor: { label: tituloDe(columnas, valor), color: "var(--chart-1)" } };
}

export function GraficoBarras({ filas, columnas, etiqueta, valor }: Props) {
  if (filas.length === 0) return <Vacio />;
  const tipo = tipoDe(columnas, valor);
  const datos = aSerie(filas, etiqueta, valor);

  return (
    <ChartContainer config={configDe(columnas, valor)} className="h-full w-full">
      {/* Barras horizontales: las etiquetas son nombres (sucursal, producto,
          proveedor) y en vertical se solapan o se rotan hasta ser ilegibles. */}
      <BarChart accessibilityLayer data={datos} layout="vertical" margin={{ left: 8 }}>
        <CartesianGrid horizontal={false} />
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="etiqueta"
          width={110}
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 12 }}
        />
        <ChartTooltip
          content={
            <ChartTooltipContent
              formatter={(_v, _n, item) => formatear(item?.payload?.crudo, tipo)}
            />
          }
        />
        <Bar dataKey="valor" radius={4}>
          {datos.map((_, i) => (
            <Cell key={i} fill={COLORES[i % COLORES.length]} />
          ))}
        </Bar>
      </BarChart>
    </ChartContainer>
  );
}

export function GraficoLineas({ filas, columnas, etiqueta, valor }: Props) {
  if (filas.length === 0) return <Vacio />;
  const tipoValor = tipoDe(columnas, valor);
  const tipoEtiqueta = tipoDe(columnas, etiqueta);
  const datos = aSerie(filas, etiqueta, valor);

  return (
    <ChartContainer config={configDe(columnas, valor)} className="h-full w-full">
      <LineChart accessibilityLayer data={datos} margin={{ left: 4, right: 8 }}>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="etiqueta"
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 11 }}
          tickFormatter={(v) => formatear(v, tipoEtiqueta)}
          minTickGap={24}
        />
        <YAxis hide />
        <ChartTooltip
          content={
            <ChartTooltipContent
              labelFormatter={(v) => formatear(String(v), tipoEtiqueta)}
              formatter={(_v, _n, item) => formatear(item?.payload?.crudo, tipoValor)}
            />
          }
        />
        <Line
          dataKey="valor"
          type="monotone"
          stroke="var(--chart-1)"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4 }}
        />
      </LineChart>
    </ChartContainer>
  );
}

export function TablaReporte({ filas, columnas }: Omit<Props, "etiqueta" | "valor">) {
  if (filas.length === 0) return <Vacio />;
  // La columna `tipo="id"` no se dibuja: es el ancla del enlace de la fila
  // (ADR-036). Un reporte de problemas que no lleva al registro deja al que
  // lo lee saliendo a buscarlo a mano.
  const ancla = columnas.find((c) => c.tipo === "id" && c.enlace);
  const visibles = columnas.filter((c) => c.tipo !== "id");
  return (
    <div className="h-full overflow-auto">
      <Table>
        <TableHeader className="sticky top-0 bg-background">
          <TableRow>
            {visibles.map((c) => (
              <TableHead
                key={c.clave}
                className={c.tipo === "texto" ? "" : "text-right"}
              >
                {c.titulo}
              </TableHead>
            ))}
            {ancla && <TableHead className="w-8" />}
          </TableRow>
        </TableHeader>
        <TableBody>
          {filas.map((fila, i) => {
            const destino = ancla
              ? rutaDestino(ancla.enlace, String(fila[ancla.clave] ?? ""))
              : null;
            return (
              <TableRow key={i}>
                {visibles.map((c) => (
                  <TableCell
                    key={c.clave}
                    className={
                      c.tipo === "texto" ? "" : "text-right tabular-nums"
                    }
                  >
                    {formatear(fila[c.clave], c.tipo)}
                  </TableCell>
                ))}
                {ancla && (
                  <TableCell className="text-right">
                    {destino && (
                      <Link
                        href={destino}
                        className="font-semibold text-primary hover:underline"
                        aria-label="Abrir el registro de esta fila"
                      >
                        →
                      </Link>
                    )}
                  </TableCell>
                )}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
