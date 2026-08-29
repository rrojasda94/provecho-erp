"use client";

import * as React from "react";
import { Combobox as ComboboxPrimitive } from "@base-ui/react/combobox";
import { CheckIcon, ChevronDownIcon, XIcon } from "lucide-react";

import { filtrarOpciones, type Opcion } from "@/lib/filtrar-opciones";
import { cn } from "@/lib/utils";

export type { Opcion };

/**
 * El desplegable con búsqueda: se escribe para filtrar en vez de bajar la
 * lista a mano.
 *
 * Reemplaza a `<select>` en toda lista que venga de la API. Los enumerados
 * fijos del código —estados, tipos, modalidades— siguen siendo `<select>`
 * nativos a propósito: ponerle un buscador a tres opciones es estorbo, no
 * ayuda.
 *
 * **Cómo entrega el valor.** Base UI dibuja un `<input type="hidden">` por
 * cada selección con el `name` recibido, así que las Server Actions lo leen
 * con `formData.get(name)` —o `getAll(name)` en `ComboboxMultiple`— sin
 * cambiar nada del lado del servidor. También acepta `value`/`alCambiar` para
 * las pantallas que mutan con `pedir()` en vez de Server Actions (Catálogo,
 * PDV, KDS).
 *
 * El filtrado ocurre **en el cliente**, sobre las opciones ya cargadas. Para
 * las listas que no entran completas en una página —hoy solo el catálogo de
 * artículos— la pantalla busca contra el servidor y le pasa acá el resultado.
 */

type PropsComunes = {
  opciones: readonly Opcion[];
  /** Nombre accesible del campo. Hace falta aunque haya un `<label>` alrededor:
   * el nombre se calcula con **todo** el texto de la etiqueta, y en la variante
   * múltiple ahí dentro viven también las fichas de lo ya elegido — sin esto, un
   * lector de pantalla anuncia "Productos del combo Pizza Quitar Pizza". */
  etiqueta?: string;
  /** Texto del campo vacío. En un filtro suele ser "Todas". */
  marcador?: string;
  id?: string;
  name?: string;
  requerido?: boolean;
  deshabilitado?: boolean;
  className?: string;
  /** Lo que se dice cuando nada coincide con lo tecleado. */
  sinResultados?: string;
};

const CLASE_CAMPO =
  "w-full rounded-[var(--radius)] border border-input bg-card px-[0.6rem] py-[0.45rem] " +
  "text-sm text-foreground outline-none transition-colors placeholder:text-gray " +
  "focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/20 " +
  "disabled:cursor-not-allowed disabled:bg-muted";

/**
 * Ata el campo a su sitio en el DOM y devuelve las dos cosas que dependen de
 * dónde cayó: dentro de qué elemento se dibuja el desplegable, y cuándo hay
 * que vaciarlo.
 *
 * **El portal.** `DialogoFormulario` usa un `<dialog>` **nativo**, que el
 * navegador sube al top layer: un portal colgado del `<body>` quedaría por
 * debajo y, peor, inerte —el modal apaga los eventos de todo lo que no esté
 * dentro de él—. Por eso se ancla al `<dialog>` más cercano cuando existe, y
 * al `<body>` cuando el campo vive en una barra de filtros.
 *
 * **El `reset`.** `DialogoFormulario` deja los hijos montados entre aperturas
 * y llama `form.reset()` al cerrar. El reset nativo vacía los `<input>` del
 * navegador pero no toca el estado de React, así que sin escucharlo el
 * diálogo se reabre con lo elegido la vez anterior —el mismo bug que
 * `PersonaPicker` ya había tenido que resolver.
 *
 * Las dos cosas se miran en el DOM en vez de pedirse por prop para que migrar
 * un `<select>` sea cambiar la etiqueta y nada más: ninguno de los 62 sabe si
 * está dentro de un diálogo ni de qué formulario cuelga.
 */
