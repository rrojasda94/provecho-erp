"use client";

import { useState } from "react";

import { ErrorApi, pedir } from "@/lib/cliente-api";

/** Lo que devuelve la consulta. Las claves que no aplican al tipo pedido
 * simplemente no vienen: el DNI no trae provincia ni el RUC fecha de
 * nacimiento. */
type Consulta = Record<string, string | boolean | null>;

/** Dos llamadas y no una con `${tipo}` interpolado: el chequeo de contrato
 * (`lib/contrato.test.ts`) lee la ruta literal del código, y una variable en
 * el medio la vuelve ilegible — con lo que estas dos rutas dejarían de
 * verificarse contra `openapi.json`. */
function consultar(tipo: "dni" | "ruc", numero: string): Promise<Consulta> {
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

/**
 * "Buscar": trae de RENIEC/SUNAT lo que ya está escrito en otro lado y
 * rellena el formulario.
 *
 * Escribe **en el DOM** del `<form>` que lo contiene, y no en estado de
 * React, porque los formularios del ERP son no controlados (`defaultValue` +
 * `name`, ver `dialogo-formulario`). Levantar cada campo a estado para poder
 * rellenar tres sería reescribir la ficha entera por un botón.
 *
 * Prellena, no decide: todo lo que escribe se puede corregir antes de
 * guardar, y si Factiliza no responde el alta sigue siendo posible tecleando
 * —mismo criterio que ADR-005—.
 */
export function BuscarDocumento({
  tipo,
  campo,
  rellena,
}: {
  tipo: "dni" | "ruc";
  /** `name` del input que tiene el número a consultar. */
  campo: string;
  /** `name` del campo del formulario → clave de la respuesta. */
  rellena: Record<string, string>;
}) {
  const [estado, setEstado] = useState<{ buscando: boolean; aviso: string }>({
    buscando: false,
    aviso: "",
  });

  async function buscar(e: React.MouseEvent<HTMLButtonElement>) {
    const form = e.currentTarget.form;
    if (!form) return;
    const numero = (form.elements.namedItem(campo) as HTMLInputElement | null)?.value.trim();
    if (!numero) {
      setEstado({ buscando: false, aviso: `Escribe el ${tipo.toUpperCase()} primero.` });
      return;
    }
    setEstado({ buscando: true, aviso: "" });
    try {
      const datos = await consultar(tipo, numero);
      if (!datos.encontrado) {
        setEstado({
          buscando: false,
          aviso: `Ese ${tipo.toUpperCase()} no figura. Completa los datos a mano.`,
        });
        return;
      }
      rellenar(form, datos, rellena);
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

  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        onClick={buscar}
        disabled={estado.buscando}
        className="w-fit rounded border border-primary px-2 py-1 text-xs font-semibold text-primary hover:bg-primary/10 disabled:opacity-50"
      >
        {estado.buscando ? "Buscando..." : `Buscar por ${tipo.toUpperCase()}`}
      </button>
      {estado.aviso && (
        <span role="status" className="text-xs text-gray">
          {estado.aviso}
        </span>
      )}
    </div>
  );
}
