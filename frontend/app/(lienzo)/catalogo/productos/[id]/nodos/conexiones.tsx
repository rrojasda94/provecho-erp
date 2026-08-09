"use client";

import { catalogoApi } from "@/lib/catalogo";

/**
 * Qué significa cablear dos nodos.
 *
 * En el lienzo se conecta y se desconecta de verdad, pero **no cualquier
 * cosa con cualquier cosa**: la topología entre tamaño, sabor y plato la
 * dicta RN-PRD-004 y no se negocia con el mouse. Lo único que el usuario
 * decide cableando es **qué extra ofrece este producto y dentro de qué
 * grupo**, que es exactamente `producto_comercial_extra` — la única relación
 * del modelo que es una elección de catálogo y no una regla.
 *
 * De ahí las dos conexiones admitidas:
 *
 *     grupo:<id>   → disponible:<extraId>   vincular DENTRO de ese grupo
 *     tamano:<id>  → disponible:<extraId>   vincular suelto (siempre opcional)
 *
 * Y la desconexión: cortar la arista que sostiene una opción la desvincula.
 * El extra no se borra — es un producto comercial con su receta y su precio,
 * y lo siguen ofreciendo otros platos.
 *
 * Cualquier otro par se rechaza con un mensaje que dice qué sí se puede, en
 * vez de no hacer nada: un cable que no engancha y no explica por qué es
 * peor que uno que no se deja tirar.
 */

/** `"opcion:g1:e9"` → `["opcion", "g1", "e9"]`. */
function partes(id: string): string[] {
  return id.split(":");
}

export async function conectar(
  productoId: string,
  desde: string,
  hasta: string,
): Promise<unknown> {
  const [tipoDesde, refDesde] = partes(desde);
  const [tipoHasta, extraId] = partes(hasta);

  if (tipoHasta !== "disponible") {
    throw new ErrorDeCableado(
      "Solo se puede conectar hacia un extra disponible: el resto del árbol " +
        "lo define el orden tamaño → sabor → extras → restas.",
    );
  }
  if (tipoDesde === "grupo") {
    return catalogoApi.vincularExtra(productoId, {
      extra_id: extraId,
      grupo_id: refDesde,
    });
  }
  if (tipoDesde === "tamano") {
    return catalogoApi.vincularExtra(productoId, { extra_id: extraId });
  }
  throw new ErrorDeCableado(
    "Arrastra desde un grupo (para colgarlo ahí dentro) o desde el tamaño " +
      "(para dejarlo como extra suelto).",
  );
}

export async function desconectar(
  productoId: string,
  desde: string,
  hasta: string,
): Promise<unknown> {
  const [tipoHasta, , extraId] = partes(hasta);
  if (tipoHasta !== "opcion") {
    throw new ErrorDeCableado(
      "Esa conexión la define el orden de los modificadores (RN-PRD-004) y " +
        "no se corta a mano. Se pueden desconectar las opciones de un grupo.",
    );
  }
  void desde;
  return catalogoApi.desvincularExtra(productoId, extraId);
}

/** Error de usuario, no de red: lo muestra la barra como cualquier otro. */
export class ErrorDeCableado extends Error {}
