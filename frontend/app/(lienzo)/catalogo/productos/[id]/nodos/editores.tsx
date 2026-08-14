"use client";

import { useState } from "react";

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  catalogoApi,
  type Producto,
  type ProductoDetalle,
  type Receta,
  type UnidadMedida,
} from "@/lib/catalogo";
import { aTitulo } from "@/lib/texto";

/**
 * Las ediciones de estructura del lienzo, cada una detrás de un nodo
 * fantasma que abre un popover.
 *
 * Los mismos campos y las mismas llamadas de antes: lo que cambia es que
 * dejan de ser un `<select>` y un formulario inline —la fuente más ruidosa
 * del "parece HTML"— y pasan a colgar del nodo donde uno esperaría agregarlos.
 *
 * Lo que NO se edita acá son las cantidades de cada receta: eso sigue en
 * Catálogo → Recetas, con enlace desde cada nodo (ADR-023 §4).
 *
 * `lienzo-tema` en el contenido: Base UI portaliza el popover a
 * `document.body`, fuera de `.lienzo`, así que sin esa clase heredaría el
 * tema claro del ERP y saldría un rectángulo blanco sobre el lienzo oscuro.
 */

type Correr = (accion: () => Promise<unknown>) => Promise<void>;

function Fantasma({
  etiqueta,
  titulo,
  children,
}: {
  etiqueta: string;
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <Popover>
      <PopoverTrigger
        render={
          <button type="button" className="lienzo-agregar" title={titulo}>
            {etiqueta}
          </button>
        }
      />
      <PopoverContent className="lienzo-tema">
        <div className="lienzo-editor">{children}</div>
      </PopoverContent>
    </Popover>
  );
}

