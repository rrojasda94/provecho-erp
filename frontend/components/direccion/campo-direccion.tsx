"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { cargarMaps } from "@/lib/google-maps";

import {
  abrirBuscador,
  anclaDeTexto,
  direccionDePunto,
  type Buscador,
  type Sugerencia,
} from "./buscador-lugares";
import { useConfigMapas } from "./config-mapas";
import { ListaSugerencias } from "./lista-sugerencias";
import { useMapaPin } from "./usar-mapa";
import { useSugerencias } from "./usar-sugerencias";

import {
  coordenadasDe,
  estaAnclada,
  UBICACION_VACIA,
  type Ubicacion,
} from "./ubicacion";

export { UBICACION_VACIA, type Ubicacion };

/** Por defecto nadie escucha. Una función vacía y no un `?.`: el opcional
 * suma una rama por cada llamada y el componente ya roza el tope de
 * complejidad del lint. */
const NADIE_ESCUCHA = () => {};

function CamposOcultos({ ancla }: { ancla: Ubicacion }) {
  // Vacío y no `null`: un `FormData` no sabe expresar null, y la Server
  // Action convierte el vacío en null antes de mandarlo a la API.
  return (
    <>
      {(Object.keys(UBICACION_VACIA) as (keyof Ubicacion)[]).map((campo) => (
        <input key={campo} type="hidden" name={campo} value={ancla[campo] ?? ""} />
      ))}
    </>
  );
}

/** Los atributos ARIA del combobox, o ninguno. Función aparte y no un
 * ternario dentro de `CampoTexto`: sin buscador el campo es el `<input>` de
 * siempre —ni `role`, ni `aria-expanded`— y eso es justo lo que
 * `direccion.spec.ts` verifica sin clave de Google. */
function atributosCombobox(
  activo: boolean,
  props: { idLista: string; idActivo: string | undefined; expandido: boolean },
): React.ComponentProps<"input"> {
  if (!activo) return {};
  return {
    role: "combobox",
    "aria-autocomplete": "list",
    "aria-expanded": props.expandido,
    "aria-controls": props.idLista,
    "aria-activedescendant": props.idActivo,
  };
}

/** El campo de texto y sus valores por defecto.
 *
 * Vive aparte por el límite de complejidad del lint: cada valor por defecto
 * cuenta como una rama. `comboProps` no lleva default —siempre lo pasa
 * `CampoDireccion`— así que no suma a esa cuenta.
 */
function CampoTexto({
  campoRef,
  nombre = "direccion",
  etiqueta = "Dirección",
  requerido = false,
  claseCampo = "",
  claseEtiqueta = "flex flex-col gap-1 text-sm font-semibold",
  defaultValue = "",
  onInput,
  onKeyDown,
  onFocus,
  onBlur,
  comboProps,
}: {
  campoRef: React.RefObject<HTMLInputElement | null>;
  nombre?: string;
  etiqueta?: string;
  requerido?: boolean;
  claseCampo?: string;
  claseEtiqueta?: string;
  defaultValue?: string | null;
  onInput: (e: React.FormEvent<HTMLInputElement>) => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  onFocus: () => void;
  onBlur: () => void;
  comboProps: React.ComponentProps<"input">;
}) {
  return (
    <label className={claseEtiqueta}>
      {etiqueta}
      <input
        ref={campoRef}
        name={nombre}
        className={claseCampo}
        required={requerido}
        maxLength={255}
        defaultValue={defaultValue ?? ""}
        autoComplete="off"
        onInput={onInput}
        onKeyDown={onKeyDown}
        onFocus={onFocus}
        onBlur={onBlur}
        {...comboProps}
      />
    </label>
  );
}

/** El `??` vive fuera del componente: adentro cuenta para su complejidad. */
function inicial(u: Ubicacion | null | undefined): Ubicacion {
  return u ?? UBICACION_VACIA;
}

/** El mapa solo existe con SDK cargado, y solo se ve con el pin puesto.
 * Se monta siempre —oculto por CSS y no por no-renderizarse— para que el
 * `<div>` ya exista cuando el SDK cargue: la versión que lo montaba solo con
 * `conMapa` era el mismo huevo-y-gallina que tuvo el buscador. */
function Mapa({
  contenedor,
  visible,
}: {
  contenedor: React.RefObject<HTMLDivElement | null>;
  visible: boolean;
}) {
  return (
    <div
      ref={contenedor}
      aria-hidden
      className={`w-full overflow-hidden rounded-lg border border-border ${
        visible ? "h-44" : "hidden"
      }`}
    />
  );
}

