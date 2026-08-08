"use client";

import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  rectSortingStrategy,
  SortableContext,
  sortableKeyboardCoordinates,
} from "@dnd-kit/sortable";
import { Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { FiltrosTablero } from "@/components/reportes/filtros-tablero";
import { TarjetaReporte } from "@/components/reportes/tarjeta-reporte";
import { useTablero } from "@/components/reportes/use-tablero";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  Catalogo,
  Reporte,
  Rol,
  Sucursal,
  Tablero as TableroGuardado,
  Tarjeta,
} from "@/lib/reportes";

type Props = {
  catalogo: Catalogo;
  sucursales: Sucursal[];
  tableros: TableroGuardado[];
  roles: Rol[];
};

const SIN_ROL = "__privado__";

function tarjetaNueva(reporte: Reporte): Tarjeta {
  return {
    codigo: reporte.codigo,
    titulo: null,
    visual: reporte.visual,
    ancho: 2,
    alto: "mediano",
  };
}

function SelectorDeTablero({
  guardados,
  actual,
  onSeleccionar,
}: {
  guardados: TableroGuardado[];
  actual: TableroGuardado | null;
  onSeleccionar: (id: string) => void;
}) {
  if (guardados.length === 0) return null;
  return (
    <div className="flex items-center gap-2">
      <Label htmlFor="tablero">Tablero</Label>
      <Select
        items={Object.fromEntries(guardados.map((x) => [x.id, x.nombre]))}
        value={actual?.id ?? ""}
        onValueChange={(v) => onSeleccionar(String(v))}
      >
        <SelectTrigger id="tablero" size="sm" className="w-56">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {guardados.map((t) => (
            <SelectItem key={t.id} value={t.id}>
              {t.nombre}
              {t.predeterminado ? " ★" : ""}
              {t.propio ? "" : ` (de ${t.compartido_por})`}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function BarraAcciones({
  guardados,
  actual,
  editable,
  editando,
  onSeleccionar,
  onAlternarEdicion,
  onGuardar,
  onEliminar,
}: {
  guardados: TableroGuardado[];
  actual: TableroGuardado | null;
  editable: boolean;
  editando: boolean;
  onSeleccionar: (id: string) => void;
  onAlternarEdicion: () => void;
  onGuardar: (comoNuevo: boolean) => void;
  onEliminar: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <SelectorDeTablero
        guardados={guardados}
        actual={actual}
        onSeleccionar={onSeleccionar}
      />
      {editable && (
        <>
          <Button variant="outline" size="sm" onClick={onAlternarEdicion}>
            {editando ? "Listo" : "Editar"}
          </Button>
          <Button size="sm" onClick={() => onGuardar(false)}>
            Guardar
          </Button>
        </>
      )}
      {/* Siempre disponible: es la vía para quedarse con una copia propia de
          un tablero que otro compartió. */}
      <Button variant="outline" size="sm" onClick={() => onGuardar(true)}>
        Guardar como…
      </Button>
      {actual && editable && (
        <Button variant="outline" size="sm" onClick={onEliminar} className="text-destructive">
          Eliminar
        </Button>
      )}
      {actual && !editable && (
        <span className="text-xs text-muted-foreground">
          Compartido por {actual.compartido_por} — solo lectura
        </span>
      )}
    </div>
  );
}

function SelectorDeReportes({
  reportes,
  onAgregar,
}: {
  reportes: Reporte[];
  onAgregar: (r: Reporte) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-dashed p-3">
      <span className="text-sm font-medium text-muted-foreground">
        Agregar reporte:
      </span>
      {reportes.map((r) => (
        <Button
          key={r.codigo}
          variant="outline"
          size="sm"
          onClick={() => onAgregar(r)}
          title={r.descripcion}
        >
          <Plus className="size-3.5" />
          {r.nombre}
        </Button>
      ))}
    </div>
  );
}

function Compartir({
  roles,
  rolId,
  onCambiar,
}: {
  roles: Rol[];
  rolId: string | null;
  onCambiar: (rolId: string | null) => void;
}) {
  if (roles.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-dashed p-3">
      <Label htmlFor="compartir">Compartir con el rol</Label>
      <Select
        items={{
          [SIN_ROL]: "Nadie (privado)",
          ...Object.fromEntries(roles.map((r) => [r.id, r.nombre])),
        }}
        value={rolId ?? SIN_ROL}
        onValueChange={(v) => onCambiar(v === SIN_ROL ? null : String(v))}
      >
        <SelectTrigger id="compartir" size="sm" className="w-48">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={SIN_ROL}>Nadie (privado)</SelectItem>
          {roles.map((r) => (
            <SelectItem key={r.id} value={r.id}>
              {r.nombre}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <span className="text-xs text-muted-foreground">
        Se comparte la disposición, no los datos: cada tarjeta sigue exigiendo el
        permiso de su módulo.
      </span>
    </div>
  );
}

export function Tablero({ catalogo, sucursales, tableros, roles }: Props) {
  const t = useTablero(tableros);
  const [editando, setEditando] = useState(t.tarjetas.length === 0);
  // `null` = nadie está pidiendo nombre; `true`/`false` = se está pidiendo, y
  // el valor es el `comoNuevo` con el que hay que guardar cuando confirme.
  const [pidiendoNombre, setPidiendoNombre] = useState<boolean | null>(null);
  const [nombreBorrador, setNombreBorrador] = useState("");

  // Un puntero tiene que moverse 6 px antes de considerarse arrastre: sin
  // eso, un clic en el asa se interpretaría como un arrastre de 0 px y
  // bloquearía el resto de los controles de la tarjeta.
  const sensores = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const porCodigo = useMemo(
    () => new Map(catalogo.reportes.map((r) => [r.codigo, r])),
    [catalogo.reportes],
  );

  const editable = !t.actual || t.actual.propio;

  // El aviso se emite como toast en vez de quedar en un `<span>` gris que
  // nadie mira cuando termina de guardar.
  useEffect(() => {
    if (t.aviso) toast(t.aviso);
  }, [t.aviso]);

  function alSoltar(evento: DragEndEvent) {
    const { active, over } = evento;
    if (over && active.id !== over.id) {
      t.moverTarjeta(String(active.id), String(over.id));
    }
  }

  /** Guardar sobre un tablero propio ya existente no pregunta nada: conserva
   * su nombre. Solo el alta y "Guardar como…" piden uno.
   *
   * El nombre se pide en un campo de la página y no con `window.prompt`: el
   * prompt nativo no se puede etiquetar, no se puede estilar y ningún
   * automatismo de navegador lo alcanza — el guardado quedaba sin forma de
   * probarse de punta a punta. */
  async function pedirNombreYGuardar(comoNuevo: boolean) {
    if (!comoNuevo && t.actual) {
      if (await t.guardar(t.actual.nombre, false)) setEditando(false);
      return;
    }
    setNombreBorrador(t.actual?.nombre ?? "Mi tablero");
    setPidiendoNombre(comoNuevo);
  }

  async function confirmarNombre() {
    const nombre = nombreBorrador.trim();
    if (!nombre || pidiendoNombre === null) return;
    const comoNuevo = pidiendoNombre;
    setPidiendoNombre(null);
    if (await t.guardar(nombre, comoNuevo)) setEditando(false);
  }

  function confirmarEliminar() {
    if (t.actual && window.confirm(`¿Eliminar el tablero "${t.actual.nombre}"?`)) {
      void t.eliminar();
    }
  }

  if (catalogo.reportes.length === 0) {
    return (
      <p className="rounded-lg border p-4 text-sm text-muted-foreground">
        Tu usuario no tiene permiso sobre ningún reporte todavía.
      </p>
    );
  }

  return (
    <section className="flex flex-col gap-4">
      <BarraAcciones
        guardados={t.guardados}
        actual={t.actual}
        editable={editable}
        editando={editando}
        onSeleccionar={t.seleccionar}
        onAlternarEdicion={() => setEditando((v) => !v)}
        onGuardar={(comoNuevo) => void pedirNombreYGuardar(comoNuevo)}
        onEliminar={confirmarEliminar}
      />

      <Dialog
        open={pidiendoNombre !== null}
        onOpenChange={(abierto) => {
          if (!abierto) setPidiendoNombre(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nombre del tablero</DialogTitle>
          </DialogHeader>
          <form
            className="flex flex-col gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              void confirmarNombre();
            }}
          >
            <div className="flex flex-col gap-2">
              <Label htmlFor="nombre-tablero">Nombre</Label>
              <Input
                id="nombre-tablero"
                autoFocus
                value={nombreBorrador}
                onChange={(e) => setNombreBorrador(e.target.value)}
              />
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setPidiendoNombre(null)}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={!nombreBorrador.trim()}>
                Guardar
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <FiltrosTablero
        filtros={t.filtros}
        rangos={catalogo.rangos}
        sucursales={sucursales}
        onCambiar={t.setFiltros}
      />

      {editando && editable && (
        <>
          <SelectorDeReportes
            reportes={catalogo.reportes}
            onAgregar={(r) => t.agregarTarjeta(tarjetaNueva(r))}
          />
          <Compartir roles={roles} rolId={t.rolId} onCambiar={t.setRolId} />
        </>
      )}

      {t.tarjetas.length === 0 ? (
        <p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
          Tablero vacío. Agregá un reporte para empezar.
        </p>
      ) : (
        <DndContext
          sensors={sensores}
          collisionDetection={closestCenter}
          onDragEnd={alSoltar}
        >
          <SortableContext
            items={t.tarjetas.map((x) => x.uid)}
            strategy={rectSortingStrategy}
          >
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
              {t.tarjetas.map((tarjeta) => {
                const reporte = porCodigo.get(tarjeta.codigo);
                if (!reporte) return null;
                return (
                  <TarjetaReporte
                    // `uid` y no el índice: con el índice, arrastrar
                    // remontaría la tarjeta y volvería a pedir sus datos.
                    key={tarjeta.uid}
                    tarjeta={tarjeta}
                    reporte={reporte}
                    filtros={t.filtros}
                    editando={editando && editable}
                    onCambiar={(cambios) => t.cambiarTarjeta(tarjeta.uid, cambios)}
                    onQuitar={() => t.quitarTarjeta(tarjeta.uid)}
                  />
                );
              })}
            </div>
          </SortableContext>
        </DndContext>
      )}
    </section>
  );
}
