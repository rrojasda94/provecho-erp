"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";

import { crearPromocionAction, terminarPromocionAction } from "../actions";

export type Promocion = {
  id: string;
  nombre: string;
  tipo: "nxm" | "cantidad" | "combo" | "monto_minimo";
  condicion: Record<string, unknown>;
  beneficio: Record<string, unknown>;
  desde: string | null;
  hasta: string | null;
  dias_semana: number[] | null;
  hora_desde: string | null;
  hora_hasta: string | null;
  sucursal_id: string | null;
  modalidades: string[] | null;
  prioridad: number;
  acumulable: boolean;
  activa: boolean;
};

export type Sucursal = { id: string; nombre: string };

/** Los cuatro tipos, dichos como los dice el negocio y no como los guarda la
 * base. El formulario cambia de campos según cuál se elija: preguntar los
 * doce parámetros de los cuatro tipos a la vez es la forma de que nadie
 * complete ninguno bien. */
const TIPOS = [
  {
    clave: "nxm",
    nombre: "Lleva N, paga menos",
    ejemplo: "2x1, 3x2, la segunda a mitad de precio",
  },
  {
    clave: "cantidad",
    nombre: "Desde X unidades",
    ejemplo: "6 gaseosas → 15 % en las gaseosas",
  },
  {
    clave: "combo",
    nombre: "Combo",
    ejemplo: "hamburguesa + papas + gaseosa a precio fijo",
  },
  {
    clave: "monto_minimo",
    nombre: "Desde S/ X de pedido",
    ejemplo: "10 % desde S/ 80 · o sin mínimo, para el martes de pizzas",
  },
] as const;

const DIAS = [
  ["1", "Mar"],
  ["2", "Mié"],
  ["3", "Jue"],
  ["4", "Vie"],
  ["5", "Sáb"],
  ["6", "Dom"],
  ["0", "Lun"],
] as const;

const MODALIDADES = ["mesa", "takeout", "delivery"] as const;

const CAMPO = "flex flex-col gap-1 text-sm font-semibold";

type Numeros = Record<string, number | undefined>;

/** Cómo se lee una regla en una tabla, sin abrir nada. La columna existe
 * para responder "¿qué hace esta promoción?" de un vistazo — que es la
 * pregunta que se hace quien mira la lista, no "¿qué JSON tiene?". */
function comoSeLeeNxm(c: Numeros, b: Numeros): string {
  const pct = b.descuento_pct ?? 100;
  return pct === 100
    ? `Lleva ${c.lleva}, paga ${(c.lleva ?? 0) - (b.libera ?? 0)}`
    : `Lleva ${c.lleva}, ${b.libera} al ${pct} % de descuento`;
}

function comoSeLeeCombo(p: Promocion, b: Numeros): string {
  const productos = (p.condicion.producto_ids as string[] | undefined)?.length ?? 0;
  return b.precio_fijo != null
    ? `${productos} productos a S/ ${b.precio_fijo}`
    : `${productos} productos, uno gratis`;
}

function comoSeLee(p: Promocion): string {
  const c = p.condicion as Numeros;
  const b = p.beneficio as Numeros;
  if (p.tipo === "nxm") return comoSeLeeNxm(c, b);
  if (p.tipo === "cantidad") {
    return `Desde ${c.minimo} unidades, ${b.descuento_pct} % de descuento`;
  }
  if (p.tipo === "combo") return comoSeLeeCombo(p, b);
  return c.minimo
    ? `Desde S/ ${c.minimo}, ${b.descuento_pct} % de descuento`
    : `${b.descuento_pct} % mientras esté vigente`;
}

/** La vigencia en una línea. `—` es "siempre, hasta que alguien la apague",
 * que es como se piden la mitad de ellas. */
function cuandoCorre(p: Promocion): string {
  const partes: string[] = [];
  if (p.desde || p.hasta) partes.push(`${p.desde ?? "…"} → ${p.hasta ?? "…"}`);
  if (p.dias_semana?.length) {
    partes.push(
      p.dias_semana
        .map((d) => DIAS.find(([clave]) => Number(clave) === d)?.[1] ?? d)
        .join(" "),
    );
  }
  if (p.hora_desde && p.hora_hasta) {
    partes.push(`${p.hora_desde.slice(0, 5)}–${p.hora_hasta.slice(0, 5)}`);
  }
  return partes.join(" · ") || "Siempre";
}

