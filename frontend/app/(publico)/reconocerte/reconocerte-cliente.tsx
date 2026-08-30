"use client";

import Link from "next/link";
import { startTransition, useActionState, useRef, useState } from "react";

import { CampoDireccion } from "@/components/direccion/campo-direccion";

import { buscarNombreAction, registrarAction } from "./actions";
import { ESTADO_INICIAL, type Cupon } from "./estado";

/** Fecha ISO → «22 de setiembre de 2026». `T00:00` fuerza hora local: sin él
 * el navegador la lee como UTC y en Perú (UTC-5) muestra el día anterior. */
function enLetras(iso: string): string {
  return new Date(`${iso}T00:00`).toLocaleDateString("es-PE", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function TarjetaCupon({ cupon, descuento }: { cupon: Cupon; descuento: number }) {
  return (
    <section className="reconocerte-cupon" aria-live="polite">
      <p className="reconocerte-cupon-saludo">
        {cupon.ya_estaba_registrado
          ? "¡Ya te conocíamos! Este es tu código:"
          : "¡Listo! Te registramos. Este es tu código:"}
      </p>
      {/* `.cifra` es la monoespaciada del sistema: un código que alguien va a
          dictar en caja se lee mejor sin dígitos que bailan. */}
      <p className="reconocerte-codigo cifra">{cupon.codigo}</p>
      <p className="reconocerte-cupon-detalle">
        {descuento}% de descuento · válido hasta el {enLetras(cupon.vigente_hasta)}
      </p>
      <p className="reconocerte-cupon-nota">
        Es tu DNI. Menciónalo en caja en tu próxima compra — se usa una sola vez.
      </p>
    </section>
  );
}

/**
 * El formulario de la landing.
 *
 * Dos decisiones heredadas del resto del front:
 *
 * - **`onSubmit` y no `<form action={...}>`.** React 19 resetea el formulario
 *   cuando la acción va en el prop `action`, también cuando devolvió error:
 *   un DNI rechazado borraría los seis campos y el cliente abandonaría. Mismo
 *   candado que `app/login` y `components/formulario/`.
 * - **Campos no controlados** (`defaultValue` + `name`): lo que se teclea
 *   antes de que React hidrate vive en el DOM, y un campo controlado lo
 *   descartaría al arrancar.
 *
 * El nombre sí es estado: lo escribe RENIEC al salir del campo de DNI, y para
 * eso hay que poder pisarlo desde JavaScript. Queda editable a propósito — si
 * el proveedor no contesta, el cliente lo escribe y sigue (RN-PTS-004).
 */
export default function ReconocerteCliente({
  descuento,
  vigenciaDias,
}: {
  descuento: number;
  vigenciaDias: number;
}) {
  const [estado, despachar, pendiente] = useActionState(registrarAction, ESTADO_INICIAL);
  const [nombre, setNombre] = useState("");
  const [buscando, setBuscando] = useState(false);
  const formulario = useRef<HTMLFormElement>(null);

  const completarNombre = async (dni: string) => {
    if (!/^\d{8}$/.test(dni) || nombre.trim()) return;
    setBuscando(true);
    const { nombres, apellidos } = await buscarNombreAction(dni);
    setBuscando(false);
    const completo = `${nombres} ${apellidos}`.trim();
    // Vacío = el proveedor no contestó o no encontró el documento. No es un
    // error que mostrar: el campo queda como estaba y el cliente lo escribe.
    if (completo) setNombre(completo);
  };

  if (estado.cupon) {
    return <TarjetaCupon cupon={estado.cupon} descuento={descuento} />;
  }

  return (
    <form
      ref={formulario}
      className="publico-form"
      onSubmit={(e) => {
        e.preventDefault();
        const datos = new FormData(e.currentTarget);
        startTransition(() => despachar(datos));
      }}
    >
      <label className="publico-campo">
        <span>DNI</span>
        <input
          name="numero_documento"
          inputMode="numeric"
          autoComplete="off"
          maxLength={8}
          required
          onBlur={(e) => void completarNombre(e.currentTarget.value.trim())}
        />
        <small>Con tu DNI completamos tu nombre y es tu código de descuento.</small>
      </label>

      <label className="publico-campo">
        <span>Nombres y apellidos</span>
        <input
          name="nombre"
          autoComplete="name"
          required
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          placeholder={buscando ? "Buscando..." : ""}
        />
      </label>

      <label className="publico-campo">
        <span>Teléfono</span>
        <input name="telefono" type="tel" inputMode="tel" autoComplete="tel" required />
      </label>

      <label className="publico-campo">
        <span>Fecha de cumpleaños</span>
        <input name="fecha_nacimiento" type="date" autoComplete="bday" />
      </label>

      {/* El mismo componente del ERP: autocompletado de Google, pin
          arrastrable y los cinco ocultos que anclan la dirección al mapa
          (ADR-053). Sin clave configurada queda como un campo de texto. */}
      {/* `claseEtiqueta` viste el `<label>` y `claseCampo` el `<input>`: en
          este componente son dos props distintas, no una que envuelva a la
          otra como en los demás campos de arriba. */}
      <CampoDireccion
        nombre="direccion"
        etiqueta="Dirección"
        claseEtiqueta="publico-campo"
        claseCampo="publico-input"
      />

      <label className="publico-consentimiento">
        <input type="checkbox" name="acepta_terminos" required />
        <span>
          Acepto los{" "}
          <Link href="/reconocerte/terminos" target="_blank">
            términos y condiciones
          </Link>{" "}
          y que Inversiones Turísticas y Alimentarias Majambo EIRL y Grupo Majambo
          usen mis datos con fines comerciales.
        </span>
      </label>

      {estado.error ? (
        <p className="publico-error" role="alert">
          {estado.error}
        </p>
      ) : null}

      <button type="submit" className="publico-boton" disabled={pendiente}>
        {pendiente ? "Registrando..." : `Quiero mi ${descuento}% de descuento`}
      </button>

      <p className="publico-letra-chica">
        El cupón vale {vigenciaDias} días desde que lo recibes y se usa una sola vez.
      </p>
    </form>
  );
}
