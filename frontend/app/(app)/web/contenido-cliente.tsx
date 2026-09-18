"use client";

import { useActionState } from "react";

import { ESTADO_INICIAL } from "@/lib/errores";

import { guardarContenidoAction } from "./actions";

export type Contenido = {
  hero?: {
    titulo?: string;
    subtitulo?: string;
    cta_texto?: string;
    cta_url?: string;
    imagen_url?: string;
  };
  nosotros?: { titulo?: string; parrafos?: string[] };
  contacto?: {
    whatsapp?: string;
    email?: string;
    instagram?: string;
    facebook?: string;
    tiktok?: string;
  };
  trabaja?: { titulo?: string; cuerpo?: string };
  pie?: { texto?: string };
  seo?: { titulo?: string; descripcion?: string };
};

function Seccion({
  titulo,
  ayuda,
  clave,
  marcaId,
  children,
}: {
  titulo: string;
  ayuda?: string;
  clave: string;
  marcaId: string;
  children: React.ReactNode;
}) {
  const [estado, formAction, pendiente] = useActionState(guardarContenidoAction, ESTADO_INICIAL);
  return (
    <form
      action={formAction}
      className="flex flex-col gap-2 rounded-lg border border-border bg-white p-4"
    >
      <input type="hidden" name="marca_id" value={marcaId} />
      <input type="hidden" name="clave" value={clave} />
      <h2 className="font-heading text-base italic uppercase text-dark">{titulo}</h2>
      {ayuda && <p className="text-xs text-gray">{ayuda}</p>}
      {children}
      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={pendiente}
          className="self-start rounded bg-primary px-4 py-1.5 text-sm font-bold text-white hover:bg-primary/90 disabled:opacity-60"
        >
          {pendiente ? "Guardando..." : "Guardar"}
        </button>
        {estado.error && <span className="text-xs text-secondary">{estado.error}</span>}
        {estado.ok && <span className="text-xs text-accent">Guardado.</span>}
      </div>
    </form>
  );
}

const CAMPO = "flex flex-col gap-1 text-sm font-semibold";

// Cada `Campos*` toma su propia sección (nunca ausente: `page.tsx` la
// completa con `{}` si la marca no la guardó todavía) y aísla sus lecturas
// opcionales del resto — juntarlas todas en `ContenidoCliente` disparaba la
// complejidad ciclomática del linter (cada `?.`/`??` cuenta como rama).

function CamposHero({ hero }: { hero: NonNullable<Contenido["hero"]> }) {
  return (
    <>
      <label className={CAMPO}>
        Título
        <input name="titulo" required maxLength={150} defaultValue={hero.titulo ?? ""} />
      </label>
      <label className={CAMPO}>
        Bajada
        <textarea name="subtitulo" rows={2} maxLength={300} defaultValue={hero.subtitulo ?? ""} />
      </label>
      <div className="flex gap-2">
        <label className={CAMPO + " flex-1"}>
          Texto del botón
          <input name="cta_texto" maxLength={50} defaultValue={hero.cta_texto ?? ""} />
        </label>
        <label className={CAMPO + " flex-1"}>
          Enlace del botón
          <input
            name="cta_url"
            maxLength={300}
            placeholder="/carta"
            defaultValue={hero.cta_url ?? ""}
          />
        </label>
      </div>
    </>
  );
}

function CamposNosotros({ nosotros }: { nosotros: NonNullable<Contenido["nosotros"]> }) {
  return (
    <>
      <label className={CAMPO}>
        Título
        <input name="titulo" required maxLength={150} defaultValue={nosotros.titulo ?? ""} />
      </label>
      <label className={CAMPO}>
        Historia
        <textarea name="parrafos" rows={6} defaultValue={(nosotros.parrafos ?? []).join("\n")} />
      </label>
    </>
  );
}

