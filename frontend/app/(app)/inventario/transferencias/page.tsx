import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import {
  TransferenciasCliente,
  type OpcionSku,
  type Transferencia,
} from "./transferencias-cliente";

type Almacen = { id: string; nombre: string };
type Sku = { id: string; codigo: string; articulo_nombre: string };

export default async function TransferenciasPage() {
  const { token, usuario } = await obtenerSesion();

  let transferencias: Transferencia[];
  let problema = "";
  try {
    transferencias = (
      await apiFetch<Pagina<Transferencia>>("/api/v1/inventory/transferencias", {
        token,
      })
    ).items;
  } catch (e) {
    transferencias = [];
    problema =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los traslados."
        : "No se pudieron cargar los traslados.";
  }
  // Fuera del `catch`: construir JSX ahí adentro se lleva puesto el límite de
  // los error boundaries de React.
  if (problema) return <p className="text-secondary">{problema}</p>;

  // Los catálogos no bloquean el listado: sin ellos la tabla se ve con los
  // ids y los formularios quedan inertes, que es mejor que una pantalla en
  // blanco por un 403 de otra consulta.
  const [almacenes, skus] = await Promise.all([
    apiFetch<Almacen[]>("/api/v1/almacenes", { token }).catch(() => []),
    apiFetch<Sku[]>("/api/v1/inventory/skus", { token }).catch(() => []),
  ]);

  return (
    <TransferenciasCliente
      transferencias={transferencias}
      nombreDeAlmacen={Object.fromEntries(
        almacenes.map((a) => [a.id, a.nombre]),
      )}
      skus={skus.map(
        (s): OpcionSku => ({ id: s.id, etiqueta: `${s.articulo_nombre} (${s.codigo})` }),
      )}
      permisos={usuario.permisos}
    />
  );
}