function useAncla(alReiniciar: () => void) {
  const [nodo, setNodo] = React.useState<HTMLDivElement | null>(null);
  const ancla = React.useCallback((n: HTMLDivElement | null) => setNodo(n), []);
  // `undefined` y no `null`: para el `Portal` de Base UI, `null` significa
  // "todavía no sé el contenedor, no montés nada" y lo deja así para
  // siempre —nunca cae al `<body>` por defecto—. `undefined` es lo que
  // dispara ese valor por defecto. Sin esta distinción, cualquier campo
  // fuera de un `<dialog>` (los filtros de una tabla, el selector de
  // sucursal del PDV) abría el desplegable pero nunca dibujaba el popup:
  // "expanded" en el DOM y ninguna opción en ningún lado.
  const contenedor = React.useMemo(
    () => (nodo?.closest("dialog") as HTMLElement | null) ?? undefined,
    [nodo],
  );

  // El handler se lee de un ref para no re-suscribirse en cada render: el que
  // reinicia depende de `defaultValue`, que suele ser un literal nuevo cada vez.
  const reiniciar = React.useRef(alReiniciar);
  React.useEffect(() => {
    reiniciar.current = alReiniciar;
  });
  React.useEffect(() => {
    const form = nodo?.closest("form");
    if (!form) return;
    const alResetear = () => reiniciar.current();
    form.addEventListener("reset", alResetear);
    return () => form.removeEventListener("reset", alResetear);
  }, [nodo]);

  return { ancla, contenedor };
}

/** El popup, idéntico en las dos variantes. */
function Desplegable({
  contenedor,
  filtradas,
  sinResultados,
}: {
  contenedor: HTMLElement | undefined;
  filtradas: readonly Opcion[];
  sinResultados: string;
}) {
  return (
    <ComboboxPrimitive.Portal container={contenedor}>
      <ComboboxPrimitive.Positioner sideOffset={4} className="isolate z-50">
        <ComboboxPrimitive.Popup
          data-slot="combobox-popup"
          className={cn(
            "max-h-[min(18rem,var(--available-height))] w-[var(--anchor-width)] min-w-40",
            "origin-[var(--transform-origin)] overflow-y-auto overflow-x-hidden rounded-lg",
            "bg-popover p-1 text-sm text-popover-foreground shadow-md ring-1 ring-foreground/10",
            "data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95",
            "data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",
          )}
        >
          <ComboboxPrimitive.Empty className="px-2 py-3 text-center text-gray">
            {sinResultados}
          </ComboboxPrimitive.Empty>
          <ComboboxPrimitive.List>
            {filtradas.map((opcion) => (
              <ComboboxPrimitive.Item
                key={opcion.valor}
                value={opcion.valor}
                data-slot="combobox-item"
                className={cn(
                  "relative flex cursor-default items-start gap-2 rounded-md py-1.5 pl-2 pr-8",
                  "outline-hidden select-none data-highlighted:bg-muted",
                  "data-disabled:pointer-events-none data-disabled:opacity-50",
                )}
              >
                <span className="flex min-w-0 flex-col">
                  <span className="truncate">{opcion.etiqueta}</span>
                  {opcion.pista && (
                    <span className="truncate text-xs text-gray">{opcion.pista}</span>
                  )}
                </span>
                <ComboboxPrimitive.ItemIndicator className="absolute right-2 top-1.5">
                  <CheckIcon className="size-4" />
                </ComboboxPrimitive.ItemIndicator>
              </ComboboxPrimitive.Item>
            ))}
          </ComboboxPrimitive.List>
        </ComboboxPrimitive.Popup>
      </ComboboxPrimitive.Positioner>
    </ComboboxPrimitive.Portal>
  );
}

function indice(opciones: readonly Opcion[]) {
  return new Map(opciones.map((o) => [o.valor, o.etiqueta]));
}

