"use client";

import { useState } from "react";

import { ErrorApi, pedir } from "@/lib/cliente-api";
import { tipoPorLargo, type TipoConsulta } from "@/lib/documento";
import { puedeConsultarDocumento } from "@/lib/permisos";

/** Lo que devuelve la consulta. Las claves que no aplican al tipo pedido
 * simplemente no vienen: el DNI no trae provincia ni el RUC fecha de
 * nacimiento. */
export type Consulta = Record<string, string | boolean | null>;

/** `auto` deja que el largo decida a quién se le pregunta (RN-CPP-003). Lo
 * usan los campos donde el cliente dicta un número sin decir qué es —caja—;
 * las fichas de alta, donde el campo ya es "RUC" o "DNI", siguen fijando el
 * tipo para poder avisar "eso no es un RUC" en vez de consultar el padrón
 * equivocado. */
export type TipoPedido = TipoConsulta | "auto";

/** Dos llamadas y no una con `${tipo}` interpolado: el chequeo de contrato
 * (`lib/contrato.test.ts`) lee la ruta literal del código, y una variable en
 * el medio la vuelve ilegible — con lo que estas dos rutas dejarían de
 * verificarse contra `openapi.json`. */
function consultar(tipo: TipoConsulta, numero: string): Promise<Consulta> {
  const n = encodeURIComponent(numero);
  return tipo === "dni"
    ? pedir<Consulta>(`/consulta/dni/${n}`)
    : pedir<Consulta>(`/consulta/ruc/${n}`);
}

/** Escribe en el formulario lo que vino, sin pisar con vacío lo que ya
 * estaba: traer menos datos no es motivo para borrar los que había. */
function rellenar(form: HTMLFormElement, datos: Consulta, mapa: Record<string, string>) {
  for (const [nombreCampo, clave] of Object.entries(mapa)) {
    const control = form.elements.namedItem(nombreCampo);
    if (control instanceof HTMLInputElement && datos[clave]) {
      control.value = String(datos[clave]);
    }
  }
}

/** Qué padrón toca, o por qué no se puede saber. La decisión se toma acá y no
 * en cada llamador para que las dos formas del botón digan lo mismo. */
function resolverTipo(
  pedido: TipoPedido,
  numero: string,
): { tipo: TipoConsulta } | { aviso: string } {
  if (!numero) return { aviso: "Escribe el documento primero." };
  if (pedido !== "auto") return { tipo: pedido };
  const tipo = tipoPorLargo(numero);
  // No se consulta a ciegas: cada llamada gasta cuota de un proveedor pago, y
  // un número de nueve dígitos no está "casi bien" — no es ninguno de los dos.
  return tipo ? { tipo } : { aviso: "Deben ser 8 dígitos (DNI) u 11 (RUC)." };
}

/** El fetch, el "Buscando..." y el aviso — lo único que comparten las dos
 * formas del botón. De dónde sale el número y a dónde va la respuesta lo pone
 * cada una. */
function useConsultaDocumento() {
  const [estado, setEstado] = useState<{ buscando: boolean; aviso: string }>({
    buscando: false,
    aviso: "",
  });

  async function ejecutar(
    pedido: TipoPedido,
    numero: string,
    aplicar: (datos: Consulta) => void,
  ) {
    const limpio = numero.trim();
    const resuelto = resolverTipo(pedido, limpio);
    if ("aviso" in resuelto) {
      setEstado({ buscando: false, aviso: resuelto.aviso });
      return;
    }
    const etiqueta = resuelto.tipo.toUpperCase();
    setEstado({ buscando: true, aviso: "" });
    try {
      const datos = await consultar(resuelto.tipo, limpio);
      if (!datos.encontrado) {
        setEstado({
          buscando: false,
          aviso: `Ese ${etiqueta} no figura. Completa los datos a mano.`,
        });
        return;
      }
      aplicar(datos);
      setEstado({ buscando: false, aviso: "Datos traídos: revísalos antes de guardar." });
    } catch (err) {
      setEstado({
        buscando: false,
        aviso:
          err instanceof ErrorApi
            ? err.message
            : "No se pudo consultar. Completa los datos a mano.",
      });
    }
  }

  return { estado, ejecutar };
}

