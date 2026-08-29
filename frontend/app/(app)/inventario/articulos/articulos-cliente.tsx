"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useRouter } from "next/navigation";
import { useMemo } from "react";

import { BOTON_FILA, DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { Combobox } from "@/components/ui/combobox";
import { RUTA_EXPORTAR_ARTICULOS } from "@/lib/catalogo";

import { crearArticuloAction, editarArticuloAction } from "./actions";
import { ImportarArticulos } from "./importar-articulos";

export type Articulo = {
  id: string;
  id_interno: string;
  nombre: string;
  unidad_medida_id: string;
  tipo: string;
  categoria_id: string | null;
  costo_promedio: string;
  archivado: boolean;
  controla_lote: boolean;
  dias_alerta_vencimiento: number | null;
};

export type Categoria = { id: string; nombre: string };
export type UnidadMedida = { id: string; nombre: string; decimales: number };

// README del módulo: enum extensible, hoy estos 6 valores.
const TIPOS_ARTICULO = [
  "insumo",
  "subreceta",
  "mercaderia",
  "empaque",
  "repuesto",
  "suministro",
] as const;

function SelectorTipo({ valor }: { valor?: string }) {
  return (
    <label className="flex flex-col gap-1 text-sm font-semibold">
      Tipo
      <select name="tipo" defaultValue={valor ?? "insumo"}>
        {TIPOS_ARTICULO.map((tipo) => (
          <option key={tipo} value={tipo}>
            {tipo}
          </option>
        ))}
      </select>
    </label>
  );
}

function SelectorCategoria({
  categorias,
  valor,
}: {
  categorias: Categoria[];
  valor?: string | null;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm font-semibold">
      Categoría (opcional)
      <Combobox
        name="categoria_id"
        etiqueta="Categoría"
        defaultValue={valor ?? ""}
        marcador="Sin categoría"
        opciones={categorias.map((cat) => ({ valor: cat.id, etiqueta: cat.nombre }))}
      />
    </label>
  );
}

function DialogoNuevoArticulo({
  categorias,
  unidadesMedida,
}: {
  categorias: Categoria[];
  unidadesMedida: UnidadMedida[];
}) {
  const sinUnidades = unidadesMedida.length === 0;

  return (
    <DialogoFormulario
      titulo="Nuevo artículo"
      disparador="+ Nuevo artículo"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearArticuloAction}
      envioDeshabilitado={sinUnidades}
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Código interno (máx. 4)
        <input name="id_interno" required maxLength={4} placeholder="H001" />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input name="nombre" required maxLength={150} />
      </label>
      <SelectorTipo />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Unidad de medida
        {sinUnidades ? (
          <span className="text-xs font-normal text-secondary">
            No hay unidades de medida cargadas — no se puede crear un artículo todavía.
          </span>
        ) : (
          <Combobox
            name="unidad_medida_id"
            etiqueta="Unidad de medida"
            requerido
            marcador="Elegir..."
            opciones={unidadesMedida.map((u) => ({ valor: u.id, etiqueta: u.nombre }))}
          />
        )}
      </label>
      <SelectorCategoria categorias={categorias} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Costo promedio inicial
        <input name="costo_promedio" type="number" min={0} step="0.01" defaultValue="0" />
      </label>
    </DialogoFormulario>
  );
}

/** Corrección de un artículo ya creado.
 *
 * La unidad de medida no se ofrece y no es un olvido: el stock, los
 * movimientos y las recetas ya cargadas están expresados en la unidad
 * actual, así que cambiarla no convierte nada — reinterpreta en silencio
 * todo lo que ya existe. Un artículo con la unidad equivocada se archiva y
 * se crea de nuevo. */
