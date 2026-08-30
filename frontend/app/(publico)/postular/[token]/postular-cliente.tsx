"use client";

import { startTransition, useActionState } from "react";

import { postularAction } from "./actions";
import { ESTADO_INICIAL } from "./estado";

/** Los canales del SOP de publicación de convocatoria. Es lo que después
 *  permite comparar canal vs. contratado final, así que son opciones y no un
 *  campo libre: «FB», «facebook» y «Face» no se agrupan solos. */
const CANALES = [
  "Un trabajador me contó",
  "Facebook",
  "Computrabajo o Indeed",
  "Cartel en el local",
  "Otro",
];

/** Meses que el ERP conserva la ficha del postulante
 *  (`RRHH_PLAZO_CONSERVACION_POSTULANTE_MESES`). Va en el texto del
 *  consentimiento: sin plazo, la autorización no es informada (Ley 29733). */
const MESES_CONSERVACION = 12;

/**
 * El formulario de postulación.
 *
 * Dos decisiones heredadas del resto del front:
 *
 * - **`onSubmit` y no `<form action={...}>`.** React 19 resetea el formulario
 *   cuando la acción va en el prop `action`, también cuando devolvió error:
 *   un teléfono rechazado borraría los seis campos y el candidato abandonaría.
 * - **Campos no controlados** (`name` sin `value`): lo que se teclea antes de
 *   que React hidrate vive en el DOM, y un campo controlado lo descartaría al
 *   arrancar.
 */
export default function PostularCliente({ token }: { token: string }) {
  const [estado, despachar, pendiente] = useActionState(postularAction, ESTADO_INICIAL);

  if (estado.puesto) {
    return (
      <section className="postular-gracias" aria-live="polite">
        <p className="postular-gracias-titulo">¡Listo! Recibimos tu postulación.</p>
        <p>
          Quedaste registrado para <strong>{estado.puesto}</strong>. Si tu perfil
          encaja te llamamos al número que dejaste.
        </p>
        <p className="publico-letra-chica">
          No hace falta que vuelvas a enviarla. Guardamos tus datos {MESES_CONSERVACION}{" "}
          meses y después se eliminan.
        </p>
      </section>
    );
  }

  return (
    <form
      className="publico-form"
      onSubmit={(e) => {
        e.preventDefault();
        const datos = new FormData(e.currentTarget);
        startTransition(() => despachar(datos));
      }}
    >
      {/* El token de la convocatoria: sale de la URL que el candidato abrió y
          es lo único que autoriza a escribir. Va oculto y no como argumento
          ligado porque el resto del formulario ya viaja como `FormData`. */}
      <input type="hidden" name="convocatoria" value={token} />

      <label className="publico-campo">
        <span>Nombres</span>
        <input name="nombres" autoComplete="given-name" maxLength={100} required />
      </label>

      <label className="publico-campo">
        <span>Apellidos</span>
        <input name="apellidos" autoComplete="family-name" maxLength={100} required />
      </label>

      <label className="publico-campo">
        <span>Teléfono</span>
        <input
          name="telefono"
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          maxLength={30}
          required
        />
        <small>Es por donde te vamos a llamar.</small>
      </label>

      <label className="publico-campo">
        <span>Correo (opcional)</span>
        <input name="email" type="email" autoComplete="email" maxLength={150} />
      </label>

      <label className="publico-campo">
        <span>¿Cómo te enteraste?</span>
        <select name="canal_origen" defaultValue="">
          <option value="">Prefiero no decirlo</option>
          {CANALES.map((canal) => (
            <option key={canal} value={canal}>
              {canal}
            </option>
          ))}
        </select>
      </label>

      <label className="publico-campo">
        <span>Cuéntanos de tu experiencia y tu disponibilidad</span>
        {/* 2000 es el techo que valida el servidor por respuesta
            (`_MAX_LARGO_RESPUESTA`): cortarlo acá evita un 422 después de
            escribir. */}
        <textarea name="experiencia" rows={4} maxLength={2000} />
        <small>Dónde trabajaste antes, qué turnos puedes cubrir.</small>
      </label>

      <label className="publico-consentimiento">
        <input type="checkbox" name="consentimiento_datos" required />
        <span>
          Autorizo a Inversiones Turísticas y Alimentarias Majambo EIRL a tratar mis
          datos para este proceso de selección y a conservarlos{" "}
          {MESES_CONSERVACION} meses. Puedo pedir acceder a ellos, corregirlos o
          eliminarlos escribiendo a <a href="mailto:hola@majambo.com.pe">hola@majambo.com.pe</a>.
        </span>
      </label>

      {estado.error ? (
        <p className="publico-error" role="alert">
          {estado.error}
        </p>
      ) : null}

      <button type="submit" className="publico-boton" disabled={pendiente}>
        {pendiente ? "Enviando..." : "Enviar mi postulación"}
      </button>
    </form>
  );
}
