"use client";

import { useActionState } from "react";

import {
  aprobarParametroAction,
  proponerTarifaDeliveryAction,
  type EstadoGerencia,
} from "../actions";

export type ConfiguracionDelivery = {
  tarifa_base: string;
  precio_por_km: string;
  radio_km: string;
  distritos_restringidos: string[];
  activa: boolean;
  rutas_reales: boolean;
};

export type PropuestaDelivery = {
  id: string;
  codigo: string;
  valor: Record<string, unknown>;
  valor_display: string | null;
};

const ESTADO_INICIAL: EstadoGerencia = { error: "", ok: false };

/** Los `<input>` sueltos solo se estilan dentro de un `<dialog>`
 * (`globals.css`), y esta pantalla es un formulario de página. Misma clase
 * que el resto de los formularios que no viven en un diálogo — ver
 * `contabilidad/periodos`. */
const CAMPO = "rounded border border-gray/40 px-2 py-1";

const ROTULOS: Record<string, string> = {
  delivery_tarifa_base: "Tarifa base",
  delivery_precio_por_km: "Precio por kilómetro",
  delivery_radio_km: "Radio máximo",
  delivery_distritos_restringidos: "Distritos sin reparto propio",
};

/** Un renglón de diagnóstico. Existe porque la degradación de ADR-053/054 es
 * silenciosa por diseño —sin claves el ERP se comporta como antes— y del lado
 * de Gerencia eso es una pantalla que parece andar y no anda. */
function Estado({ ok, si, no }: { ok: boolean; si: string; no: string }) {
  return (
    <li className="flex items-start gap-2">
      <span aria-hidden className={ok ? "text-primary" : "text-secondary"}>
        {ok ? "●" : "○"}
      </span>
      <span className={ok ? "text-dark" : "text-secondary"}>{ok ? si : no}</span>
    </li>
  );
}

function Campo({
  nombre,
  etiqueta,
  ayuda,
  defaultValue,
  paso = "0.01",
}: {
  nombre: string;
  etiqueta: string;
  ayuda: string;
  defaultValue: string;
  paso?: string;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm font-semibold">
      {etiqueta}
      <input
        name={nombre}
        type="number"
        min="0"
        step={paso}
        defaultValue={defaultValue}
        className={`w-40 ${CAMPO}`}
      />
      <input type="hidden" name={`actual_${nombre}`} value={defaultValue} />
      <span className="text-xs font-normal text-gray">{ayuda}</span>
    </label>
  );
}

/** `valor_display` solo lo escribe el backend para las magnitudes con unidad
 * (RN-GER-010): un monto sale "S/ 7.50" y lo adimensional sale `null`. En el
 * listado genérico eso cae en un `JSON.stringify`, que acá sería pedirle a
 * Gerencia que apruebe `{"km":"8"}`. */
function comoTexto(p: PropuestaDelivery): string {
  if (p.valor_display) return p.valor_display;
  if (Array.isArray(p.valor.distritos)) {
    return p.valor.distritos.join(", ") || "ninguno";
  }
  if (p.valor.km !== undefined) return `${p.valor.km} km`;
  return JSON.stringify(p.valor);
}

function Pendiente({ propuesta }: { propuesta: PropuestaDelivery }) {
  const [estado, aprobar, aprobando] = useActionState(
    aprobarParametroAction,
    ESTADO_INICIAL,
  );
  return (
    <li className="flex flex-wrap items-center gap-3 border-b border-gray/15 py-2 text-sm">
      <span className="font-semibold text-dark">
        {ROTULOS[propuesta.codigo] ?? propuesta.codigo}
      </span>
      <span>{comoTexto(propuesta)}</span>
      <form action={aprobar} className="ml-auto">
        <input type="hidden" name="parametro_id" value={propuesta.id} />
        <button
          type="submit"
          disabled={aprobando}
          className="rounded bg-primary px-3 py-1 text-xs font-bold text-white hover:bg-secondary"
        >
          {aprobando ? "Aprobando..." : "Aprobar"}
        </button>
      </form>
      {estado.error && (
        <p role="alert" className="w-full text-xs font-semibold text-secondary">
          {estado.error}
        </p>
      )}
    </li>
  );
}

