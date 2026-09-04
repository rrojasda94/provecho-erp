import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import {
  TransferenciasCliente,
  type Transferencia,
} from "./transferencias-cliente";

type Almacen = { id: string; nombre: string };

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

  const almacenes = await apiFetch<Almacen[]>("/api/v1/almacenes", {
    token,
  }).catch(() => []);

  return (
    <TransferenciasCliente
      transferencias={transferencias}
      nombreDeAlmacen={Object.fromEntries(
        almacenes.map((a) => [a.id, a.nombre]),
      )}
      permisos={usuario.permisos}
    />
  );
}
