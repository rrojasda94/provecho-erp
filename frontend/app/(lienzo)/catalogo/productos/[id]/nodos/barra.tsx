"use client";

import Link from "next/link";

import {
  type Articulo,
  type Producto,
  type ProductoDetalle,
  type Receta,
  type UnidadMedida,
} from "@/lib/catalogo";
import { sinVincular } from "@/lib/lienzo";

import {
  AgregarOpcion,
  EditorEmpaque,
  NuevoGrupo,
  NuevoTamano,
} from "./editores";

/**
 * Barra del lienzo: por dónde se sale y qué se puede agregar.
 *
 * La pantalla vive fuera del shell del módulo (necesita los 100dvh), así que
 * los enlaces de vuelta —a la ficha y al inicio— tienen que estar acá: sin
 * ellos el lienzo sería una calle sin salida, que es un costo que el PDV y el
 * KDS aceptan por ser pantallas de operación y una de catálogo no debería.
 *
 * Los "+ algo" son nodos fantasma agrupados acá y no colgando de cada
 * columna: un fantasma por columna llenaba el lienzo de cajas punteadas que
 * competían con los nodos reales.
 */
export function Barra({
  padre,
  activo,
  recetas,
  unidades,
  extrasDisponibles,
  empaques,
  error,
  onCorrer,
}: {
  padre: ProductoDetalle;
  activo: ProductoDetalle;
  recetas: Receta[];
  unidades: UnidadMedida[];
  extrasDisponibles: Producto[];
  empaques: Articulo[];
  error: string;
  onCorrer: (accion: () => Promise<unknown>) => Promise<void>;
}) {
  const libres = sinVincular(extrasDisponibles, activo);
  // Colgar una opción de un grupo obligatorio es agregar un sabor; el primero
  // es el caso frecuente y merece el atajo de la barra.
  const combinacion = activo.grupos.find((g) => g.minimo >= 1) ?? null;

  return (
    <header className="lienzo-top">
      <Link href="/catalogo/productos" className="lienzo-enlace">
        ← Productos
      </Link>
      <span className="lienzo-sep">/</span>
      <Link
        href={`/catalogo/productos/${padre.id}`}
        className="lienzo-enlace"
      >
        Ficha
      </Link>
      <h1>{padre.nombre}</h1>

      <NuevoTamano
        padre={padre}
        recetas={recetas}
        unidades={unidades}
        onCorrer={onCorrer}
      />
      <NuevoGrupo productoId={activo.id} onCorrer={onCorrer} />
      <AgregarOpcion
        productoId={activo.id}
        grupoId={combinacion?.id ?? null}
        disponibles={libres}
        onCorrer={onCorrer}
      />
      <EditorEmpaque nodo={activo} empaques={empaques} onCorrer={onCorrer} />

      {error ? (
        <p role="alert" className="lienzo-error">
          {error}
        </p>
      ) : (
        <p className="lienzo-ayuda">
          Toca los nodos para armar un plato · las cantidades se editan en{" "}
          <Link href="/catalogo/recetas" className="lienzo-enlace">
            Recetas
          </Link>
        </p>
      )}
    </header>
  );
}
