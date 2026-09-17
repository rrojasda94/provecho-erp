import { NextResponse } from "next/server";

/** Healthcheck del contenedor (`storefront/Dockerfile`). Nunca toca la API:
 * responder 200 mientras el proceso de Next esté vivo, sin importar si la
 * API está arriba, es lo que hace que el `apiFetch` que degrada a `null`
 * (build sin API, backend caído) no tumbe también el healthcheck. */
export function GET() {
  return NextResponse.json({ estado: "ok" });
}