/** Índice `valor → etiqueta`: el input muestra el nombre, no el UUID. */
function useEtiquetas(opciones: readonly Opcion[]) {
  return React.useMemo(() => {
    const mapa = new Map<string, string>();
    for (const o of opciones) mapa.set(o.valor, o.etiqueta);
    return (valor: string) => mapa.get(valor) ?? "";
  }, [opciones]);
}

export type ComboboxProps = PropsComunes & {
  /** Sin `value` el campo es no controlado y viaja por `FormData`. */
  value?: string | null;
  defaultValue?: string | null;
  alCambiar?: (valor: string | null) => void;
};

/** Una sola opción. El reemplazo directo de un `<select>` de toda la vida. */
export function Combobox({
  opciones,
  etiqueta,
  marcador = "Buscar...",
  sinResultados = "Sin resultados.",
  id,
  name,
  requerido,
  deshabilitado,
  className,
  value,
  defaultValue,
  alCambiar,
}: ComboboxProps) {
  const [consulta, setConsulta] = React.useState("");
  // Controlado por dentro aunque el llamador no pase `value`: es lo que
  // permite devolverlo a su estado inicial cuando el formulario se reinicia.
  const [propio, setPropio] = React.useState<string | null>(defaultValue ?? null);
  const seleccion = value === undefined ? propio : value;
  const { ancla, contenedor } = useAncla(() => setPropio(defaultValue ?? null));
  const etiquetaDe = useEtiquetas(opciones);

  const filtradas = React.useMemo(
    () => filtrarOpciones(opciones, consulta),
    [opciones, consulta],
  );
  const valores = React.useMemo(() => opciones.map((o) => o.valor), [opciones]);
  const valoresFiltrados = React.useMemo(() => filtradas.map((o) => o.valor), [filtradas]);

  return (
    <ComboboxPrimitive.Root
      items={valores}
      filteredItems={valoresFiltrados}
      itemToStringLabel={etiquetaDe}
      onInputValueChange={setConsulta}
      name={name}
      required={requerido}
      disabled={deshabilitado}
      value={seleccion}
      onValueChange={(nuevo) => {
        setPropio(nuevo);
        alCambiar?.(nuevo);
      }}
    >
      <div ref={ancla} className="relative w-full" data-slot="combobox">
        <ComboboxPrimitive.Input
          id={id}
          aria-label={etiqueta}
          placeholder={marcador}
          data-slot="combobox-input"
          className={cn(CLASE_CAMPO, "pr-14", className)}
        />
        <div className="absolute inset-y-0 right-0 flex items-center">
          {/* Volver a "sin elegir". El `<select>` que esto reemplaza traía una
              opción vacía —"Todas"— y sin forma de vaciar el campo, un filtro
              se queda clavado en la primera sucursal que se toque. Se esconde
              solo cuando no hay nada que borrar. */}
          {!requerido && (
            <ComboboxPrimitive.Clear
              aria-label="Limpiar"
              className="flex items-center px-1 text-gray hover:text-foreground"
            >
              <XIcon className="size-4" />
            </ComboboxPrimitive.Clear>
          )}
          <ComboboxPrimitive.Trigger
            aria-label="Mostrar opciones"
            disabled={deshabilitado}
            className="flex items-center px-2 text-gray"
          >
            <ChevronDownIcon className="size-4" />
          </ComboboxPrimitive.Trigger>
        </div>
      </div>
      <Desplegable
        contenedor={contenedor}
        filtradas={filtradas}
        sinResultados={sinResultados}
      />
    </ComboboxPrimitive.Root>
  );
}

export type ComboboxMultipleProps = PropsComunes & {
  value?: readonly string[];
  defaultValue?: readonly string[];
  alCambiar?: (valores: string[]) => void;
};

/**
 * Varias opciones a la vez, cada una como una etiqueta que se quita con su ✕.
 *
 * Manda un `<input type="hidden">` repetido con el mismo `name`, que es como
 * ya viajan las líneas de una orden de compra: del lado del servidor se lee
 * con `formData.getAll(name)`.
 */