/** «Buscar por RUC», «Buscar DNI / RUC» — según lo que el campo admita. */
function textoBoton(tipo: TipoPedido): string {
  return tipo === "auto" ? "Buscar DNI / RUC" : `Buscar por ${tipo.toUpperCase()}`;
}

function Aviso({ texto }: { texto: string }) {
  if (!texto) return null;
  return (
    <span role="status" className="text-xs text-gray">
      {texto}
    </span>
  );
}

/**
 * "Buscar": trae de RENIEC/SUNAT lo que ya está escrito en otro lado y
 * rellena el formulario.
 *
 * Escribe **en el DOM** del `<form>` que lo contiene, y no en estado de
 * React, porque los formularios del ERP son no controlados (`defaultValue` +
 * `name`, ver `dialogo-formulario`). Levantar cada campo a estado para poder
 * rellenar tres sería reescribir la ficha entera por un botón. Donde la
 * pantalla **sí** lleva estado —los diálogos del PDV— va `ConsultaDocumento`,
 * que por dentro es lo mismo.
 *
 * Prellena, no decide: todo lo que escribe se puede corregir antes de
 * guardar, y si Factiliza no responde el alta sigue siendo posible tecleando
 * —mismo criterio que ADR-005—.
 *
 * **Se esconde solo.** El gate por `consulta.documento` vive acá y no en cada
 * pantalla que lo monta: repetirlo en seis lugares es cómo el séptimo se
 * olvida. Como `permisos` es obligatorio, montarlo sin decir de quién es la
 * sesión no compila.
 */
export function BuscarDocumento({
  permisos,
  tipo,
  campo,
  rellena,
}: {
  /** Los del usuario de la sesión. Sin `consulta.documento` no se dibuja
   * nada: el botón terminaría en un 403 y, peor, la consulta que sí sale
   * gasta cuota de Factiliza. */
  permisos: string[];
  tipo: TipoPedido;
  /** `name` del input que tiene el número a consultar. */
  campo: string;
  /** `name` del campo del formulario → clave de la respuesta. */
  rellena: Record<string, string>;
}) {
  const { estado, ejecutar } = useConsultaDocumento();

  async function buscar(e: React.MouseEvent<HTMLButtonElement>) {
    const form = e.currentTarget.form;
    if (!form) return;
    const numero = (form.elements.namedItem(campo) as HTMLInputElement | null)?.value ?? "";
    await ejecutar(tipo, numero, (datos) => rellenar(form, datos, rellena));
  }

  // Después del hook y no antes: el orden de los hooks no puede depender de
  // una condición.
  if (!puedeConsultarDocumento(permisos)) return null;

  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        onClick={buscar}
        disabled={estado.buscando}
        className="w-fit rounded border border-primary px-2 py-1 text-xs font-semibold text-primary hover:bg-primary/10 disabled:opacity-50"
      >
        {estado.buscando ? "Buscando..." : textoBoton(tipo)}
      </button>
      <Aviso texto={estado.aviso} />
    </div>
  );
}

/**
 * El mismo botón, para pantallas con estado propio: recibe el número que el
 * componente ya tiene y le devuelve la respuesta cruda por `onDatos`, que
 * decide qué campo llena con qué.
 *
 * Existe porque el PDV se dibuja con estado de React (un `useState` por campo)
 * y no con formularios no controlados: ahí `form.elements` no lleva a ningún
 * lado —el `value` de un input controlado se pisa en el siguiente render—.
 * Quien la usa recibe el objeto entero porque en `auto` no sabe de antemano si
 * le va a llegar una persona (`nombres`/`apellidos`) o una empresa
 * (`razon_social`/`direccion`).
 */
export function ConsultaDocumento({
  permisos,
  numero,
  onDatos,
  tipo = "auto",
  className,
}: {
  permisos: string[];
  /** El documento tal como está tecleado ahora. */
  numero: string;
  onDatos: (datos: Consulta) => void;
  tipo?: TipoPedido;
  /** La pantalla táctil le da su propio tamaño de dedo. */
  className?: string;
}) {
  const { estado, ejecutar } = useConsultaDocumento();

  if (!puedeConsultarDocumento(permisos)) return null;

  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        className={className}
        disabled={estado.buscando}
        onClick={() => ejecutar(tipo, numero, onDatos)}
      >
        {estado.buscando ? "Buscando..." : textoBoton(tipo)}
      </button>
      <Aviso texto={estado.aviso} />
    </div>
  );
}