function mensaje(aviso: string, anclada: boolean, conMapa: boolean): string {
  if (aviso) return aviso;
  if (anclada) return "Anclada en el mapa. Arrastra el pin si la puerta está a media cuadra.";
  if (conMapa) {
    return (
      "Escribe la dirección y elige una sugerencia para ponerle punto en el mapa; " +
      "si Google no la conoce, déjala escrita."
    );
  }
  return "Escribe la dirección. El mapa no está disponible.";
}

const AVISO_TEXTO_A_MANO = "Dirección escrita a mano: queda sin punto en el mapa.";
const AVISO_DEDUCIDO = "Punto deducido del texto: revísalo antes de guardar.";
const AVISO_PIN_MOVIDO = "Pin movido: revisa la dirección antes de guardar.";
const AVISO_SIN_GEOCODE = "No se pudo leer la dirección de ese punto.";

/**
 * Campo de dirección anclado a Google Maps (ADR-053, ADR-072).
 *
 * Una sola caja, no dos: el `<input>` de siempre busca sugerencias de Google
 * mientras se teclea (`buscador-lugares.abrirBuscador`) y las muestra en un
 * desplegable propio (`ListaSugerencias`). Elegir una escribe el texto,
 * guarda el ancla y centra el pin del mapa de abajo, con arrastre para
 * corregir la puerta exacta cuando Google la deja a media cuadra.
 *
 * ADR-053 tenía esto en dos cajas —el buscador de Google arriba, el campo de
 * texto abajo— y esa fue la causa del bug que ADR-072 corrige: se tecleaba
 * en la caja que no buscaba, así que nada quedaba anclado nunca. Lo que esa
 * decisión sí protegía, la salida de emergencia de texto libre, se conserva
 * intacta: **se puede escribir una dirección que Google no conoce.** En
 * Tarapoto hay calles así, y el alta no puede depender de que un tercero
 * conteste (mismo criterio que ADR-005 y ADR-041).
 *
 * **Editar el texto a mano suelta el pin.** Si el texto dijera una calle y
 * las coordenadas otra, el reparto iría al lugar equivocado y cobraría la
 * distancia equivocada. El backend aplica la misma regla por su cuenta
 * (`shared/ubicacion.py`): esto es la versión visible, no la que manda.
 *
 * **Una dirección guardada solo como texto se ancla sola al abrir la
 * ficha**, con un geocode directo, y solo si el resultado es inequívoco
 * (`lib/direcciones.esConfiable`) — anclar en silencio un punto dudoso sería
 * peor que no anclar, porque hay plata atada a él (ADR-054).
 *
 * Se monta dentro de los formularios NO controlados del ERP (`defaultValue` +
 * `name`, ver `dialogo-formulario`): el texto y los cinco ocultos son campos
 * del `<form>` que lo contiene y se envían solos.
 */