export function ComboboxMultiple({
  opciones,
  etiqueta,
  marcador = "Buscar...",
  sinResultados = "Sin resultados.",
  id,
  name,
  requerido,
  deshabilitado,
  className,
  value,
  defaultValue,
  alCambiar,
}: ComboboxMultipleProps) {
  const [consulta, setConsulta] = React.useState("");
  const [propios, setPropios] = React.useState<string[]>([...(defaultValue ?? [])]);
  const seleccion = value === undefined ? propios : [...value];
  const { ancla, contenedor } = useAncla(() => setPropios([...(defaultValue ?? [])]));
  const etiquetaDe = useEtiquetas(opciones);

  const filtradas = React.useMemo(
    () => filtrarOpciones(opciones, consulta),
    [opciones, consulta],
  );
  const valores = React.useMemo(() => opciones.map((o) => o.valor), [opciones]);
  const valoresFiltrados = React.useMemo(() => filtradas.map((o) => o.valor), [filtradas]);

  return (
    <ComboboxPrimitive.Root
      multiple
      items={valores}
      filteredItems={valoresFiltrados}
      itemToStringLabel={etiquetaDe}
      onInputValueChange={setConsulta}
      name={name}
      required={requerido}
      disabled={deshabilitado}
      value={seleccion}
      onValueChange={(nuevos) => {
        setPropios(nuevos);
        alCambiar?.(nuevos);
      }}
    >
      <div ref={ancla} className="w-full" data-slot="combobox">
        <ComboboxPrimitive.Chips
          data-slot="combobox-chips"
          className={cn(
            CLASE_CAMPO,
            "flex flex-wrap items-center gap-1 focus-within:border-ring",
            "focus-within:ring-3 focus-within:ring-ring/20",
            className,
          )}
        >
          <ComboboxPrimitive.Value>
            {(seleccionados: string[]) =>
              seleccionados.map((valor) => (
                <ComboboxPrimitive.Chip
                  key={valor}
                  data-slot="combobox-chip"
                  className={cn(
                    "flex items-center gap-1 rounded-md bg-muted py-0.5 pl-2 pr-1",
                    "text-xs font-medium text-foreground",
                  )}
                >
                  {etiquetaDe(valor)}
                  <ComboboxPrimitive.ChipRemove
                    aria-label={`Quitar ${etiquetaDe(valor)}`}
                    className="rounded p-0.5 text-gray hover:text-foreground"
                  >
                    <XIcon className="size-3" />
                  </ComboboxPrimitive.ChipRemove>
                </ComboboxPrimitive.Chip>
              ))
            }
          </ComboboxPrimitive.Value>
          <ComboboxPrimitive.Input
            id={id}
            aria-label={etiqueta}
            placeholder={marcador}
            data-slot="combobox-input"
            className="min-w-24 flex-1 bg-transparent text-sm outline-none"
          />
        </ComboboxPrimitive.Chips>
      </div>
      <Desplegable
        contenedor={contenedor}
        filtradas={filtradas}
        sinResultados={sinResultados}
      />
    </ComboboxPrimitive.Root>
  );
}

export type ComboboxRemotoProps = Omit<PropsComunes, "opciones"> & {
  /** Qué se ofrece cuando lo tecleado ya da para buscar. */
  buscar: (consulta: string) => Promise<Opcion[]>;
  /** Lo que se muestra antes de teclear, y el valor ya elegido al editar: sin
   * esto un campo con valor guardado no sabría con qué nombre dibujarlo. */
  iniciales?: readonly Opcion[];
  value?: string | null;
  defaultValue?: string | null;
  alCambiar?: (valor: string | null) => void;
};

const LARGO_MINIMO = 2;
const RETRASO_MS = 300;