/**
 * Tarifa del delivery propio (ADR-054, ADR-068).
 *
 * Escribe sobre `parametro_empresa` como cualquier otro valor operativo, así
 * que **el cambio no llega al PDV hasta que se aprueba** (ADR-014,
 * RN-GER-009). Son dos pasos y no uno a propósito: acá se define cuánta plata
 * paga el cliente, y el mismo mecanismo que audita el umbral de una orden de
 * compra vale para esto.
 *
 * La tarifa que se muestra arriba es la **efectiva** —lo aprobado, o la
 * semilla del `.env` si Gerencia todavía no aprobó nada—, que es con la que
 * el PDV está cobrando ahora mismo.
 */
export function DeliveryCliente({
  configuracion,
  pendientes,
  empresaId,
  conMapa,
}: {
  configuracion: ConfiguracionDelivery;
  pendientes: PropuestaDelivery[];
  empresaId: string;
  /** El navegador tiene clave de Maps: sin ella no hay buscador ni pin, y
   * una dirección sin ancla no se puede medir. */
  conMapa: boolean;
}) {
  const [estado, guardar, guardando] = useActionState(
    proponerTarifaDeliveryAction,
    ESTADO_INICIAL,
  );
  const distritos = configuracion.distritos_restringidos.join(", ");

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="font-heading text-xl text-dark">Tarifa del delivery</h1>
        <p className="mt-1 text-sm text-gray">
          Cuánto se cobra por llevar un pedido y hasta dónde llega el reparto propio.
          El servidor mide la distancia de manejo real y congela el costo en la venta;
          el valor nuevo empieza a cobrarse recién cuando se aprueba abajo.
        </p>
      </div>

      <ul className="flex flex-col gap-1 rounded-lg border border-border bg-card p-4 text-sm">
        <Estado
          ok={configuracion.activa}
          si={`Cobrando: S/ ${configuracion.tarifa_base} de base + S/ ${configuracion.precio_por_km} por km.`}
          no="El reparto no se está cobrando: la tarifa base y el precio por km están en cero."
        />
        <Estado
          ok={configuracion.rutas_reales}
          si="Distancias medidas por carretera con Google Routes."
          no="Sin GOOGLE_MAPS_SERVER_KEY: las distancias se estiman en línea recta y se cobran marcadas «aprox.»."
        />
        <Estado
          ok={conMapa}
          si="El mapa y el buscador de direcciones están disponibles."
          no="Sin GOOGLE_MAPS_BROWSER_KEY: las direcciones se escriben a mano, sin punto en el mapa, y sin punto no hay distancia que medir."
        />
      </ul>

      <form action={guardar} className="flex max-w-md flex-col gap-4">
        <input type="hidden" name="empresa_id" value={empresaId} />
        <input type="hidden" name="divisa" value="PEN" />

        <Campo
          nombre="tarifa_base"
          etiqueta="Tarifa base (S/)"
          ayuda="Lo que cuesta salir, antes del primer kilómetro. 0 = solo se cobra la distancia."
          defaultValue={configuracion.tarifa_base}
        />
        <Campo
          nombre="precio_por_km"
          etiqueta="Precio por kilómetro (S/)"
          ayuda="Por kilómetro de manejo real, no en línea recta."
          defaultValue={configuracion.precio_por_km}
        />
        <Campo
          nombre="radio_km"
          etiqueta="Radio máximo (km)"
          ayuda="Pasado este radio se sugiere derivar el pedido a una plataforma externa. 0 = sin radio."
          defaultValue={configuracion.radio_km}
          paso="0.1"
        />
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Distritos sin reparto propio
          <input
            name="distritos"
            defaultValue={distritos}
            placeholder="Belén, Morales"
            className={CAMPO}
          />
          <input type="hidden" name="actual_distritos" value={distritos} />
          <span className="text-xs font-normal text-gray">
            Separados por coma. El distrito llega con la dirección del mapa; sin ancla
            no hay distrito que comparar.
          </span>
        </label>
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Motivo
          <input
            name="motivo"
            placeholder="Por qué se cambia la tarifa"
            className={CAMPO}
          />
        </label>

        {estado.error && (
          <p role="alert" className="text-sm font-semibold text-secondary">
            {estado.error}
          </p>
        )}
        <button
          type="submit"
          disabled={guardando}
          className="self-start rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
        >
          {guardando ? "Proponiendo..." : "Proponer cambio"}
        </button>
      </form>

      <section>
        <h2 className="font-heading text-base text-dark">Esperando aprobación</h2>
        {pendientes.length === 0 ? (
          <p className="mt-1 text-sm text-gray">
            Nada pendiente: lo que se ve arriba es lo que el PDV está cobrando.
          </p>
        ) : (
          <ul className="mt-2 flex flex-col">
            {pendientes.map((p) => (
              <Pendiente key={p.id} propuesta={p} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