export function CampoDireccion({
  ubicacion,
  onCambio = NADIE_ESCUCHA,
  ...presentacion
}: {
  /** `name` del campo de texto. El de los ocultos es fijo. */
  nombre?: string;
  etiqueta?: string;
  requerido?: boolean;
  defaultValue?: string | null;
  ubicacion?: Ubicacion | null;
  /** Para los formularios que NO son `<form>` — el PDV lleva el pedido en
   * estado de React, no en campos del DOM. */
  onCambio?: (texto: string, ubicacion: Ubicacion) => void;
  /** El PDV tiene su propia paleta y sus propias clases (`pdv-campo`). */
  claseCampo?: string;
  claseEtiqueta?: string;
}) {
  // Del contexto y no de props: la clave la lee el servidor y el layout la
  // baja una sola vez (`components/direccion/config-mapas`).
  const { apiKey, mapId, pais } = useConfigMapas();
  const paisBuscado = pais || "pe";
  const [ancla, setAncla] = useState<Ubicacion>(inicial(ubicacion));
  const [conMapa, setConMapa] = useState(false);
  const [buscador, setBuscador] = useState<Buscador | null>(null);
  const [aviso, setAviso] = useState("");

  const inputRef = useRef<HTMLInputElement>(null);
  // Guarda que el anclaje automático del texto ya guardado corrió: una sola
  // vez por montaje, nunca en cada render.
  const anclaje = useRef(false);

  /** Escribe en el DOM y no en estado: el campo es no controlado. */
  const escribirTexto = useCallback((texto: string) => {
    if (inputRef.current) inputRef.current.value = texto;
  }, []);

  /** Pin soltado en otro punto: se pregunta qué dirección hay ahí. */
  const reubicar = useCallback(
    async (lat: number, lng: number) => {
      const maps = window.google?.maps;
      if (!maps) return;
      const hallado = await direccionDePunto(maps, lat, lng);
      if (!hallado) {
        // Mover el pin sin poder nombrar la dirección es peor que no
        // haberlo movido: el texto quedaría contando otra historia.
        setAviso(AVISO_SIN_GEOCODE);
        return;
      }
      escribirTexto(hallado.texto);
      setAncla(hallado.ancla);
      onCambio(hallado.texto, hallado.ancla);
      setAviso(AVISO_PIN_MOVIDO);
    },
    [escribirTexto, onCambio],
  );

  const { mapaRef, moverPin } = useMapaPin({ mapId, alSoltar: reubicar });

  const elegir = useCallback(
    async (s: Sugerencia) => {
      if (!buscador) return;
      const { texto, ancla: nueva } = await buscador.detalle(s);
      escribirTexto(texto);
      setAncla(nueva);
      onCambio(texto, nueva);
      setAviso("");
      const punto = coordenadasDe(nueva);
      if (punto) void moverPin(punto.lat, punto.lng);
    },
    [buscador, escribirTexto, moverPin, onCambio],
  );

  const sug = useSugerencias(buscador, elegir);

  // Monta el buscador de Google. Si el SDK no carga —sin clave, sin internet,
  // clave restringida a otro dominio— no pasa nada: queda el campo de texto,
  // que es todo lo que había antes de esta integración.
  useEffect(() => {
    let vivo = true;
    cargarMaps(apiKey)
      .then(async (maps) => {
        if (!vivo) return;
        setConMapa(true);
        const abierto = await abrirBuscador(maps, paisBuscado);
        if (vivo) setBuscador(abierto);
      })
      .catch(() => {
        // Silencio deliberado: no hay nada que el usuario pueda hacer y el
        // formulario funciona igual. El detalle queda en la consola del SDK.
      });
    return () => {
      vivo = false;
    };
  }, [apiKey, paisBuscado]);

  // Al aparecer el mapa: si la ficha ya venía anclada, centra el pin ahí. Si
  // no, y hay texto sin ancla, intenta deducirle un punto (ADR-072). Una
  // sola vez por montaje —`anclaje` lo garantiza— y nunca vuelve a correr
  // por lo que el propio usuario haga después.
  useEffect(() => {
    if (!conMapa || anclaje.current) return;
    anclaje.current = true;
    const maps = window.google?.maps;
    if (!maps) return;
    const punto = coordenadasDe(ancla);
    if (punto) {
      void moverPin(punto.lat, punto.lng);
      return;
    }
    const texto = inputRef.current?.value.trim();
    if (!texto) return;
    void anclaDeTexto(maps, texto, paisBuscado).then((deducida) => {
      if (!deducida) return;
      setAncla(deducida);
      onCambio(texto, deducida);
      setAviso(AVISO_DEDUCIDO);
      const p = coordenadasDe(deducida);
      if (p) void moverPin(p.lat, p.lng);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conMapa]);

  const anclada = estaAnclada(ancla);

  return (
    <div className="flex flex-col gap-1.5">
      <div className="relative">
        <CampoTexto
          {...presentacion}
          campoRef={inputRef}
          comboProps={atributosCombobox(buscador !== null, {
            idLista: sug.idLista,
            idActivo: sug.activo >= 0 ? sug.idOpcion(sug.activo) : undefined,
            expandido: sug.abierto,
          })}
          onFocus={sug.alEnfocar}
          onBlur={sug.alPerderFoco}
          onKeyDown={sug.alTeclado}
          onInput={(e) => {
            const valor = e.currentTarget.value;
            sug.alTeclear(valor);
            // Texto tecleado a mano: el pin viejo ya no es de esta dirección.
            onCambio(valor, UBICACION_VACIA);
            if (!anclada) return;
            setAncla(UBICACION_VACIA);
            setAviso(AVISO_TEXTO_A_MANO);
          }}
        />
        {sug.abierto && (
          <ListaSugerencias
            sugerencias={sug.lista}
            activo={sug.activo}
            idLista={sug.idLista}
            idOpcion={sug.idOpcion}
            onTomar={sug.tomar}
          />
        )}
      </div>

      <CamposOcultos ancla={ancla} />

      <Mapa contenedor={mapaRef} visible={anclada} />

      <p className="text-xs text-muted-foreground" role="status">
        {mensaje(aviso, anclada, conMapa)}
      </p>
    </div>
  );
}
