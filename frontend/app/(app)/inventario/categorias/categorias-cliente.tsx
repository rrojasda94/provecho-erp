"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import { BOTON_FILA, DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { Combobox } from "@/components/ui/combobox";
import { primeroElDe } from "@/lib/destinos";
import { ROLES_CONTABLES } from "@/lib/roles-contables";

import { crearCategoriaAction, editarCategoriaAction } from "../actions";

export type Categoria = {
  id: string;
  nombre: string;
  frecuencia_conteo: string | null;
  padre_id: string | null;
  /** Rol contable → código del PCGE (ADR-086). `null` = no configura nada y
   * hereda todo de su madre. */
  asiento_contable_config: Record<string, string> | null;
};

export type Cuenta = {
  id: string;
  codigo: string;
  nombre: string;
  cuenta_padre_id: string | null;
  activa: boolean;
};


export type ProgramaConteo = {
  almacen_id: string;
  categoria_id: string;
  categoria: string;
  frecuencia: string;
  ultimo_conteo: string | null;
  proxima_fecha: string;
  estado: string;
  dias_atraso: number;
};

type Fila = Categoria & { estado: string; proxima: string; atraso: number };

// Las seis de `rules.FRECUENCIAS_CONTEO`. Vacío = fuera del conteo cíclico.
const FRECUENCIAS = [
  "diario",
  "semanal",
  "quincenal",
  "mensual",
  "semestral",
  "anual",
] as const;

function SelectorFrecuencia({ valor }: { valor?: string | null }) {
  return (
    <label className="flex flex-col gap-1 text-sm font-semibold">
      Frecuencia de conteo
      <select name="frecuencia_conteo" defaultValue={valor ?? ""}>
        <option value="">Sin conteo cíclico</option>
        {FRECUENCIAS.map((f) => (
          <option key={f} value={f}>
            {f}
          </option>
        ))}
      </select>
      <span className="text-xs font-normal text-gray">
        Cada cuánto toca contar esta categoría (RN-INV-007). No hay un número universal:
        el queso no se cuenta con la misma frecuencia que las servilletas.
      </span>
    </label>
  );
}

/** Qué cuenta usa realmente una categoría para un rol, mirando hacia arriba.
 * Es la misma regla que `inventory.queries_publicas.config_contable_de_categorias`
 * resuelve al asentar, escrita acá para **mostrarla**: sin ver de dónde
 * hereda, el árbol no se entiende. */
function heredado(
  categoria: Categoria,
  rol: string,
  porId: Map<string, Categoria>,
): { codigo: string; de: string } | null {
  let actual = categoria.padre_id ? porId.get(categoria.padre_id) : undefined;
  // Tope de profundidad: `_validar_madre` impide el ciclo al guardar, pero
  // una fila tocada a mano no puede colgar el navegador.
  for (let salto = 0; salto < 6 && actual; salto += 1) {
    const codigo = actual.asiento_contable_config?.[rol];
    if (codigo) return { codigo, de: actual.nombre };
    actual = actual.padre_id ? porId.get(actual.padre_id) : undefined;
  }
  return null;
}

