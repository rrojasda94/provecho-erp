import { ApiError, apiFetch, leerPagina, type Pagina, type ParamsPagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import {
  AsientosCliente,
  type Asiento,
  type AsientoOmitido,
  type Cuenta,
} from "./asientos-cliente";

/** El libro crece con cada venta: se busca (por glosa) y pagina en el
 * servidor. Pedía la primera página y buscaba en el navegador, así que del
 * asiento 51 en adelante no se veía nada. */
export default async function AsientosPage({
  searchParams,
}: {
  searchParams: Promise<ParamsPagina>;
}) {
  const { token, usuario } = await obtenerSesion();
  const { query, pagina, tamano, q } = leerPagina(await searchParams);

  try {
    const [asientos, cuentas] = await Promise.all([
      apiFetch<Pagina<Asiento>>(`/api/v1/accounting/asientos?${query}`, { token }),
      apiFetch<Cuenta[]>("/api/v1/accounting/cuentas-contables", { token }),
    ]);

    // Los asientos que el ERP decidió no escribir (ADR-089). Aparte del
    // `Promise.all` y con su propio `catch`: es un aviso, y un aviso que no
    // carga no puede tumbar el libro contable — que es justo el error que se
    // viene a hacer visible.
    let omitidos: AsientoOmitido[] = [];
    try {
      omitidos = await apiFetch<AsientoOmitido[]>(
        "/api/v1/accounting/asientos-omitidos",
        { token },
      );
    } catch {
      // silencioso a propósito, ver comentario arriba.
    }

    return (
      <AsientosCliente
        asientos={asientos.items}
        pagina={{ total: asientos.total, page: pagina, pageSize: tamano, q }}
        cuentas={cuentas}
        omitidos={omitidos}
        permisos={usuario.permisos}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver el libro contable."
        : "No se pudo cargar el libro contable.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
