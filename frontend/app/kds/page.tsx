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
 *
 * La sucursal va por el mismo camino (`?sucursal=<id>`). Antes era siempre
 * `usuario.sucursales[0]`: un jefe de cocina con dos locales veía uno solo y
 * no tenía forma de llegar al otro. Lo que llega por la URL **se valida
 * contra sus sucursales** — la URL la escribe cualquiera.
 */

import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import {
  SEMAFORO_DE_FABRICA,
  type Categoria,
  type Pantalla,
  type Semaforo,
  type SucursalKds,
} from "@/lib/kds";
import { tieneAccesoModulo, tienePermiso } from "@/lib/permisos";
import { obtenerSesion } from "@/lib/sesion";

import DespachoCliente from "./despacho-cliente";
import EstacionesCliente from "./estaciones-cliente";
import HistorialCliente from "./historial-cliente";
import KdsCliente from "./kds-cliente";
import "./kds.css";

/**
 * La sucursal de la URL solo si de verdad es suya; si no, la primera. El gate
 * real lo hace la API (`tenant.exigir_sucursal`); esto evita pedirle una
 * cocina ajena y comerse un 403 dibujado como "no se pudo cargar".
 */
function sucursalElegida(pedida: string | undefined, propias: string[]): string | undefined {
  return pedida && propias.includes(pedida) ? pedida : propias[0];
}

/**
 * Las suyas, y solo si tiene más de una: el selector no tiene sentido para
 * quien trabaja en un local. Si el catálogo falla, la cocina abre igual con
 * la sucursal actual — mismo criterio que con las categorías.
 */
async function sucursalesDelUsuario(token: string, propias: string[]): Promise<SucursalKds[]> {
  if (propias.length <= 1) return [];
  return apiFetch<SucursalKds[]>("/api/v1/sucursales", { token })
    .then((todas) => todas.filter((s) => propias.includes(s.id)))
    .catch(() => []);
}

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
  searchParams: Promise<{ pantalla?: string; sucursal?: string; vista?: string }>;
}) {
  const { token, usuario } = await obtenerSesion();
  const parametros = await searchParams;

  if (!tieneAccesoModulo(usuario.permisos, "kds.")) {
    return (
      <Bloqueo
        titulo="Sin permiso"
        detalle="Tu usuario no tiene acceso a las pantallas de cocina. Pídele a un administrador el permiso `kds.operar`."
      />
    );
  }

  const sucursalId = sucursalElegida(parametros.sucursal, usuario.sucursales);
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

  const elegida = parametros.pantalla;
  const pantalla = pantallas.find((p) => p.id === elegida && p.activo);

  if (pantalla) {
    // La entrega es acto de despacho, con permiso propio (RN-CUP-006): el
    // cocinero no ve el botón deshabilitado, no lo ve. Lo mismo para
    // deshacerla, que usa el mismo permiso.
    const puedeEntregar = tienePermiso(usuario.permisos, "sales.entregar_pedido");
    const comun = { id: pantalla.id, nombre: pantalla.nombre };
    const semaforo = await apiFetch<Semaforo>(
      `/api/v1/kds/configuracion?sucursal_id=${sucursalId}`,
      { token },
    ).catch(() => SEMAFORO_DE_FABRICA);
    if (parametros.vista === "historial") {
      return (
        <HistorialCliente
          pantalla={comun}
          sucursalId={sucursalId}
          puedeEntregar={puedeEntregar}
        />
      );
    }
    // Despacho y preparación miran la misma cola pero no hacen lo mismo:
    // una cocina y tacha línea por línea, la otra arma el pedido completo y
    // lo entrega (ADR-044). Por eso son dos componentes y no un filtro.
    return pantalla.tipo === "despacho" ? (
      <DespachoCliente
        pantalla={comun}
        sucursalId={sucursalId}
        puedeEntregar={puedeEntregar}
        semaforo={semaforo}
      />
    ) : (
      <KdsCliente
        pantalla={{ ...comun, orden: pantalla.orden }}
        sucursalId={sucursalId}
        semaforo={semaforo}
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

  const sucursales = await sucursalesDelUsuario(token, usuario.sucursales);

  return (
    <EstacionesCliente
      sucursalId={sucursalId}
      sucursales={sucursales}
      inicial={pantallas}
      categorias={categorias}
      puedeConfigurar={puedeConfigurar}
    />
  );
}
