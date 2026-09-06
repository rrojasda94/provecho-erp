import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import {
  AsientosCliente,
  type Asiento,
  type AsientoOmitido,
  type Cuenta,
} from "./asientos-cliente";

export default async function AsientosPage() {
  const { token, usuario } = await obtenerSesion();

  try {
    const [asientos, cuentas] = await Promise.all([
      apiFetch<Pagina<Asiento>>("/api/v1/accounting/asientos", { token }),
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
