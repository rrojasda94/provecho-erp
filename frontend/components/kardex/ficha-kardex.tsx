import Link from "next/link";

import { KardexArticulo } from "@/components/kardex/kardex-articulo";
import { Rastro } from "@/components/shell/rastro";
import { ApiError, apiFetch } from "@/lib/api";
import { hoyEnZonaDelNegocio } from "@/lib/fechas";
import {
  diasHasta,
  estadoDeSede,
  leerAmbito,
  queryDeAmbito,
  type Ambito,
  type Kardex,
  type KardexAlmacen,
  type PrecioHistorico,
} from "@/lib/kardex";
import { obtenerSesion } from "@/lib/sesion";

type Articulo = {
  id: string;
  id_interno: string;
  nombre: string;
  tipo: string;
  unidad_medida_id: string;
  costo_promedio: string;
  archivado: boolean;
  controla_lote: boolean;
  dias_alerta_vencimiento: number | null;
};

type UnidadMedida = { id: string; nombre: string };

/** Lo que la ficha lee de la URL: dónde mirar y de dónde tomar precios. */
export type ParamsKardex = { ambito?: string; precios?: string };

function mensajeDeError(e: unknown): string {
  const status = e instanceof ApiError ? e.status : 0;
  if (status === 403)
    return "Tu usuario no tiene permiso para ver este artículo.";
  if (status === 404) return "Ese artículo no existe.";
  return "No se pudo cargar el artículo.";
}

/** Nombre del ámbito elegido, sacado de las filas por almacén. */
function nombreDe(ambito: Ambito, sedes: KardexAlmacen[]): string | undefined {
  if (!ambito) return undefined;
  const fila = sedes.find((s) =>
    ambito.tipo === "almacen"
      ? s.almacen_id === ambito.id
      : s.sucursal_id === ambito.id,
  );
  if (!fila) return undefined;
  return ambito.tipo === "almacen"
    ? fila.almacen
    : (fila.sucursal ?? undefined);
}

/** Las sedes distintas que aparecen entre los almacenes. */
function sucursalesDe(sedes: KardexAlmacen[]): [string, string][] {
  const mapa = new Map<string, string>();
  for (const s of sedes)
    if (s.sucursal_id && s.sucursal) mapa.set(s.sucursal_id, s.sucursal);
  return [...mapa];
}

