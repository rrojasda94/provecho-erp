/**
 * Proxy del PDV hacia la API.
 *
 * El token vive en una cookie **httpOnly**: el JavaScript del navegador no
 * puede leerlo, y así debe ser — una cookie legible por JS es una cookie
 * robable por cualquier script inyectado. Pero el PDV es una pantalla
 * intensamente interactiva y no puede resolver todo con Server Actions sin
 * pagar un round-trip de renderizado por cada tecla.
 *
 * La salida es este proxy: el navegador llama a `/api/proxy/...` sin
 * credenciales, Next adjunta el `Authorization` desde la cookie y reenvía.
 * El token nunca sale del servidor.
 *
 * No filtra rutas a propósito: la autorización real la hace la API, que
 * valida firma y permiso en cada request (ADR-004). Duplicar esa lista acá
 * solo crearía un segundo lugar donde olvidarse de actualizarla.
 */

import { cookies } from "next/headers";

import { API_INTERNAL_URL } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

const METODOS_CON_CUERPO = new Set(["POST", "PUT", "PATCH"]);

async function reenviar(req: Request, ruta: string[]): Promise<Response> {
  const token = (await cookies()).get(COOKIE_TOKEN)?.value;
  if (!token) {
    return Response.json({ detail: "Sesión expirada" }, { status: 401 });
  }
  const consulta = new URL(req.url).search;
  const destino = `${API_INTERNAL_URL}/${ruta.join("/")}${consulta}`;

  const respuesta = await fetch(destino, {
    method: req.method,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: METODOS_CON_CUERPO.has(req.method) ? await req.text() : undefined,
    cache: "no-store",
  });

  // 204 y 304 no admiten cuerpo: construir una Response con uno lanza
  // TypeError y el borrado parecería fallar aunque el servidor lo hizo.
  if (respuesta.status === 204 || respuesta.status === 304) {
    return new Response(null, { status: respuesta.status });
  }

  // Se devuelve el cuerpo tal cual: el detalle de error de la API es lo que
  // el cajero necesita ver ("el pago excede el saldo de la cuenta"), no un
  // mensaje genérico inventado acá.
  const cuerpo = await respuesta.text();
  return new Response(cuerpo, {
    status: respuesta.status,
    headers: { "Content-Type": "application/json" },
  });
}

type Contexto = { params: Promise<{ ruta: string[] }> };

export async function GET(req: Request, { params }: Contexto) {
  return reenviar(req, (await params).ruta);
}

export async function POST(req: Request, { params }: Contexto) {
  return reenviar(req, (await params).ruta);
}

export async function PATCH(req: Request, { params }: Contexto) {
  return reenviar(req, (await params).ruta);
}

export async function DELETE(req: Request, { params }: Contexto) {
  return reenviar(req, (await params).ruta);
}
