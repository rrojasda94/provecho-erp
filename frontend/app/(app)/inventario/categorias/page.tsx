import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import {
  CategoriasCliente,
  type Categoria,
  type Cuenta,
  type ProgramaConteo,
} from "./categorias-cliente";

type Params = Promise<{ categoria?: string }>;

export default async function CategoriasPage({
  searchParams,
}: {
  searchParams: Params;
}) {
  const { token } = await obtenerSesion();
  // `?categoria=<id>` es a donde llega `inventory.conteo_vencido` (ADR-036).
  const { categoria } = await searchParams;

  let categorias: Categoria[];
  try {
    categorias = await apiFetch<Categoria[]>("/api/v1/inventory/categorias", { token });
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver las categorías."
        : "No se pudo cargar el catálogo de categorías.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  // El programa de conteo es contexto: si falla, la pantalla sigue diciendo
  // qué categorías hay y cada cuánto se cuentan.
  const programa = await apiFetch<ProgramaConteo[]>(
    "/api/v1/inventory/conteos/programa",
    { token },
  ).catch(() => []);

  // El plan de cuentas es de otro módulo y exige `accounting.leer`, que quien
  // administra el catálogo no necesariamente tiene. Si niega, los campos caen
  // a texto con el código y el servidor los valida igual: un selector que no
  // carga no puede dejar la pantalla inservible.
  let cuentas: Cuenta[] = [];
  let avisoCuentas: string | null = null;
  try {
    cuentas = await apiFetch<Cuenta[]>("/api/v1/accounting/cuentas-contables", {
      token,
    });
  } catch (e) {
    avisoCuentas =
      e instanceof ApiError && e.status === 403
        ? "No puedes ver el plan de cuentas (accounting.leer): escribe el código a mano."
        : "No se pudo cargar el plan de cuentas.";
  }

  return (
    <CategoriasCliente
      categorias={categorias}
      programa={programa}
      resaltado={categoria ?? null}
      cuentas={cuentas}
      avisoCuentas={avisoCuentas}
    />
  );
}
