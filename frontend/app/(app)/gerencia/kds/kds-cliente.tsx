"use client";

import { useActionState } from "react";

import {
  aprobarParametroAction,
  proponerSemaforoKdsAction,
  type EstadoGerencia,
} from "../actions";

export type ConfiguracionKds = {
  minutos_ambar: number;
  minutos_rojo: number;
  color_normal: string;
  color_ambar: string;
  color_rojo: string;
};

export type PropuestaKds = {
  id: string;
  codigo: string;
  valor: Record<string, unknown>;
};

const ESTADO_INICIAL: EstadoGerencia = { error: "", ok: false };

/** Los `<input>` sueltos solo se estilan dentro de un `<dialog>`
 * (`globals.css`) y esta pantalla es un formulario de página — mismo criterio
 * que `gerencia/delivery`. */
const CAMPO = "rounded border border-gray/40 px-2 py-1";

const ROTULOS: Record<string, string> = {
  kds_minutos_ambar: "Minutos para el ámbar",
  kds_minutos_rojo: "Minutos para el rojo",
  kds_color_normal: "Color normal",
  kds_color_ambar: "Color ámbar",
  kds_color_rojo: "Color rojo",
};

function Minutos({
  nombre,
  etiqueta,
  ayuda,
  valor,
}: {
  nombre: string;
  etiqueta: string;
  ayuda: string;
  valor: number;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm font-semibold">
      {etiqueta}
      <input
        name={nombre}
        type="number"
        min="1"
        max="240"
        step="1"
        defaultValue={valor}
        className={`w-28 ${CAMPO}`}
      />
      <input type="hidden" name={`actual_${nombre}`} value={valor} />
      <span className="text-xs font-normal text-gray">{ayuda}</span>
    </label>
  );
}

/** `<input type="color">` nativo: el navegador ya trae un selector que
 * funciona con el dedo y con el teclado, y ninguna librería de picker vale
 * su peso para elegir tres colores. */
function Color({
  nombre,
  etiqueta,
  ayuda,
  valor,
}: {
  nombre: string;
  etiqueta: string;
  ayuda: string;
  valor: string;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm font-semibold">
      {etiqueta}
      <span className="flex items-center gap-2">
        <input
          name={nombre}
          type="color"
          defaultValue={valor}
          className="h-9 w-14 cursor-pointer rounded border border-gray/40"
        />
        <code className="text-xs font-normal text-gray">{valor}</code>
      </span>
      <input type="hidden" name={`actual_${nombre}`} value={valor} />
      <span className="text-xs font-normal text-gray">{ayuda}</span>
    </label>
  );
}

function comoTexto(p: PropuestaKds): string {
  if (typeof p.valor.minutos === "number") return `${p.valor.minutos} min`;
  if (typeof p.valor.color === "string") return p.valor.color;
  return JSON.stringify(p.valor);
}

function Pendiente({ propuesta }: { propuesta: PropuestaKds }) {
  const [estado, aprobar, aprobando] = useActionState(
    aprobarParametroAction,
    ESTADO_INICIAL,
  );
  const color = typeof propuesta.valor.color === "string" ? propuesta.valor.color : null;
  return (
    <li className="flex flex-wrap items-center gap-3 border-b border-gray/15 py-2 text-sm">
      <span className="font-semibold text-dark">
        {ROTULOS[propuesta.codigo] ?? propuesta.codigo}
      </span>
      {/* Un `#f87171` no le dice nada a nadie: se aprueba mirando el color. */}
      {color && (
        <span
          aria-hidden
          className="inline-block h-4 w-4 rounded border border-gray/40"
          style={{ background: color }}
        />
      )}
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
 * Semáforo del KDS.
 *
 * Escribe sobre `parametro_empresa` como cualquier valor operativo, así que
 * el cambio **no llega a la cocina hasta que se aprueba** (ADR-014,
 * RN-GER-009). Lo que se ve arriba es el semáforo efectivo: lo aprobado, o
 * los valores de fábrica si Gerencia todavía no aprobó nada.
 *
 * Se configura y no se fija en el código porque ocho minutos son una
 * eternidad en una barra de bebidas y nada en un horno a leña: el número
 * correcto lo sabe quien mira la cocina.
 */
export function KdsGerenciaCliente({
  configuracion,
  pendientes,
  empresaId,
}: {
  configuracion: ConfiguracionKds;
  pendientes: PropuestaKds[];
  empresaId: string;
}) {
  const [estado, guardar, guardando] = useActionState(
    proponerSemaforoKdsAction,
    ESTADO_INICIAL,
  );

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="font-heading text-xl text-dark">Tiempos y colores del KDS</h1>
        <p className="mt-1 text-sm text-gray">
          Cada tarjeta de la cocina muestra cuánto lleva esperando el pedido y cambia
          de color al pasar estos minutos. Un pedido ya listo se queda verde por más
          que espere: ese no espera por la cocina, espera por quien despacha.
        </p>
      </div>

      {/* La misma tarjeta que ve la cocina, con los colores que están puestos:
          aprobar un color sin verlo es aprobar un código hexadecimal. */}
      <div className="flex flex-wrap gap-3">
        {(
          [
            ["Recién tomado", configuracion.color_normal],
            [`Desde ${configuracion.minutos_ambar} min`, configuracion.color_ambar],
            [`Desde ${configuracion.minutos_rojo} min`, configuracion.color_rojo],
          ] as const
        ).map(([titulo, color]) => (
          <div
            key={titulo}
            className="w-44 rounded-lg border border-border bg-card p-3"
            style={{ borderTop: `4px solid ${color}` }}
          >
            <p className="text-sm font-semibold text-dark">#128</p>
            <p className="text-xs" style={{ color }}>
              {titulo}
            </p>
          </div>
        ))}
      </div>

      <form action={guardar} className="flex max-w-md flex-col gap-4">
        <input type="hidden" name="empresa_id" value={empresaId} />

        <Minutos
          nombre="minutos_ambar"
          etiqueta="Minutos para el ámbar"
          ayuda="A partir de acá la tarjeta llama la atención: «mirá esto»."
          valor={configuracion.minutos_ambar}
        />
        <Minutos
          nombre="minutos_rojo"
          etiqueta="Minutos para el rojo"
          ayuda="Tiene que ser mayor que el ámbar. Acá alguien va a ver qué pasó."
          valor={configuracion.minutos_rojo}
        />
        <Color
          nombre="color_normal"
          etiqueta="Color normal"
          ayuda="El pedido va en tiempo, o ya está listo."
          valor={configuracion.color_normal}
        />
        <Color
          nombre="color_ambar"
          etiqueta="Color ámbar"
          ayuda="Se está demorando."
          valor={configuracion.color_ambar}
        />
        <Color
          nombre="color_rojo"
          etiqueta="Color rojo"
          ayuda="La tablet de cocina se mira de lejos y con luz encima: conviene un color que se distinga del ámbar de un vistazo."
          valor={configuracion.color_rojo}
        />
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Motivo
          <input
            name="motivo"
            placeholder="Por qué se cambian los tiempos"
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
            Nada pendiente: lo que se ve arriba es lo que la cocina está usando.
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
