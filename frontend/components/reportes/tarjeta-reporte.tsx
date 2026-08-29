"use client";

import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Download, GripVertical, X } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import {
  GraficoArea,
  GraficoBarras,
  GraficoLineas,
  GraficoPie,
  TablaReporte,
} from "@/components/reportes/graficos";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ErrorApi } from "@/lib/cliente-api";
import {
  aCsv,
  ALTURAS,
  ANCHOS,
  datosDeReporte,
  descargarCsv,
  exportarXlsx,
  nombreArchivo,
  type Datos,
  type Filtros,
  type Reporte,
  type Tarjeta,
  type Visual,
} from "@/lib/reportes";

type Props = {
  tarjeta: Tarjeta & { uid: string };
  reporte: Reporte;
  filtros: Filtros;
  editando: boolean;
  onCambiar: (cambios: Partial<Tarjeta>) => void;
  onQuitar: () => void;
};

/** Pide los datos del reporte y avisa cómo va. Aparte del componente de
 * presentación porque son dos cosas: el ciclo de vida de una petición y una
 * tarjeta. */
function useDatos(codigo: string, filtros: Filtros) {
  const [datos, setDatos] = useState<Datos | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);

  // `filtros` se serializa para la lista de dependencias: es un objeto nuevo
  // en cada render del padre y compararlo por identidad recargaría siempre.
  const claveFiltros = JSON.stringify(filtros);

  useEffect(() => {
    let vigente = true;
    setCargando(true);
    setError(null);
    datosDeReporte(codigo, JSON.parse(claveFiltros) as Filtros)
      .then((d) => vigente && setDatos(d))
      .catch((e: unknown) => {
        if (!vigente) return;
        setError(
          e instanceof ErrorApi && e.status === 403
            ? "Sin permiso para este reporte."
            : "No se pudo cargar.",
        );
      })
      .finally(() => vigente && setCargando(false));
    // Una respuesta que llega tarde no debe pisar a la del filtro actual.
    return () => {
      vigente = false;
    };
  }, [codigo, claveFiltros]);

  return { datos, error, cargando };
}

function Cuerpo({
  estado,
  visual,
  reporte,
}: {
  estado: ReturnType<typeof useDatos>;
  visual: Visual;
  reporte: Reporte;
}) {
  if (estado.cargando) {
    return <p className="text-sm text-muted-foreground">Cargando…</p>;
  }
  if (estado.error) {
    return <p className="text-sm text-destructive">{estado.error}</p>;
  }
  if (!estado.datos) return null;
  const { filas, columnas } = estado.datos;
  const comun = {
    filas,
    columnas,
    etiqueta: reporte.etiqueta,
    valor: reporte.valor,
  };
  if (visual === "barras") return <GraficoBarras {...comun} />;
  if (visual === "lineas") return <GraficoLineas {...comun} />;
  if (visual === "area") return <GraficoArea {...comun} />;
  if (visual === "pie") return <GraficoPie {...comun} />;
  return <TablaReporte filas={filas} columnas={columnas} />;
}

/** Título de la tarjeta: editable en modo edición, texto plano si no.
 * Aparte del render principal por lo mismo que `Cuerpo`/`Controles`: baja la
 * complejidad ciclomática de `TarjetaReporte` por debajo del límite del
 * lint. */
function Titulo({
  tarjeta,
  reporte,
  titulo,
  editando,
  onCambiar,
}: {
  tarjeta: Tarjeta;
  reporte: Reporte;
  titulo: string;
  editando: boolean;
  onCambiar: (cambios: Partial<Tarjeta>) => void;
}) {
  if (!editando) return <CardTitle className="truncate text-sm">{titulo}</CardTitle>;
  return (
    <Input
      value={tarjeta.titulo ?? ""}
      placeholder={reporte.nombre}
      onChange={(e) => onCambiar({ titulo: e.target.value || null })}
      aria-label={`Título de ${reporte.nombre}`}
      className="h-7 min-w-0 text-sm"
    />
  );
}