function CamposContacto({ contacto }: { contacto: NonNullable<Contenido["contacto"]> }) {
  return (
    <div className="grid grid-cols-2 gap-2">
      <label className={CAMPO}>
        WhatsApp
        <input name="whatsapp" maxLength={20} defaultValue={contacto.whatsapp ?? ""} />
      </label>
      <label className={CAMPO}>
        Email
        <input name="email" type="email" maxLength={150} defaultValue={contacto.email ?? ""} />
      </label>
      <label className={CAMPO}>
        Instagram
        <input name="instagram" maxLength={150} defaultValue={contacto.instagram ?? ""} />
      </label>
      <label className={CAMPO}>
        Facebook
        <input name="facebook" maxLength={150} defaultValue={contacto.facebook ?? ""} />
      </label>
      <label className={CAMPO}>
        TikTok
        <input name="tiktok" maxLength={150} defaultValue={contacto.tiktok ?? ""} />
      </label>
    </div>
  );
}

function CamposTrabaja({ trabaja }: { trabaja: NonNullable<Contenido["trabaja"]> }) {
  return (
    <>
      <label className={CAMPO}>
        Título
        <input name="titulo" required maxLength={150} defaultValue={trabaja.titulo ?? ""} />
      </label>
      <label className={CAMPO}>
        Texto
        <textarea
          name="cuerpo"
          required
          rows={3}
          maxLength={2000}
          defaultValue={trabaja.cuerpo ?? ""}
        />
      </label>
    </>
  );
}

function CamposPie({ pie }: { pie: NonNullable<Contenido["pie"]> }) {
  return (
    <label className={CAMPO}>
      Texto
      <textarea name="texto" required rows={2} maxLength={500} defaultValue={pie.texto ?? ""} />
    </label>
  );
}

function CamposSeo({ seo }: { seo: NonNullable<Contenido["seo"]> }) {
  return (
    <>
      <label className={CAMPO}>
        Título de la página
        <input name="titulo" required maxLength={70} defaultValue={seo.titulo ?? ""} />
      </label>
      <label className={CAMPO}>
        Descripción
        <textarea
          name="descripcion"
          required
          rows={2}
          maxLength={200}
          defaultValue={seo.descripcion ?? ""}
        />
      </label>
    </>
  );
}

export function ContenidoCliente({
  marcaId,
  nombreMarca,
  contenido,
}: {
  marcaId: string;
  nombreMarca: string;
  contenido: Contenido;
}) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-heading text-xl italic uppercase text-dark">Sitio web</h1>
        <p className="text-sm text-gray">
          Textos del sitio público de <strong>{nombreMarca}</strong>{" "}
          (charlies.majambo.com.pe). Los cambios se ven en el sitio hasta un
          minuto después de guardar.
        </p>
      </div>

      <Seccion titulo="Portada (hero)" clave="hero" marcaId={marcaId}>
        <CamposHero hero={contenido.hero ?? {}} />
      </Seccion>

      <Seccion titulo="Nosotros" ayuda="Un párrafo por línea." clave="nosotros" marcaId={marcaId}>
        <CamposNosotros nosotros={contenido.nosotros ?? {}} />
      </Seccion>

      <Seccion titulo="Contacto y redes" clave="contacto" marcaId={marcaId}>
        <CamposContacto contacto={contenido.contacto ?? {}} />
      </Seccion>

      <Seccion titulo="Trabaja con nosotros" clave="trabaja" marcaId={marcaId}>
        <CamposTrabaja trabaja={contenido.trabaja ?? {}} />
      </Seccion>

      <Seccion titulo="Pie de página" clave="pie" marcaId={marcaId}>
        <CamposPie pie={contenido.pie ?? {}} />
      </Seccion>

      <Seccion
        titulo="SEO"
        ayuda="Lo que Google muestra en el resultado de búsqueda."
        clave="seo"
        marcaId={marcaId}
      >
        <CamposSeo seo={contenido.seo ?? {}} />
      </Seccion>
    </div>
  );
}
