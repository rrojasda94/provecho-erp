/**
 * Tablero de despacho (ADR-098): qué pedido delivery está listo sin
 * asignar, y qué rutas siguen vivas — con su última posición y el estado
 * de cada parada. Vive en el shell (ADR-013 lo reserva para lo que se
 * opera de pie y con las manos ocupadas; despachar es trabajo de
 * escritorio) y sondea, como el resto de pantallas operativas.
 */

import { ApiError, apiFetch } from "@/lib/api";
import { type Repartidor, type Tablero } from "@/lib/delivery";
import { tienePermiso } from "@/lib/permisos";
import { obtenerSesion } from "@/lib/sesion";

import TableroCliente from "./tablero-cliente";

type SucursalOpcion = { id: string; nombre: string };

/** La sucursal de la URL solo si de verdad es suya; si no, la primera —
 * mismo criterio que `app/kds/page.tsx`. */
function sucursalElegida(pedida: string | undefined, propias: string[]): string | undefined {
  return pedida && propias.includes(pedida) ? pedida : propias[0];
}

async function sucursalesDelUsuario(
  token: string,
  propias: string[],
): Promise<SucursalOpcion[]> {
  if (propias.length <= 1) return [];
  return apiFetch<SucursalOpcion[]>("/api/v1/sucursales", { token })
    .then((todas) => todas.filter((s) => propias.includes(s.id)))
    .catch(() => []);
}

export default async function DeliveryPage({
  searchParams,
}: {
  searchParams: Promise<{ sucursal?: string }>;
}) {
  const { token, usuario } = await obtenerSesion();
  const parametros = await searchParams;
  const sucursalId = sucursalElegida(parametros.sucursal, usuario.sucursales);

  if (!sucursalId) {
    return (
      <p className="text-secondary">
        Tu usuario no tiene ninguna sucursal asignada, así que no hay tablero que mostrar.
      </p>
    );
  }

  let tablero: Tablero;
  try {
    tablero = await apiFetch<Tablero>(`/api/v1/delivery/tablero?sucursal_id=${sucursalId}`, {
      token,
    });
  } catch (e) {
    // El tablero exige `delivery.despachar` (más estricto que la ficha del
    // módulo, `delivery.leer`): quien solo lee todavía tiene Repartidores
    // e Historial, así que un 403 acá no es un callejón sin salida. Un
    // 401 (la sesión venció justo entre esta llamada y `obtenerSesion()`)
    // cae en el mensaje genérico de abajo: recargar la página lo manda a
    // `/login`, que es lo que `obtenerSesion()` ya hace por su cuenta.
    if (e instanceof ApiError && e.status === 403) {
      return (
        <p className="text-secondary">
          Tu usuario puede ver Repartidores e Historial, pero no el tablero de despacho — pídele
          a un administrador el permiso <code>delivery.despachar</code>.
        </p>
      );
    }
    return <p className="text-secondary">No se pudo cargar el tablero de despacho.</p>;
  }

  const sucursales = await sucursalesDelUsuario(token, usuario.sucursales);
  const puedeDespachar = tienePermiso(usuario.permisos, "delivery.despachar");

  // Solo para armar el selector de "Nueva ruta": si de verdad no tiene
  // `delivery.despachar` no llegó hasta acá (el 403 de arriba lo detiene
  // antes), así que este fetch no necesita su propio try/catch de permiso.
  let repartidores: Repartidor[] = [];
  if (puedeDespachar) {
    repartidores = await apiFetch<Repartidor[]>(
      `/api/v1/delivery/repartidores?sucursal_id=${sucursalId}&activo=true`,
      { token },
    ).catch(() => []);
  }

  return (
    <TableroCliente
      inicial={tablero}
      sucursalId={sucursalId}
      sucursales={sucursales}
      puedeDespachar={puedeDespachar}
      repartidores={repartidores}
    />
  );
}
