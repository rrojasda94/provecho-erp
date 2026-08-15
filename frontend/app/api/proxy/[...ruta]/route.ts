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
 *
 * **Lo único que agrega es el `Authorization`.** Todo lo demás pasa como
 * viene, en las dos direcciones (ADR-048): el cuerpo va y vuelve en bytes,
 * y el tipo de contenido lo deciden los extremos. Un proxy que decodifica
 * a texto y reetiqueta como JSON funciona mientras todo sea JSON y corrompe
 * en silencio lo primero que no lo sea — que fue exactamente lo que le pasó
 * al `.xlsx` de la plantilla de recetas.
 */

import { cookies } from "next/headers";

import { API_INTERNAL_URL } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

const METODOS_CON_CUERPO = new Set(["POST", "PUT", "PATCH"]);

/**
 * Las cabeceras de la respuesta que describen **el cuerpo**, y por eso son
 * las que el navegador necesita para saber qué acaba de recibir: si lo
 * dibuja, lo parsea o lo guarda, y con qué nombre.
 *
 * Es una lista blanca y no "todo menos una lista negra" por dos motivos
 * concretos, los dos con síntoma silencioso:
 *
 * - `content-encoding` / `content-length` vienen de una respuesta que
 *   `fetch` ya **descomprimió**. Reenviarlos le pide al navegador que
 *   gunzipee bytes planos, o que espere un largo que no es.
 * - `set-cookie` de la API terminaría en el navegador. La cookie de sesión
 *   la pone el login del lado de Next; nada de lo que la API mande tiene
 *   por qué cruzar.
 */
const CABECERAS_DEL_CUERPO = ["content-type", "content-disposition"];

async function reenviar(req: Request, ruta: string[]): Promise<Response> {
  const token = (await cookies()).get(COOKIE_TOKEN)?.value;
  if (!token) {
    return Response.json({ detail: "Sesión expirada" }, { status: 401 });
  }
  const consulta = new URL(req.url).search;
  const destino = `${API_INTERNAL_URL}/${ruta.join("/")}${consulta}`;

  // El `Content-Type` **entrante**, no uno fijo: en `multipart/form-data` el
  // header lleva un `boundary` generado por el navegador, y escribir uno
  // propio deja al servidor buscando una marca que el cuerpo no tiene. El
  // error que devuelve no menciona la palabra "boundary" por ningún lado.
  const tipo = req.headers.get("content-type");

  const respuesta = await fetch(destino, {
    method: req.method,
    headers: {
      ...(tipo ? { "Content-Type": tipo } : {}),
      Authorization: `Bearer ${token}`,
    },
    // `arrayBuffer()` y no `text()`: un `.xlsx` es un ZIP, y decodificarlo
    // como UTF-8 reemplaza cada byte inválido por U+FFFD. La corrupción es
    // irreversible y no falla — el archivo llega, pesa parecido y no abre.
    //
    // Se junta el cuerpo entero en memoria en vez de encadenar `req.body`:
    // pasar un stream exige `duplex: "half"`, que no está en el tipo
    // estándar de `RequestInit`, y lo que sube por acá son formularios y
    // planillas de catálogo, no archivos de gigabytes.
    body: METODOS_CON_CUERPO.has(req.method) ? await req.arrayBuffer() : undefined,
    cache: "no-store",
  });

  // 204 y 304 no admiten cuerpo: construir una Response con uno lanza
  // TypeError y el borrado parecería fallar aunque el servidor lo hizo.
  if (respuesta.status === 204 || respuesta.status === 304) {
    return new Response(null, { status: respuesta.status });
  }

  const cabeceras = new Headers();
  for (const nombre of CABECERAS_DEL_CUERPO) {
    const valor = respuesta.headers.get(nombre);
    if (valor) cabeceras.set(nombre, valor);
  }

  // El cuerpo se devuelve **sin tocar**, como stream: el detalle de error de
  // la API es lo que el cajero necesita ver ("el pago excede el saldo de la
  // cuenta") y una descarga es lo que el navegador tiene que guardar. Las
  // dos cosas se rompen igual si acá alguien las convierte a texto.
  return new Response(respuesta.body, { status: respuesta.status, headers: cabeceras });
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
