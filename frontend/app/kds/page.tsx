/**
 * Pantalla de cocina (KDS). Pantalla completa fuera del shell, igual que el
 * PDV (ADR-013): se opera de pie, en tablet, con las manos ocupadas.
 *
 * El servidor resuelve sesión, sucursal y qué pantallas existen; la cola y
 * el avance viven en el cliente, que refresca por polling — una pantalla de
 * cocina que dependiera de un round-trip de renderizado por toque no sirve.
 *
 * La pantalla elegida va en la URL (`?pantalla=<id>`) y no en el servidor:
 * cada tablet de la cocina se queda con su enlace en favoritos y sobrevive
 * a un reinicio sin que nadie vuelva a elegir estación.
 */

import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import type { Categoria, Pantalla } from "@/lib/kds";
import { tieneAccesoModulo, tienePermiso } from "@/lib/permisos";
import { obtenerSesion } from "@/lib/sesion";

import EstacionesCliente from "./estaciones-cliente";
import KdsCliente from "./kds-cliente";
import "./kds.css";

/** Cada bloqueo dice a quién pedirle qué: en cocina nadie va a leer un 500. */
function Bloqueo({ titulo, detalle }: { titulo: string; detalle: string }) {
  return (
    <main className="kds-vacio">
      <h1>{titulo}</h1>
      <p>{detalle}</p>
    </main>
  );
}

export default async function PaginaKds({
  searchParams,
}: {
  searchParams: Promise<{ pantalla?: string }>;
}) {
  const { token, usuario } = await obtenerSesion();

  if (!tieneAccesoModulo(usuario.permisos, "kds.")) {
    return (
      <Bloqueo
        titulo="Sin permiso"
        detalle="Tu usuario no tiene acceso a las pantallas de cocina. Pídele a un administrador el permiso `kds.operar`."
      />
    );
  }

  const sucursalId = usuario.sucursales[0];
  if (!sucursalId) {
    return (
      <Bloqueo
        titulo="Sin sucursal asignada"
        detalle="Tu usuario no tiene ninguna sucursal asignada, así que no hay cocina que mostrar. Pídele a un administrador que te asigne una."
      />
    );
  }

  let pantallas: Pantalla[];
  try {
    pantallas = await apiFetch<Pantalla[]>(
      `/api/v1/kds/pantallas?sucursal_id=${sucursalId}`,
      { token },
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) redirect("/login");
    return (
      <Bloqueo
        titulo="No se pudo cargar la cocina"
        detalle="Revisa la conexión con la API e intenta de nuevo."
      />
    );
  }

  const elegida = (await searchParams).pantalla;
  const pantalla = pantallas.find((p) => p.id === elegida && p.activo);

  if (pantalla) {
    return (
      <KdsCliente
        pantalla={{ id: pantalla.id, nombre: pantalla.nombre, tipo: pantalla.tipo }}
        // La entrega es acto de despacho, con permiso propio (RN-CUP-006):
        // el cocinero no ve el botón deshabilitado, no lo ve.
        puedeEntregar={tienePermiso(usuario.permisos, "sales.entregar_pedido")}
      />
    );
  }

  // Sin estación elegida se muestra el tablero de estaciones, que también es
  // donde se crean: sin él, una sucursal nueva no tendría forma de configurar
  // su primera pantalla salvo por API.
  const puedeConfigurar = tienePermiso(usuario.permisos, "kds.configurar");
  let categorias: Categoria[] = [];
  if (puedeConfigurar) {
    // El catálogo lo sirve `inventory` y exige `inventory.leer`: un
    // supervisor de cocina podría no tenerlo. Sin categorías se puede crear
    // igual una pantalla sin filtro, así que el fallo no bloquea.
    categorias = await apiFetch<Categoria[]>("/api/v1/inventory/categorias", {
      token,
    }).catch(() => []);
  }

  return (
    <EstacionesCliente
      sucursalId={sucursalId}
      inicial={pantallas}
      categorias={categorias}
      puedeConfigurar={puedeConfigurar}
    />
  );
}