function CamposDelTipo({ tipo }: { tipo: string }) {
  if (tipo === "nxm") {
    return (
      <>
        <label className={CAMPO}>
          Lleva
          <input name="lleva" type="number" min={2} defaultValue={2} required />
        </label>
        <label className={CAMPO}>
          De esas, van con descuento
          <input name="libera" type="number" min={1} defaultValue={1} required />
        </label>
        <label className={CAMPO}>
          Descuento sobre las liberadas (%)
          <input name="descuento_pct" type="number" min={1} max={100} defaultValue={100} />
          <span className="text-xs font-normal text-gray">
            100 % es un 2x1; 50 %, la segunda a mitad de precio.
          </span>
        </label>
      </>
    );
  }
  if (tipo === "cantidad") {
    return (
      <>
        <label className={CAMPO}>
          Desde cuántas unidades
          <input name="minimo" type="number" min={1} defaultValue={6} required />
        </label>
        <label className={CAMPO}>
          Descuento (%)
          <input name="descuento_pct" type="number" min={1} max={100} defaultValue={15} />
        </label>
      </>
    );
  }
  if (tipo === "combo") {
    return (
      <>
        <label className={CAMPO}>
          Precio fijo del combo (S/)
          <input name="precio_fijo" type="number" min={0} step="0.01" />
        </label>
        <label className={CAMPO}>
          …o el producto que va gratis
          <input name="gratis_producto_id" placeholder="id del producto" />
          <span className="text-xs font-normal text-gray">
            Uno de los dos, no los dos.
          </span>
        </label>
      </>
    );
  }
  return (
    <>
      <label className={CAMPO}>
        Desde cuánto de pedido (S/)
        <input name="minimo" type="number" min={0} step="0.01" defaultValue={0} />
        <span className="text-xs font-normal text-gray">
          Cero = sin mínimo: la promoción corre solo por su vigencia.
        </span>
      </label>
      <label className={CAMPO}>
        Descuento (%)
        <input name="descuento_pct" type="number" min={1} max={100} defaultValue={10} />
      </label>
    </>
  );
}

function DialogoNuevaPromocion({ sucursales }: { sucursales: Sucursal[] }) {
  const [tipo, setTipo] = useState<string>("nxm");
  return (
    <DialogoFormulario
      titulo="Nueva promoción"
      disparador="+ Nueva promoción"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearPromocionAction}
      alAbrir={() => setTipo("nxm")}
      ayuda="Se aplica sola cuando el pedido cumple: el cajero no la pide ni la firma. Para un descuento puntual con firma, eso se hace en la caja."
    >
      <label className={CAMPO}>
        Nombre
        <input name="nombre" maxLength={120} required placeholder="2x1 de martes" />
        <span className="text-xs font-normal text-gray">
          Es lo que el cliente lee en el ticket: que se explique solo.
        </span>
      </label>

      <fieldset className="flex flex-col gap-1.5">
        <legend className="text-sm font-semibold">Qué hace</legend>
        {TIPOS.map((t) => (
          <label key={t.clave} className="flex items-start gap-2 text-sm">
            <input
              type="radio"
              name="tipo"
              value={t.clave}
              checked={tipo === t.clave}
              onChange={() => setTipo(t.clave)}
            />
            <span>
              <strong>{t.nombre}</strong>
              <span className="block text-xs text-gray">{t.ejemplo}</span>
            </span>
          </label>
        ))}
      </fieldset>

      <CamposDelTipo tipo={tipo} />

      {tipo !== "combo" && (
        <label className={CAMPO}>
          Categorías que alcanza
          <input name="categoria_ids" placeholder="ids separados por coma" />
          <span className="text-xs font-normal text-gray">
            Vacío = todo el pedido.
          </span>
        </label>
      )}
      <label className={CAMPO}>
        {tipo === "combo" ? "Productos del combo" : "Productos que alcanza"}
        <input name="producto_ids" placeholder="ids separados por coma" />
      </label>

      <fieldset className="flex flex-col gap-1.5">
        <legend className="text-sm font-semibold">Cuándo corre</legend>
        <div className="flex gap-2">
          <label className={CAMPO}>
            Desde
            <input name="desde" type="date" />
          </label>
          <label className={CAMPO}>
            Hasta
            <input name="hasta" type="date" />
          </label>
        </div>
        <div className="flex flex-wrap gap-2 text-sm">
          {DIAS.map(([clave, etiqueta]) => (
            <label key={clave} className="flex items-center gap-1">
              <input type="checkbox" name="dias_semana" value={clave} />
              {etiqueta}
            </label>
          ))}
        </div>
        <div className="flex gap-2">
          <label className={CAMPO}>
            Desde las
            <input name="hora_desde" type="time" />
          </label>
          <label className={CAMPO}>
            Hasta las
            <input name="hora_hasta" type="time" />
          </label>
        </div>
        <span className="text-xs text-gray">
          Todo vacío = corre siempre. La franja puede cruzar la medianoche.
        </span>
      </fieldset>

      <fieldset className="flex flex-col gap-1.5">
        <legend className="text-sm font-semibold">Dónde</legend>
        <label className={CAMPO}>
          Sucursal
          <select name="sucursal_id" defaultValue="">
            <option value="">Todas</option>
            {sucursales.map((s) => (
              <option key={s.id} value={s.id}>
                {s.nombre}
              </option>
            ))}
          </select>
        </label>
        <div className="flex flex-wrap gap-2 text-sm">
          {MODALIDADES.map((m) => (
            <label key={m} className="flex items-center gap-1">
              <input type="checkbox" name="modalidades" value={m} />
              {m}
            </label>
          ))}
        </div>
        <span className="text-xs text-gray">
          Sin marcar ninguna = todas. Una promoción de salón no siempre vale
          en delivery, donde el margen ya se lo comió el reparto.
        </span>
      </fieldset>

      <label className={CAMPO}>
        Prioridad
        <input name="prioridad" type="number" defaultValue={0} />
        <span className="text-xs font-normal text-gray">
          Cuando dos promociones alcanzan el mismo plato, la de mayor
          prioridad se lo lleva.
        </span>
      </label>
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" name="acumulable" />
        <span>
          <strong>Se acumula con otras</strong>
          <span className="block text-xs text-gray">
            Se suma encima de lo que otra ya aplicó sobre los mismos platos.
            Sin marcar, cada plato lo descuenta una sola promoción — que es lo
            que evita regalar más de lo aprobado.
          </span>
        </span>
      </label>
    </DialogoFormulario>
  );
}