export function NuevoTamano({
  padre,
  recetas,
  unidades,
  onCorrer,
}: {
  padre: ProductoDetalle;
  recetas: Receta[];
  unidades: UnidadMedida[];
  onCorrer: Correr;
}) {
  const [nombre, setNombre] = useState("");
  const [idInterno, setIdInterno] = useState("");
  const [recetaId, setRecetaId] = useState("");

  if (padre.receta_id) {
    return (
      <span className="lienzo-nota" title="Quítale la receta en la ficha">
        Receta propia: no admite tamaños
      </span>
    );
  }

  return (
    <Fantasma etiqueta="+ tamaño" titulo="Agregar una presentación">
      <label>
        Tarjeta en el PDV
        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          onBlur={() => setNombre((n) => aTitulo(n))}
          placeholder="Familiar"
        />
      </label>
      <label>
        Código
        <input
          value={idInterno}
          onChange={(e) => setIdInterno(e.target.value.slice(0, 4))}
          placeholder="PZPF"
        />
      </label>
      <label>
        Receta
        <select value={recetaId} onChange={(e) => setRecetaId(e.target.value)}>
          <option value="">Crear una vacía con este nombre</option>
          {recetas.map((r) => (
            <option key={r.id} value={r.id}>
              {r.nombre}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        className="lienzo-boton"
        disabled={!nombre.trim() || !idInterno}
        onClick={() =>
          onCorrer(async () => {
            // Sin receta elegida se crea una vacía: la variante no puede
            // existir sin receta, y mandar al usuario a otro módulo antes de
            // poder crear el nodo era peor que crearla en blanco.
            const receta =
              recetaId ||
              (
                await catalogoApi.crearReceta({
                  nombre: `${padre.nombre} ${nombre}`.trim(),
                  rendimiento_cantidad: "1",
                  rendimiento_unidad_medida_id: unidades[0]?.id ?? "",
                })
              ).id;
            await catalogoApi.crearProducto({
              id_interno: idInterno.trim().toUpperCase(),
              marca_id: padre.marca_id,
              nombre: `${padre.nombre} ${nombre}`.trim(),
              receta_id: receta,
              producto_padre_id: padre.id,
            });
            setNombre("");
            setIdInterno("");
            setRecetaId("");
          })
        }
      >
        Crear tamaño
      </button>
    </Fantasma>
  );
}

export function NuevoGrupo({
  productoId,
  onCorrer,
}: {
  productoId: string;
  onCorrer: Correr;
}) {
  const [nombre, setNombre] = useState("");
  const [obligatorio, setObligatorio] = useState(true);
  const [unaSola, setUnaSola] = useState(true);

  return (
    <Fantasma etiqueta="+ grupo" titulo="Agregar un grupo de opciones">
      <label>
        Nombre del grupo
        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          onBlur={() => setNombre((n) => aTitulo(n))}
          placeholder="Sabor"
        />
      </label>
      <label className="fila">
        <input
          type="checkbox"
          checked={obligatorio}
          onChange={(e) => setObligatorio(e.target.checked)}
        />
        Obligatorio
      </label>
      <label className="fila">
        <input
          type="checkbox"
          checked={unaSola}
          onChange={(e) => setUnaSola(e.target.checked)}
        />
        Una sola opción
      </label>
      <button
        type="button"
        className="lienzo-boton"
        disabled={!nombre.trim()}
        onClick={() => {
          // Un grupo de sabores ES esto: obligatorio (mínimo 1) y de una sola
          // opción (máximo 1). Por eso no hace falta un tipo de grupo aparte
          // en la base (ADR-035 §5).
          onCorrer(() =>
            catalogoApi.crearGrupo(productoId, {
              nombre,
              minimo: obligatorio ? 1 : 0,
              maximo: unaSola ? 1 : null,
            }),
          );
          setNombre("");
        }}
      >
        Crear grupo
      </button>
    </Fantasma>
  );
}

export function AgregarOpcion({
  producto,
  grupoId,
  disponibles,
  unidades,
  onCorrer,
}: {
  producto: ProductoDetalle;
  grupoId: string | null;
  disponibles: Producto[];
  unidades: UnidadMedida[];
  onCorrer: Correr;
}) {
  const [filtro, setFiltro] = useState("");
  const [idInterno, setIdInterno] = useState("");

  const visibles = disponibles.filter((p) =>
    p.nombre.toLowerCase().includes(filtro.toLowerCase()),
  );
  const nombre = aTitulo(filtro.trim());

  return (
    <Fantasma etiqueta="+ opción" titulo="Colgar un extra de este producto">
      <label>
        Buscar o nombrar uno nuevo
        <input
          value={filtro}
          onChange={(e) => setFiltro(e.target.value)}
          placeholder="Peperoni"
        />
      </label>
      {visibles.slice(0, 8).map((p) => (
        <button
          key={p.id}
          type="button"
          className="lienzo-boton"
          onClick={() =>
            onCorrer(() =>
              catalogoApi.vincularExtra(producto.id, {
                extra_id: p.id,
                grupo_id: grupoId,
              }),
            )
          }
        >
          {p.nombre}
        </button>
      ))}
      {visibles.length === 0 && filtro.trim() === "" && (
        <p className="lienzo-nota">No queda ningún extra libre por colgar.</p>
      )}

      {/* Un sabor que todavía no existe se crea acá y no en otro módulo: el
          lienzo es el lugar de trabajo del catálogo, y mandar a crear el
          producto y su receta en dos pantallas antes de poder cablearlo es
          justo lo que hacía sentir que las recetas no eran componibles. */}
      {nombre && (
        <>
          <p className="lienzo-nota">
            {visibles.length > 0 ? "…o crear uno nuevo:" : "Ninguno con ese nombre."}
          </p>
          <label>
            Código
            <input
              value={idInterno}
              onChange={(e) => setIdInterno(e.target.value.slice(0, 4))}
              placeholder="SPEP"
            />
          </label>
          <button
            type="button"
            className="lienzo-boton"
            disabled={!idInterno.trim()}
            onClick={() =>
              onCorrer(async () => {
                // Receta vacía con el nombre de la opción, igual que
                // "+ tamaño": la opción no puede existir sin receta y sus
                // cantidades se cargan después, en el inspector del nodo.
                const receta = await catalogoApi.crearReceta({
                  nombre: `${nombre} ${producto.nombre}`.trim(),
                  rendimiento_cantidad: "1",
                  rendimiento_unidad_medida_id: unidades[0]?.id ?? "",
                });
                const extra = await catalogoApi.crearProducto({
                  id_interno: idInterno.trim().toUpperCase(),
                  marca_id: producto.marca_id,
                  nombre,
                  receta_id: receta.id,
                  es_extra: true,
                });
                await catalogoApi.vincularExtra(producto.id, {
                  extra_id: extra.id,
                  grupo_id: grupoId,
                });
                setFiltro("");
                setIdInterno("");
              })
            }
          >
            Crear “{nombre}” y colgarlo
          </button>
        </>
      )}
    </Fantasma>
  );
}

const MODALIDADES = ["mesa", "takeout", "delivery"];

export function EditorEmpaque({
  nodo,
  empaques,
  onCorrer,
}: {
  nodo: ProductoDetalle;
  empaques: { id: string; nombre: string }[];
  onCorrer: Correr;
}) {
  const marcadas = nodo.modalidades_empaque ?? [];
  const guardar = (cuerpo: {
    empaque_id: string | null;
    modalidades_empaque: string[] | null;
  }) => onCorrer(() => catalogoApi.editarProducto(nodo.id, cuerpo));

  return (
    <Fantasma
      etiqueta="empaque"
      titulo="Qué empaque consume y en qué modalidades (RN-EMP-003)"
    >
      <label>
        Artículo
        <select
          value={nodo.empaque_id ?? ""}
          onChange={(e) =>
            guardar({
              empaque_id: e.target.value || null,
              modalidades_empaque: e.target.value ? marcadas : null,
            })
          }
        >
          <option value="">Sin empaque</option>
          {empaques.map((a) => (
            <option key={a.id} value={a.id}>
              {a.nombre}
            </option>
          ))}
        </select>
      </label>
      {nodo.empaque_id &&
        MODALIDADES.map((m) => (
          <label key={m} className="fila">
            <input
              type="checkbox"
              checked={marcadas.includes(m)}
              onChange={(e) =>
                guardar({
                  empaque_id: nodo.empaque_id,
                  modalidades_empaque: e.target.checked
                    ? [...marcadas, m]
                    : marcadas.filter((x) => x !== m),
                })
              }
            />
            {m}
          </label>
        ))}
    </Fantasma>
  );
}

