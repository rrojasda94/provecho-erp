import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import type {
  ArbolProducto,
  Articulo,
  Producto,
  Receta,
  UnidadMedida,
} from "@/lib/catalogo";
import { MODULOS } from "@/lib/modulos";
import { puedeVerModulo } from "@/lib/permisos";
import { obtenerSesion } from "@/lib/sesion";

import { LienzoNodos } from "./nodos-cliente";
import "./lienzo.css";

/**
 * El lienzo vive **fuera** del shell del módulo, como el PDV y el KDS: un
 * grafo necesita los 100dvh y una superficie oscura, y un rectángulo negro
 * encajonado en la columna crema del ERP se lee como un error de render.
 *
 * El costo de salir del shell es que se pierde el guard de `ModuloShell`, así
 * que la pantalla lo hace ella. `puedeVerModulo()` y no un string a mano: es
 * el único lugar que resuelve prefijo-vs-permiso-exacto (enmienda de ADR-013,
 * 2026-08-03), y duplicar la comprobación es cómo un módulo termina visible
 * en una pantalla y bloqueado en otra.
 */
const CATALOGO = MODULOS.find((m) => m.clave === "catalogo")!;

function Bloqueo({ titulo, detalle }: { titulo: string; detalle: string }) {
  return (
    <main className="lienzo-vacio">
      <h1>{titulo}</h1>
      <p>{detalle}</p>
    </main>
  );
}

export default async function NodosPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { token, usuario } = await obtenerSesion();

  if (!puedeVerModulo(usuario.permisos, CATALOGO)) {
    return (
      <Bloqueo
        titulo="Sin permiso"
        detalle="Tu usuario no tiene acceso al catálogo. Pídele a un administrador el permiso `sales.gestionar_catalogo`."
      />
    );
  }

  try {
    // Una sola llamada por el árbol (ADR-058). Antes eran la ficha del padre
    // **más una por cada variante**: con tres tamaños y ocho sabores, 27 idas
    // a la red para dibujar un árbol. Cada tamaño sigue trayendo SUS grupos
    // —"Peperoni" en Personal y en Familiar son dos opciones distintas con
    // dos recetas distintas—, solo que ahora vienen juntas.
    const [arbol, recetas, unidades, productos, articulos] = await Promise.all([
      apiFetch<ArbolProducto>(`/api/v1/sales/productos/${id}/arbol`, { token }),
      apiFetch<Receta[]>("/api/v1/inventory/recetas", { token }),
      apiFetch<UnidadMedida[]>("/api/v1/inventory/unidades-medida", { token }),
      apiFetch<Producto[]>("/api/v1/sales/productos", { token }),
      apiFetch<Pagina<Articulo>>("/api/v1/inventory/articulos", { token }),
    ]);

    return (
      <LienzoNodos
        inicial={arbol}
        variantesIniciales={arbol.variantes_detalle}
        atributos={arbol.atributos}
        exclusiones={arbol.exclusiones}
        recetas={recetas}
        unidades={unidades}
        extrasDisponibles={productos.filter((p) => p.es_extra)}
        empaques={articulos.items.filter((a) => !a.archivado)}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver este producto."
        : "No se pudo cargar el producto. Revisa la conexión con la API.";
    return <Bloqueo titulo="No se pudo abrir el lienzo" detalle={mensaje} />;
  }
}
