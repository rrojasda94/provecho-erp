"use client";

import { CalendarIcon, ChevronDown } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Filtros, Sucursal } from "@/lib/reportes";

type Props = {
  filtros: Filtros;
  rangos: Record<string, string>;
  sucursales: Sucursal[];
  onCambiar: (filtros: Filtros) => void;
};

/** `2026-08-04` ↔ Date, sin pasar por `new Date("2026-08-04")`, que lo
 * interpreta como UTC y en Perú devuelve el día anterior. */
function aFecha(iso: string | null): Date | undefined {
  if (!iso) return undefined;
  const [a, m, d] = iso.split("-").map(Number);
  return new Date(a, m - 1, d);
}

function aIso(fecha: Date | undefined): string | null {
  if (!fecha) return null;
  const mes = String(fecha.getMonth() + 1).padStart(2, "0");
  const dia = String(fecha.getDate()).padStart(2, "0");
  return `${fecha.getFullYear()}-${mes}-${dia}`;
}

function SelectorFecha({
  id,
  etiqueta,
  valor,
  onCambiar,
}: {
  id: string;
  etiqueta: string;
  valor: string | null;
  onCambiar: (iso: string | null) => void;
}) {
  const [abierto, setAbierto] = useState(false);
  const fecha = aFecha(valor);
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{etiqueta}</Label>
      <Popover open={abierto} onOpenChange={setAbierto}>
        <PopoverTrigger
          render={
            <Button id={id} variant="outline" className="w-40 justify-start font-normal">
              <CalendarIcon className="size-4" />
              {fecha ? fecha.toLocaleDateString("es-PE") : "Elegir"}
            </Button>
          }
        />
        <PopoverContent className="w-auto p-0" align="start">
          <Calendar
            mode="single"
            selected={fecha}
            onSelect={(d) => {
              onCambiar(aIso(d));
              setAbierto(false);
            }}
            autoFocus
          />
        </PopoverContent>
      </Popover>
    </div>
  );
}

function SelectorSucursales({
  filtros,
  sucursales,
  onCambiar,
}: Omit<Props, "rangos">) {
  const alternar = (id: string) => {
    const ids = filtros.sucursal_ids.includes(id)
      ? filtros.sucursal_ids.filter((s) => s !== id)
      : [...filtros.sucursal_ids, id];
    onCambiar({ ...filtros, sucursal_ids: ids });
  };

  const n = filtros.sucursal_ids.length;
  const resumen = n === 0 ? "Todas mis sucursales" : `${n} seleccionada${n > 1 ? "s" : ""}`;

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-medium">Sucursales</span>
      <Popover>
        <PopoverTrigger
          render={
            <Button variant="outline" className="w-56 justify-between font-normal">
              {resumen}
              <ChevronDown className="size-4 opacity-60" />
            </Button>
          }
        />
        <PopoverContent className="w-56 p-2" align="start">
          {sucursales.length === 0 && (
            <p className="p-1 text-xs text-muted-foreground">
              Sin sucursales asignadas.
            </p>
          )}
          <div className="flex max-h-64 flex-col gap-1 overflow-y-auto">
            {sucursales.map((s) => (
              <Label
                key={s.id}
                className="flex cursor-pointer items-center gap-2 rounded px-1 py-1.5 font-normal hover:bg-accent/40"
              >
                <Checkbox
                  checked={filtros.sucursal_ids.includes(s.id)}
                  onCheckedChange={() => alternar(s.id)}
                />
                <span className="truncate">{s.nombre}</span>
              </Label>
            ))}
          </div>
          {n > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="mt-1 w-full justify-start"
              onClick={() => onCambiar({ ...filtros, sucursal_ids: [] })}
            >
              Limpiar selección
            </Button>
          )}
        </PopoverContent>
      </Popover>
    </div>
  );
}

export function FiltrosTablero({ filtros, rangos, sucursales, onCambiar }: Props) {
  const personalizado = filtros.preset === "personalizado";

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-lg border bg-card p-3">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="preset">Rango</Label>
        {/* `items` no es opcional en Base UI: sin él, `Select.Value` pinta
            el valor crudo (`mes_actual`) en vez de la etiqueta. */}
        <Select
          items={rangos}
          value={filtros.preset}
          onValueChange={(v) => onCambiar({ ...filtros, preset: String(v) })}
        >
          <SelectTrigger id="preset" className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(rangos).map(([codigo, etiqueta]) => (
              <SelectItem key={codigo} value={codigo}>
                {etiqueta}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {personalizado && (
        <>
          <SelectorFecha
            id="desde"
            etiqueta="Desde"
            valor={filtros.desde}
            onCambiar={(iso) => onCambiar({ ...filtros, desde: iso })}
          />
          <SelectorFecha
            id="hasta"
            etiqueta="Hasta"
            valor={filtros.hasta}
            onCambiar={(iso) => onCambiar({ ...filtros, hasta: iso })}
          />
        </>
      )}

      <SelectorSucursales
        filtros={filtros}
        sucursales={sucursales}
        onCambiar={onCambiar}
      />

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="limite">Filas</Label>
        <Input
          id="limite"
          type="number"
          min={1}
          max={500}
          className="w-24"
          value={filtros.limite}
          onChange={(e) =>
            onCambiar({ ...filtros, limite: Number(e.target.value) || 1 })
          }
        />
      </div>
    </div>
  );
}