function CuentasContables({
  categoria,
  categorias,
  cuentas,
  aviso,
}: {
  categoria?: Categoria;
  categorias: Categoria[];
  cuentas: Cuenta[];
  aviso: string | null;
}) {
  const porId = new Map(categorias.map((c) => [c.id, c]));
  // Solo las de último nivel: ofrecer un rubro solo sirve para que el
  // guardado responda que agrupa a otras.
  const hojas = cuentas.filter(
    (c) => c.activa && !cuentas.some((otra) => otra.cuenta_padre_id === c.id),
  );

  return (
    <fieldset className="flex flex-col gap-2 rounded border border-gray/20 p-3">
      <legend className="px-1 text-sm font-semibold">Cuentas contables</legend>
      <p className="text-xs text-gray">
        Con qué cuenta del PCGE se asienta lo que agrupa esta categoría. Lo que
        dejes en blanco lo hereda de su categoría madre, y si nadie lo
        configura usa la cuenta de fábrica. Sin esto, toda venta acredita 7011
        y toda compra debita 6011.
      </p>
      {aviso && <p className="text-xs text-secondary">{aviso}</p>}
      {ROLES_CONTABLES.map(({ rol, etiqueta, ayuda }) => {
        const propio = categoria?.asiento_contable_config?.[rol] ?? "";
        const deLaMadre = categoria ? heredado(categoria, rol, porId) : null;
        const marcador = deLaMadre
          ? `Hereda de ${deLaMadre.de}: ${deLaMadre.codigo}`
          : `De fábrica: ${ayuda.split(" ·")[0]}`;
        return (
          <label key={rol} className="flex flex-col gap-1 text-xs font-semibold">
            {etiqueta}
            {hojas.length > 0 ? (
              // Con búsqueda: el PCGE sembrado son ~400 cuentas y un `<select>`
              // nativo obliga a recorrerlas con la rueda.
              <Combobox
                name={`cuenta_${rol}`}
                etiqueta={etiqueta}
                marcador={marcador}
                defaultValue={propio || undefined}
                opciones={hojas.map((c) => ({
                  valor: c.codigo,
                  etiqueta: c.nombre,
                  pista: c.codigo,
                }))}
              />
            ) : (
              // Sin plan de cuentas a la vista —el usuario no tiene
              // `accounting.leer`— se teclea el código y el servidor lo valida.
              <input
                name={`cuenta_${rol}`}
                defaultValue={propio}
                inputMode="numeric"
                maxLength={20}
                placeholder={marcador}
              />
            )}
            <span className="font-normal text-gray">{ayuda}</span>
          </label>
        );
      })}
    </fieldset>
  );
}

function SelectorMadre({
  categorias,
  categoria,
}: {
  categorias: Categoria[];
  categoria?: Categoria;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm font-semibold">
      Categoría madre
      <Combobox
        name="padre_id"
        etiqueta="Categoría madre"
        marcador="Ninguna (categoría raíz)"
        defaultValue={categoria?.padre_id ?? undefined}
        opciones={categorias
          .filter((c) => c.id !== categoria?.id)
          .map((c) => ({ valor: c.id, etiqueta: c.nombre }))}
      />
      <span className="text-xs font-normal text-gray">
        De quién hereda sus cuentas contables. «Gaseosas» debajo de «Bebidas»
        no necesita configurar nada propio.
      </span>
    </label>
  );
}

function DialogoNuevaCategoria({
  categorias,
  cuentas,
  avisoCuentas,
}: {
  categorias: Categoria[];
  cuentas: Cuenta[];
  avisoCuentas: string | null;
}) {
  return (
    <DialogoFormulario
      titulo="Nueva categoría"
      disparador="+ Nueva categoría"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearCategoriaAction}
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input name="nombre" required maxLength={100} placeholder="Lácteos" />
      </label>
      <SelectorMadre categorias={categorias} />
      <SelectorFrecuencia />
      <CuentasContables
        categorias={categorias}
        cuentas={cuentas}
        aviso={avisoCuentas}
      />
    </DialogoFormulario>
  );
}