function Controles({
  tarjeta,
  reporte,
  onCambiar,
  onQuitar,
}: {
  tarjeta: Tarjeta;
  reporte: Reporte;
  onCambiar: (cambios: Partial<Tarjeta>) => void;
  onQuitar: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-end gap-1.5">
      <Select
        items={Object.fromEntries(reporte.visuales.map((v) => [v, v]))}
        value={tarjeta.visual}
        onValueChange={(v) => onCambiar({ visual: v as Visual })}
      >
        <SelectTrigger size="sm" className="w-24" aria-label="Visualización">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {reporte.visuales.map((v) => (
            <SelectItem key={v} value={v}>
              {v}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select
        items={{ "1": "1/4", "2": "2/4", "3": "3/4", "4": "4/4" }}
        value={String(tarjeta.ancho)}
        onValueChange={(v) => onCambiar({ ancho: Number(v) })}
      >
        <SelectTrigger size="sm" className="w-20" aria-label="Ancho">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {[1, 2, 3, 4].map((n) => (
            <SelectItem key={n} value={String(n)}>
              {n}/4
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select
        items={{ chico: "Bajo", mediano: "Medio", grande: "Alto" }}
        value={tarjeta.alto}
        onValueChange={(v) => onCambiar({ alto: v as Tarjeta["alto"] })}
      >
        <SelectTrigger size="sm" className="w-24" aria-label="Alto">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="chico">Bajo</SelectItem>
          <SelectItem value="mediano">Medio</SelectItem>
          <SelectItem value="grande">Alto</SelectItem>
        </SelectContent>
      </Select>
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={onQuitar}
        aria-label={`Quitar ${reporte.nombre}`}
        className="text-destructive"
      >
        <X className="size-4" />
      </Button>
    </div>
  );
}

export function TarjetaReporte({
  tarjeta,
  reporte,
  filtros,
  editando,
  onCambiar,
  onQuitar,
}: Props) {
  const estado = useDatos(tarjeta.codigo, filtros);
  const datos = estado.datos;
  const titulo = tarjeta.titulo || reporte.nombre;
  const filas = datos?.filas.length ?? 0;

  // dnd-kit: el arrastre se activa por el asa, no por la tarjeta entera —
  // así se puede seguir seleccionando texto de una tabla en modo edición.
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: tarjeta.uid, disabled: !editando });

  const exportar = () => {
    if (!datos) return;
    descargarCsv(nombreArchivo(titulo, datos), aCsv(datos.columnas, datos.filas));
  };

  const [exportandoXlsx, setExportandoXlsx] = useState(false);
  const exportarCompleto = () => {
    setExportandoXlsx(true);
    exportarXlsx(tarjeta.codigo, filtros)
      .catch(() => toast(`No se pudo exportar «${titulo}».`))
      .finally(() => setExportandoXlsx(false));
  };

  return (
    <Card
      ref={setNodeRef}
      style={{ transform: CSS.Translate.toString(transform), transition }}
      className={`${ANCHOS[tarjeta.ancho] ?? ANCHOS[2]} gap-3 py-4 ${
        isDragging ? "z-10 opacity-70 shadow-lg" : ""
      }`}
    >
      <CardHeader className="gap-1 px-4">
        <div className="flex items-start justify-between gap-2">
          <div className="flex min-w-0 items-center gap-1">
            {editando && (
              <button
                type="button"
                className="cursor-grab touch-none text-muted-foreground active:cursor-grabbing print:hidden"
                aria-label={`Mover ${titulo}`}
                {...attributes}
                {...listeners}
              >
                <GripVertical className="size-4" />
              </button>
            )}
            <Titulo
              tarjeta={tarjeta}
              reporte={reporte}
              titulo={titulo}
              editando={editando}
              onCambiar={onCambiar}
            />
          </div>
          <div className="flex shrink-0 gap-1.5 print:hidden">
            <Button
              variant="outline"
              size="sm"
              onClick={exportar}
              disabled={filas === 0}
              title={`Descargar CSV (${filas} filas, las que se ven)`}
              aria-label={`Exportar ${reporte.nombre} a CSV`}
            >
              <Download className="size-3.5" />
              CSV
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={exportarCompleto}
              disabled={exportandoXlsx}
              title="Descargar el dataset completo del rango (hasta 50 000 filas), no solo las que se ven"
              aria-label={`Exportar ${reporte.nombre} completo a Excel`}
            >
              <Download className="size-3.5" />
              {exportandoXlsx ? "…" : "XLSX"}
            </Button>
          </div>
        </div>
        {!reporte.filtra_sucursal && (
          <Badge variant="secondary" className="w-fit text-xs font-normal">
            No filtra por sucursal
          </Badge>
        )}
        {editando && (
          <Controles
            tarjeta={tarjeta}
            reporte={reporte}
            onCambiar={onCambiar}
            onQuitar={onQuitar}
          />
        )}
      </CardHeader>
      <CardContent className={`${ALTURAS[tarjeta.alto]} min-h-0 px-4`}>
        <Cuerpo estado={estado} visual={tarjeta.visual} reporte={reporte} />
      </CardContent>
    </Card>
  );
}
