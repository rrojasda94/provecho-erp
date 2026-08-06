import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { CampanasCliente, type Campana, type Marca } from "./campanas-cliente";

export default async function MarketingPage() {
  const { token, usuario } = await obtenerSesion();

  try {
    const [campanas, marcas] = await Promise.all([
      apiFetch<Pagina<Campana>>("/api/v1/marketing/campanas", { token }),
      apiFetch<Marca[]>("/api/v1/marcas", { token }),
    ]);
    return (
      <CampanasCliente
        campanas={campanas.items}
        marcas={marcas}
        // Quien redacta el brief no lo aprueba (RN-MKT-003): el botón solo
        // aparece si este usuario tiene el permiso, en vez de ofrecerlo y
        // devolver un 403 al tocarlo.
        puedeAprobar={usuario.permisos.some(
          (p) => p === "marketing.campana_aprobar" || p === "*",
        )}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver marketing."
        : "No se pudieron cargar las campañas.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