function Opcion({
  href,
  activa,
  children,
}: {
  href: string;
  activa: boolean;
  children: string;
}) {
  return (
    <Link
      href={href}
      scroll={false}
      aria-current={activa ? "true" : undefined}
      className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
        activa
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border text-foreground hover:bg-muted"
      }`}
    >
      {children}
    </Link>
  );
}

/** Toda la empresa, cada sede o cada almacén: en la URL, para que el enlace
 * se pueda compartir con quien maneja ese local. */
function SelectorAmbito({
  ambito,
  sedes,
}: {
  ambito: Ambito;
  sedes: KardexAlmacen[];
}) {
  const sucursales = sucursalesDe(sedes);
  return (
    <nav aria-label="Dónde mirar" className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <Opcion href="?" activa={!ambito}>
          Toda la empresa
        </Opcion>
        {sucursales.map(([id, nombre]) => (
          <Opcion
            key={id}
            href={`?ambito=sucursal:${id}`}
            activa={ambito?.id === id}
          >
            {`Sede ${nombre}`}
          </Opcion>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {sedes.map((s) => (
          <Opcion
            key={s.almacen_id}
            href={`?ambito=almacen:${s.almacen_id}`}
            activa={ambito?.id === s.almacen_id}
          >
            {s.almacen}
          </Opcion>
        ))}
      </div>
    </nav>
  );
}

const TONO = {
  peligro: "bg-status-danger-surface",
  alerta: "bg-status-warning-surface",
} as const;

const cifra = (v: string | null) =>
  v === null
    ? "—"
    : Number(v).toLocaleString("es-PE", { maximumFractionDigits: 2 });

function cobertura(s: KardexAlmacen, hoy: string): string {
  if (!s.proxima_compra) return "—";
  const dias = diasHasta(s.proxima_compra, hoy);
  return dias <= 0 ? "Reponer hoy" : `${dias} día(s)`;
}

/** La realidad de cada sede lado a lado, lo que se agota primero arriba. */
function TablaSedes({ sedes, hoy }: { sedes: KardexAlmacen[]; hoy: string }) {
  if (sedes.length < 2) return null;
  return (
    <figure className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
      <figcaption className="text-sm font-semibold text-foreground">
        Cómo está cada sede
        <span className="ml-2 text-xs font-normal text-muted-foreground">
          Rojo: bajo el mínimo · ámbar: reponer en una semana o menos
        </span>
      </figcaption>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="py-1 pr-3">Almacén</th>
              <th className="py-1 pr-3">Sede</th>
              <th className="py-1 pr-3 text-right">Stock</th>
              <th className="py-1 pr-3 text-right">Mínimo</th>
              <th className="py-1 pr-3 text-right">Consumo diario</th>
              <th className="py-1 pr-3 text-right">Cobertura</th>
              <th className="py-1 text-right">Reposiciones (90 d)</th>
            </tr>
          </thead>
          <tbody>
            {sedes.map((s) => {
              const estado = estadoDeSede(s, hoy);
              return (
                <tr
                  key={s.almacen_id}
                  className={`border-t border-border ${estado ? TONO[estado] : ""}`}
                >
                  <td className="py-1.5 pr-3">
                    <Link
                      href={`?ambito=almacen:${s.almacen_id}`}
                      scroll={false}
                      className="font-medium text-primary hover:underline"
                    >
                      {s.almacen}
                    </Link>
                  </td>
                  <td className="py-1.5 pr-3">{s.sucursal ?? "—"}</td>
                  <td className="cifra py-1.5 pr-3 text-right">
                    {cifra(s.stock)}
                  </td>
                  <td className="cifra py-1.5 pr-3 text-right">
                    {cifra(s.stock_minimo)}
                  </td>
                  <td className="cifra py-1.5 pr-3 text-right">
                    {cifra(s.consumo_diario)}
                  </td>
                  <td className="cifra py-1.5 pr-3 text-right">
                    {cobertura(s, hoy)}
                  </td>
                  <td className="cifra py-1.5 text-right">
                    {s.reposiciones_90_dias}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </figure>
  );
}

/** Los precios: de la empresa, salvo que se pidan las compras directas del
 * almacén elegido. Un local abastecido por el central no compra nada. */
function PreciosPropios({
  ambito,
  activo,
}: {
  ambito: Ambito;
  activo: boolean;
}) {
  if (ambito?.tipo !== "almacen") return null;
  const base = `?ambito=almacen:${ambito.id}`;
  return (
    <Link
      href={activo ? base : `${base}&precios=almacen`}
      scroll={false}
      className="self-start text-xs font-medium text-primary hover:underline"
    >
      {activo
        ? "Ver precios de toda la empresa"
        : "Ver solo las compras que entraron directo a este almacén"}
    </Link>
  );
}

function datosDe(articulo: Articulo): [string, string][] {
  return [
    ["Código interno", articulo.id_interno],
    ["Tipo", articulo.tipo],
    ["Costo promedio", articulo.costo_promedio],
    ["Controla lote", articulo.controla_lote ? "Sí" : "No"],
    [
      "Aviso de vencimiento",
      articulo.dias_alerta_vencimiento === null
        ? "—"
        : `${articulo.dias_alerta_vencimiento} día(s) antes`,
    ],
    ["Estado", articulo.archivado ? "Archivado" : "Activo"],
  ];
}

function alcanceDePrecios(
  ambito: Ambito,
  delAlmacen: boolean,
  donde: string | undefined,
): string | undefined {
  if (!ambito) return undefined;
  return delAlmacen ? donde : "toda la empresa";
}

/** Lo que la ficha dibuja igual si falla: precios (otro módulo), unidad y la
 * comparación por sede. Cada uno cae a vacío por su cuenta. */
async function complementos(
  id: string,
  token: string,
  unidadId: string,
  almacenDePrecios: string | null,
) {
  const rutaPrecios = `/api/v1/purchases/articulos/${id}/historial-precios${
    almacenDePrecios ? `?almacen_id=${almacenDePrecios}` : ""
  }`;
  const [precios, unidades, sedes] = await Promise.all([
    apiFetch<PrecioHistorico[]>(rutaPrecios, { token }).catch(() => null),
    apiFetch<UnidadMedida[]>("/api/v1/inventory/unidades-medida", {
      token,
    }).catch(() => [] as UnidadMedida[]),
    apiFetch<KardexAlmacen[]>(
      `/api/v1/inventory/articulos/${id}/kardex/por-almacen`,
      {
        token,
      },
    ).catch(() => [] as KardexAlmacen[]),
  ]);
  const unidad = unidades.find((u) => u.id === unidadId)?.nombre ?? "";
  return { precios, unidad, sedes };
}

/**
 * Ficha de un artículo con su kardex gráfico. La misma en Inventario y en
 * Compras: cambia por dónde se llega, no lo que se necesita saber para
 * decidir cuándo y a cuánto comprar.
 *
 * Se mira en la empresa entera, en una sede o en un almacén (`?ambito=`), y
 * compara las sedes lado a lado. El historial de precios es de `purchases` y
 * lo pide aparte: sin `purchases.leer` la ficha se dibuja sin ese gráfico.
 */
export async function FichaKardex({
  id,
  params,
}: {
  id: string;
  params: ParamsKardex;
}) {
  const { token } = await obtenerSesion();
  const ambito = leerAmbito(params.ambito);
  const preciosDelAlmacen =
    ambito?.tipo === "almacen" && params.precios === "almacen";

  let articulo: Articulo;
  let kardex: Kardex;
  try {
    [articulo, kardex] = await Promise.all([
      apiFetch<Articulo>(`/api/v1/inventory/articulos/${id}`, { token }),
      apiFetch<Kardex>(
        `/api/v1/inventory/articulos/${id}/kardex?${queryDeAmbito(ambito)}`,
        {
          token,
        },
      ),
    ]);
  } catch (e) {
    return <p className="text-secondary">{mensajeDeError(e)}</p>;
  }
  const { precios, unidad, sedes } = await complementos(
    id,
    token,
    articulo.unidad_medida_id,
    preciosDelAlmacen ? ambito.id : null,
  );
  const donde = nombreDe(ambito, sedes);
  const hoy = hoyEnZonaDelNegocio();

  return (
    <section className="flex flex-col gap-6">
      <Rastro hoja={articulo.nombre} />
      <h1 className="font-heading text-xl italic uppercase text-foreground">
        {articulo.nombre}
      </h1>
      <dl className="grid gap-4 rounded-lg border border-border bg-card p-4 sm:grid-cols-3">
        {datosDe(articulo).map(([etiqueta, valor]) => (
          <div key={etiqueta} className="flex flex-col gap-0.5">
            <dt className="text-xs font-bold uppercase text-muted-foreground">
              {etiqueta}
            </dt>
            <dd className="text-sm text-foreground">{valor}</dd>
          </div>
        ))}
      </dl>
      {sedes.length > 1 && <SelectorAmbito ambito={ambito} sedes={sedes} />}
      {precios && <PreciosPropios ambito={ambito} activo={preciosDelAlmacen} />}
      <KardexArticulo
        kardex={kardex}
        precios={precios}
        unidad={unidad}
        hoy={hoy}
        ambito={donde}
        alcancePrecios={alcanceDePrecios(ambito, preciosDelAlmacen, donde)}
      />
      <TablaSedes sedes={sedes} hoy={hoy} />
    </section>
  );
}