export function PromocionesCliente({
  promociones,
  sucursales,
  puedeGestionar,
}: {
  promociones: Promocion[];
  sucursales: Sucursal[];
  puedeGestionar: boolean;
}) {
  const router = useRouter();
  const [pendiente, iniciar] = useTransition();
  const [error, setError] = useState("");

  const terminar = (id: string) =>
    iniciar(async () => {
      const resultado = await terminarPromocionAction(id);
      setError(resultado.error);
      if (resultado.ok) router.refresh();
    });

  return (
    <section className="flex flex-col gap-4">
      <header className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-dark">Promociones</h1>
          <p className="text-sm text-gray">
            Se aplican solas cuando el pedido cumple. El cupón de la landing y
            el descuento manual de caja son otra cosa.
          </p>
        </div>
        {puedeGestionar && <DialogoNuevaPromocion sucursales={sucursales} />}
      </header>

      {error && <p className="text-secondary">{error}</p>}

      {promociones.length === 0 ? (
        <p className="text-gray">
          Todavía no hay promociones. Las que se creen acá empiezan a aplicarse
          en el PDV sin que nadie las toque.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[48rem] text-sm">
            <thead className="text-left text-xs uppercase text-gray">
              <tr>
                <th className="p-2">Nombre</th>
                <th className="p-2">Qué hace</th>
                <th className="p-2">Cuándo</th>
                <th className="p-2">Dónde</th>
                <th className="p-2">Prioridad</th>
                <th className="p-2" />
              </tr>
            </thead>
            <tbody>
              {promociones.map((p) => (
                <tr
                  key={p.id}
                  className={`border-t border-border ${p.activa ? "" : "opacity-50"}`}
                >
                  <td className="p-2 font-semibold text-dark">
                    {p.nombre}
                    {!p.activa && (
                      <span className="ml-2 text-xs font-normal text-gray">
                        terminada
                      </span>
                    )}
                    {p.acumulable && (
                      <span className="ml-2 text-xs font-normal text-gray">
                        acumulable
                      </span>
                    )}
                  </td>
                  <td className="p-2">{comoSeLee(p)}</td>
                  <td className="p-2">{cuandoCorre(p)}</td>
                  <td className="p-2">
                    {sucursales.find((s) => s.id === p.sucursal_id)?.nombre ??
                      "Todas"}
                    {p.modalidades?.length ? ` · ${p.modalidades.join(", ")}` : ""}
                  </td>
                  <td className="p-2">{p.prioridad}</td>
                  <td className="p-2 text-right">
                    {puedeGestionar && p.activa && (
                      <button
                        type="button"
                        className="text-xs font-semibold text-secondary"
                        disabled={pendiente}
                        onClick={() => terminar(p.id)}
                      >
                        Terminar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