function DialogoEditarArticulo({
  articulo,
  categorias,
  nombreUdm,
}: {
  articulo: Articulo;
  categorias: Categoria[];
  nombreUdm: string;
}) {
  return (
    <DialogoFormulario
      titulo="Editar artículo"
      disparador="Editar"
      claseDisparador={BOTON_FILA}
      accion={editarArticuloAction}
      ayuda={`Unidad de medida: ${nombreUdm} — no se cambia, el stock y las recetas ya están expresados en ella.`}
    >
      <input type="hidden" name="id" value={articulo.id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Código interno (máx. 4)
        <input name="id_interno" required maxLength={4} defaultValue={articulo.id_interno} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input name="nombre" required maxLength={150} defaultValue={articulo.nombre} />
      </label>
      <SelectorTipo valor={articulo.tipo} />
      <SelectorCategoria categorias={categorias} valor={articulo.categoria_id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Costo promedio
        <input
          name="costo_promedio"
          type="number"
          min={0}
          step="0.01"
          defaultValue={articulo.costo_promedio}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Días de alerta de vencimiento (opcional)
        <input
          name="dias_alerta_vencimiento"
          type="number"
          min={0}
          max={3650}
          defaultValue={articulo.dias_alerta_vencimiento ?? ""}
          placeholder="Con cuánta anticipación se avisa 'por vencer'"
        />
      </label>
      <label className="flex items-center gap-2 text-sm font-semibold">
        <input type="checkbox" name="controla_lote" defaultChecked={articulo.controla_lote} />
        Controla lote (perecible o trazable → FEFO)
      </label>
      <label className="flex items-center gap-2 text-sm font-semibold">
        <input type="checkbox" name="archivado" defaultChecked={articulo.archivado} />
        Archivado
      </label>
    </DialogoFormulario>
  );
}

export function ArticulosCliente({
  articulos,
  categorias,
  unidadesMedida,
}: {
  articulos: Articulo[];
  categorias: Categoria[];
  unidadesMedida: UnidadMedida[];
}) {
  // La pantalla se renderiza en el servidor: tras importar hay que pedirle
  // los datos de nuevo, no mantener una copia acá.
  const router = useRouter();
  const nombreCategoria = useMemo(
    () => new Map(categorias.map((c) => [c.id, c.nombre])),
    [categorias],
  );
  const nombreUdm = useMemo(
    () => new Map(unidadesMedida.map((u) => [u.id, u.nombre])),
    [unidadesMedida],
  );

  const columnas: ColumnDef<Articulo>[] = useMemo(
    () => [
      { accessorKey: "id_interno", header: "Código" },
      { accessorKey: "nombre", header: "Nombre" },
      { accessorKey: "tipo", header: "Tipo" },
      {
        id: "categoria",
        header: "Categoría",
        accessorFn: (a) => (a.categoria_id ? nombreCategoria.get(a.categoria_id) : "—") ?? "—",
      },
      {
        id: "unidad_medida",
        header: "UdM",
        accessorFn: (a) => nombreUdm.get(a.unidad_medida_id) ?? "—",
      },
      { accessorKey: "costo_promedio", header: "Costo promedio" },
      {
        accessorKey: "archivado",
        header: "Estado",
        cell: ({ getValue }) => (
          <span
            className={
              getValue<boolean>()
                ? "rounded-full bg-gray/20 px-2 py-0.5 text-xs font-semibold text-gray"
                : "rounded-full bg-accent/30 px-2 py-0.5 text-xs font-semibold text-dark"
            }
          >
            {getValue<boolean>() ? "Archivado" : "Activo"}
          </span>
        ),
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => (
          <DialogoEditarArticulo
            articulo={row.original}
            categorias={categorias}
            nombreUdm={nombreUdm.get(row.original.unidad_medida_id) ?? "—"}
          />
        ),
      },
    ],
    [nombreCategoria, nombreUdm, categorias],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl text-dark">Artículos</h1>
        <div className="flex items-center gap-2">
          {/* El export se baja con un `<a download>` contra el proxy, que ya
              pasa bytes y conserva el nombre del archivo (ADR-048). */}
          <a
            href={RUTA_EXPORTAR_ARTICULOS}
            download
            className="rounded border border-borde px-4 py-2 text-sm font-bold text-dark hover:bg-fondo"
          >
            Exportar
          </a>
          <ImportarArticulos onImportados={() => router.refresh()} />
          <DialogoNuevoArticulo categorias={categorias} unidadesMedida={unidadesMedida} />
        </div>
      </div>
      <TablaDatos columnas={columnas} datos={articulos} placeholderBusqueda="Buscar artículo..." />
    </div>
  );
}