function DialogoEditarCategoria({
  categoria,
  categorias,
  cuentas,
  avisoCuentas,
}: {
  categoria: Categoria;
  categorias: Categoria[];
  cuentas: Cuenta[];
  avisoCuentas: string | null;
}) {
  return (
    <DialogoFormulario
      titulo="Editar categoría"
      disparador="Editar"
      claseDisparador={BOTON_FILA}
      accion={editarCategoriaAction}
      ayuda="Dejarla en 'sin conteo cíclico' la saca del calendario de conteos; no borra los ya hechos."
    >
      <input type="hidden" name="id" value={categoria.id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input name="nombre" required maxLength={100} defaultValue={categoria.nombre} />
      </label>
      <SelectorMadre categorias={categorias} categoria={categoria} />
      <SelectorFrecuencia valor={categoria.frecuencia_conteo} />
      <CuentasContables
        categoria={categoria}
        categorias={categorias}
        cuentas={cuentas}
        aviso={avisoCuentas}
      />
    </DialogoFormulario>
  );
}

/**
 * Además de administrarlas, esta pantalla es a donde lleva
 * `inventory.conteo_vencido` (ADR-036): el reporte dice que una categoría se
 * pasó de su fecha, y acá se ve cuánto y se corrige su frecuencia.
 */
export function CategoriasCliente({
  categorias,
  programa,
  resaltado,
  cuentas,
  avisoCuentas,
}: {
  categorias: Categoria[];
  programa: ProgramaConteo[];
  resaltado: string | null;
  cuentas: Cuenta[];
  avisoCuentas: string | null;
}) {
  const filas = useMemo<Fila[]>(() => {
    // Una categoría puede estar programada en varios almacenes: manda la más
    // atrasada, que es la que hay que ir a contar.
    const peor = new Map<string, ProgramaConteo>();
    for (const p of programa) {
      const actual = peor.get(p.categoria_id);
      if (!actual || p.dias_atraso > actual.dias_atraso) peor.set(p.categoria_id, p);
    }
    const lista = categorias.map((c) => {
      const p = peor.get(c.id);
      return {
        ...c,
        estado: p?.estado ?? "sin programa",
        proxima: p?.proxima_fecha ?? "—",
        atraso: p?.dias_atraso ?? 0,
      };
    });
    return primeroElDe(lista, resaltado, (c) => c.id);
  }, [categorias, programa, resaltado]);

  const columnas: ColumnDef<Fila>[] = useMemo(
    () => [
      { accessorKey: "nombre", header: "Categoría" },
      {
        id: "frecuencia",
        header: "Conteo cíclico",
        accessorFn: (c) => c.frecuencia_conteo ?? "—",
      },
      { accessorKey: "proxima", header: "Próximo conteo" },
      {
        accessorKey: "estado",
        header: "Estado",
        cell: ({ row }) =>
          row.original.estado === "vencido" ? (
            <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-bold text-red-900">
              Vencido · {row.original.atraso} día(s)
            </span>
          ) : (
            <span className="text-sm text-gray">{row.original.estado}</span>
          ),
      },
      {
        id: "cuentas",
        header: "Cuentas",
        // Sin esta columna, "el balance sale mal" no tiene dónde mirarse: no
        // había forma de ver qué categorías están configuradas y cuáles no.
        accessorFn: (c) => Object.keys(c.asiento_contable_config ?? {}).length,
        cell: ({ row }) => {
          const propias = Object.entries(row.original.asiento_contable_config ?? {});
          if (propias.length === 0) {
            return <span className="text-sm text-gray">Hereda / de fábrica</span>;
          }
          return (
            <span className="cifra text-xs">
              {propias.map(([rol, codigo]) => `${rol} ${codigo}`).join(" · ")}
            </span>
          );
        },
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => (
          <DialogoEditarCategoria
            categoria={row.original}
            categorias={categorias}
            cuentas={cuentas}
            avisoCuentas={avisoCuentas}
          />
        ),
      },
    ],
    [categorias, cuentas, avisoCuentas],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl italic uppercase text-dark">Categorías</h1>
        <DialogoNuevaCategoria
          categorias={categorias}
          cuentas={cuentas}
          avisoCuentas={avisoCuentas}
        />
      </div>
      <p className="text-sm text-gray">
        Agrupan artículos <strong>y productos comerciales</strong>: es el único
        punto donde lo que se compra y lo que se vende se agrupan igual, y por
        eso es donde se configura contra qué cuenta del PCGE se asienta cada
        cosa (ADR-086). Fijan además cada cuánto se cuenta cada grupo en el
        conteo cíclico (RN-INV-007).
      </p>
      <TablaDatos
        columnas={columnas}
        datos={filas}
        placeholderBusqueda="Buscar categoría..."
      />
    </div>
  );
}
