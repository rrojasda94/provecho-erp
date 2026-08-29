/**
 * Punto de venta. El servidor solo resuelve la sesión y el contexto
 * (empresa, sucursal, punto de venta); toda la interacción vive en el
 * cliente, porque el PDV se opera a golpes de dedo y no puede pagar un
 * round-trip de renderizado por cada producto que se toca.
 *
 * La sucursal sale de `/users/me` y va por la URL (`?sucursal=<id>`), igual
 * que en el KDS (ADR-073). Antes salía del JWT y era siempre
 * `claims.sucursales[0]`, con dos consecuencias que el local sufrió el mismo
 * día: quien tenía dos locales asignados operaba **siempre** contra el
 * primero —el pedido tomado en CH2 aparecía en las cuentas abiertas de CH1—
 * y una reasignación de sucursal no valía hasta volver a entrar, porque el
 * token viejo seguía diciendo la de antes.
 *
 * Lo que llega por la URL se valida contra las suyas: la URL la escribe
 * cualquiera. El gate real lo sigue haciendo la API en cada request.
 */

import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";
import { ProveedorConfigMapas } from "@/components/direccion/config-mapas";
import { configMapas } from "@/lib/mapas";

import BloqueoPorInactividad from "./bloqueo";
import PdvCliente from "./pdv-cliente";
import "./pdv.css";

type PuntoVenta = {
  id: string;
  sucursal_id: string;
  canal: string;
  serie_boleta: string;
  serie_factura: string;
  modalidades_habilitadas: string[] | null;
  politica_pago: string;
};

export type SucursalPdv = { id: string; nombre: string };

/** Cada motivo de bloqueo es un mensaje accionable, no un 500 genérico: el
 * cajero tiene que saber a quién pedirle qué. */
function Bloqueo({
  titulo,
  detalle,
  sucursales,
}: {
  titulo: string;
  detalle: string;
  sucursales?: SucursalPdv[];
}) {
  return (
    <main className="pdv-vacio">
      <h1>{titulo}</h1>
      <p>{detalle}</p>
      {sucursales && sucursales.length > 0 && (
        // Salida del callejón: si tiene otro local asignado, que pueda ir
        // sin llamar a nadie. Antes el mensaje era terminal aunque la caja
        // que buscaba estuviera a un clic.
        <nav className="pdv-vacio-sucursales" aria-label="Cambiar de sucursal">
          <p>Probar en otra sucursal:</p>
          <ul>
            {sucursales.map((s) => (
              <li key={s.id}>
                <a href={`/pdv?sucursal=${s.id}`}>{s.nombre}</a>
              </li>
            ))}
          </ul>
        </nav>
      )}
    </main>
  );
}

/** La sucursal de la URL solo si de verdad es suya; si no, la primera. */
function sucursalElegida(
  pedida: string | undefined,
  propias: string[],
): string | undefined {
  return pedida && propias.includes(pedida) ? pedida : propias[0];
}

/** Las suyas, y solo si tiene más de una: el selector no le sirve a quien
 * trabaja en un local. Si el catálogo falla, el PDV abre igual con la
 * sucursal actual — es un selector, no un dato del pedido. */
async function sucursalesDelUsuario(
  token: string,
  propias: string[],
): Promise<SucursalPdv[]> {
  if (propias.length <= 1) return [];
  return apiFetch<SucursalPdv[]>("/api/v1/sucursales", { token })
    .then((todas) => todas.filter((s) => propias.includes(s.id)))
    .catch(() => []);
}

type Contexto =
  | { ok: true; sucursalId: string; punto: PuntoVenta }
  | { ok: false; titulo: string; detalle: string };

async function resolverContexto(
  token: string,
  sucursalId: string,
): Promise<Contexto> {
  let puntos: PuntoVenta[];
  try {
    puntos = await apiFetch<PuntoVenta[]>(
      `/api/v1/sales/puntos-venta?sucursal_id=${sucursalId}`,
      { token },
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) redirect("/login");
    return {
      ok: false,
      titulo: "No se pudo cargar el punto de venta",
      detalle: "Revisa la conexión con la API e intenta de nuevo.",
    };
  }

  // El PDV atiende desde una caja física: canal `trabajador`. Los canales
  // `web`/`kiosko` son clientes del mismo contrato, no de esta pantalla.
  const punto = puntos.find((p) => p.canal === "trabajador") ?? puntos[0];
  if (!punto) {
    return {
      ok: false,
      titulo: "La sucursal no tiene puntos de venta",
      detalle:
        "Pídele a un administrador que dé de alta la caja de esta sucursal en Organización → Puntos de venta.",
    };
  }
  return { ok: true, sucursalId, punto };
}

export default async function PaginaPdv({
  searchParams,
}: {
  searchParams: Promise<{ sucursal?: string }>;
}) {
  // `/users/me` y no el JWT: los claims del token se congelan al emitirlo y
  // una reasignación de sucursal recién valdría al renovar. Acá se recalcula
  // contra la base en cada render.
  const { token, usuario } = await obtenerSesion();
  const parametros = await searchParams;

  const sucursales = await sucursalesDelUsuario(token, usuario.sucursales);
  const sucursalId = sucursalElegida(parametros.sucursal, usuario.sucursales);
  if (!sucursalId) {
    return (
      <Bloqueo
        titulo="Sin sucursal asignada"
        detalle="Tu usuario no tiene ninguna sucursal asignada, así que no hay caja que abrir. Pídele a un administrador que te asigne una."
      />
    );
  }

  const ctx = await resolverContexto(token, sucursalId);
  if (!ctx.ok) {
    return (
      <Bloqueo
        titulo={ctx.titulo}
        detalle={ctx.detalle}
        sucursales={sucursales.filter((s) => s.id !== sucursalId)}
      />
    );
  }

  return (
    // El PDV vive fuera del layout del back office, así que declara su propia
    // configuración de Maps: sin esto el campo de dirección de un delivery
    // quedaría sin buscador aunque la clave esté puesta.
    <ProveedorConfigMapas config={configMapas()}>
      <PdvCliente
        sucursalId={ctx.sucursalId}
        sucursales={sucursales}
        // Solo para esconder el botón de consulta a quien no puede gastar
        // cuota de Factiliza (ADR-041). La autorización real la sigue
        // haciendo la API en cada request.
        permisos={usuario.permisos}
        puntoVenta={{
          id: ctx.punto.id,
          serieBoleta: ctx.punto.serie_boleta,
          serieFactura: ctx.punto.serie_factura,
          modalidades: ctx.punto.modalidades_habilitadas ?? [
            "mesa",
            "takeout",
            "delivery",
          ],
        }}
      />
      {/* El nombre sale de `/users/me` y no del JWT: el token no lleva
          username, y la pantalla bloqueada tiene que decir de quién es la
          sesión que sigue abierta debajo. */}
      <BloqueoPorInactividad username={usuario.username} />
    </ProveedorConfigMapas>
  );
}