/**
 * Como `Combobox`, pero preguntándole al servidor en vez de filtrar lo ya
 * recibido.
 *
 * Es para las listas que **no entran** en una página: hoy solo el catálogo de
 * artículos, que son miles contra un techo de 200 filas por petición. Filtrar
 * en el cliente ahí no es lento, es incorrecto —lo que no se cargó no aparece
 * y nada lo dice—, así que la búsqueda baja a la base (`?q=`).
 *
 * Para todo lo demás va `Combobox`: un viaje al servidor por tecleo para
 * filtrar treinta sucursales es latencia a cambio de nada.
 */
export function ComboboxRemoto({
  buscar,
  iniciales = [],
  etiqueta,
  marcador = "Escribe para buscar...",
  sinResultados = "Sin resultados.",
  id,
  name,
  requerido,
  deshabilitado,
  className,
  value,
  defaultValue,
  alCambiar,
}: ComboboxRemotoProps) {
  const [opciones, setOpciones] = React.useState<readonly Opcion[]>(iniciales);
  const [buscando, setBuscando] = React.useState(false);
  const [propio, setPropio] = React.useState<string | null>(defaultValue ?? null);
  const seleccion = value === undefined ? propio : value;
  const temporizador = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const { ancla, contenedor } = useAncla(() => {
    setPropio(defaultValue ?? null);
    setOpciones(iniciales);
  });

  React.useEffect(() => () => clearTimeout(temporizador.current), []);

  // Lo ya visto se recuerda: tras elegir "Harina" y buscar otra cosa, el campo
  // tiene que seguir sabiendo cómo se llamaba lo que hay elegido, aunque esa
  // opción ya no esté entre los resultados que se están mostrando.
  const [conocidas, setConocidas] = React.useState(() => indice(iniciales));
  const etiquetaDe = React.useCallback(
    (valor: string) => conocidas.get(valor) ?? "",
    [conocidas],
  );

  const mostrar = (nuevas: readonly Opcion[]) => {
    setOpciones(nuevas);
    setConocidas((previas) => {
      const mapa = new Map(previas);
      for (const o of nuevas) mapa.set(o.valor, o.etiqueta);
      return mapa;
    });
  };

  const alTeclear = (consulta: string) => {
    clearTimeout(temporizador.current);
    const limpio = consulta.trim();
    if (limpio.length < LARGO_MINIMO) {
      setBuscando(false);
      setOpciones(iniciales);
      return;
    }
    setBuscando(true);
    temporizador.current = setTimeout(async () => {
      mostrar(await buscar(limpio));
      setBuscando(false);
    }, RETRASO_MS);
  };

  const valores = React.useMemo(() => opciones.map((o) => o.valor), [opciones]);

  return (
    <ComboboxPrimitive.Root
      items={valores}
      filteredItems={valores}
      filter={null}
      itemToStringLabel={etiquetaDe}
      onInputValueChange={alTeclear}
      name={name}
      required={requerido}
      disabled={deshabilitado}
      value={seleccion}
      onValueChange={(nuevo) => {
        setPropio(nuevo);
        alCambiar?.(nuevo);
      }}
    >
      <div ref={ancla} className="relative w-full" data-slot="combobox">
        <ComboboxPrimitive.Input
          id={id}
          aria-label={etiqueta}
          placeholder={marcador}
          data-slot="combobox-input"
          className={cn(CLASE_CAMPO, "pr-14", className)}
        />
        <div className="absolute inset-y-0 right-0 flex items-center">
          {!requerido && (
            <ComboboxPrimitive.Clear
              aria-label="Limpiar"
              className="flex items-center px-1 text-gray hover:text-foreground"
            >
              <XIcon className="size-4" />
            </ComboboxPrimitive.Clear>
          )}
          <ComboboxPrimitive.Trigger
            aria-label="Mostrar opciones"
            disabled={deshabilitado}
            className="flex items-center px-2 text-gray"
          >
            <ChevronDownIcon className="size-4" />
          </ComboboxPrimitive.Trigger>
        </div>
      </div>
      <Desplegable
        contenedor={contenedor}
        filtradas={opciones}
        sinResultados={buscando ? "Buscando..." : sinResultados}
      />
    </ComboboxPrimitive.Root>
  );
}
