import { ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";

/**
 * Entrada al BI autoservicio (ADR-082). Hoy es solo el enlace a Superset —
 * el SSO (Fase B) ya funciona, pero los tableros embebidos (Fase D, guest
 * token vía `GET /api/v1/bi/dashboards/{id}/guest-token`) esperan a que
 * existan tableros de verdad que embeber, que a su vez esperan al droplet
 * real (Fase C, ver `docs/engineering/bi-superset.md`).
 *
 * `BI_URL` se lee del servidor y no como `NEXT_PUBLIC_*` — mismo criterio
 * que `GOOGLE_MAPS_BROWSER_KEY` (`frontend/.env.example`): así la imagen no
 * queda atada a un dominio de un solo entorno.
 *
 * El permiso ya lo exigió `ModuloShell` (`bi.acceder`): quien llega hasta
 * acá puede entrar, y lo único que puede faltar es la configuración.
 */
export default function BiPage() {
  const biUrl = process.env.BI_URL;

  return (
    <div className="flex flex-col gap-6">
      <div className="max-w-xl rounded-lg border border-border bg-card p-6">
        <h1 className="text-lg font-semibold">Análisis avanzado</h1>
        <p className="mt-2 text-sm text-gray">
          Elige libremente qué cruzar, compara periodos y arma tus propios
          gráficos sobre los datos de Provecho — sin pedir un reporte nuevo
          cada vez. Entras con la misma sesión, sin un segundo usuario ni
          contraseña.
        </p>
        {biUrl ? (
          <Button className="mt-4" render={<a href={biUrl} target="_blank" rel="noopener noreferrer" />}>
            Abrir Superset
            <ExternalLink className="size-4" aria-hidden />
          </Button>
        ) : (
          <p className="mt-4 rounded border border-accent/40 bg-accent/5 p-3 text-sm text-accent">
            Todavía no está configurado. Pídeselo a quien administra Provecho.
          </p>
        )}
      </div>
    </div>
  );
}
