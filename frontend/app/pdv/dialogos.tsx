"use client";

import { useEffect, useRef, useState } from "react";

import {
  esAtribucion,
  esCustodia,
  soles,
  type ClienteBuscado,
  type CustodiaDestino,
  type DescuadreAtribucion,
  type ExtraDeCarta,
  type ItemDeCarta,
  type MedioPago,
  type MesaEnMapa,
  type PosTarjeta,
  type PosVerificado,
  type VarianteDeCarta,
} from "@/lib/pdv";

import type { Borrador, LineaBorrador } from "./tipos";

/** Envoltorio común: `<dialog>` nativo, que ya trae foco atrapado, cierre
 * con Escape y backdrop sin una línea de JS.
 *
 * `bloqueante` quita esa salida rápida: la usa la apertura de caja, donde
 * Escape no puede ser una forma de vender sin caja abierta. El navegador
 * cierra el `<dialog>` con el Escape aunque se cancele el evento `cancel`
 * — sin el `showModal()` de respaldo en el `onCancel`, quedaría cerrado en
 * el DOM mientras React sigue creyendo que `abierto` es `true`. */
export function Dialogo({
  titulo,
  abierto,
  onCerrar,
  ancho,
  bloqueante,
  children,
}: {
  titulo: string;
  abierto: boolean;
  onCerrar: () => void;
  ancho?: "ancho";
  bloqueante?: boolean;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (abierto && !d.open) d.showModal();
    if (!abierto && d.open) d.close();
  }, [abierto]);

  return (
    <dialog
      ref={ref}
      className={`pdv-dialogo ${ancho ?? ""}`}
      onClose={onCerrar}
      onCancel={(e) => {
        if (bloqueante) {
          e.preventDefault();
          ref.current?.showModal();
        }
      }}
    >
      <header>
        <h3>{titulo}</h3>
        {!bloqueante && (
          <button type="button" onClick={onCerrar} aria-label="Cerrar">
            ×
          </button>
        )}
      </header>
      <div className="pdv-dialogo-cuerpo">{children}</div>
    </dialog>
  );
}

const BILLETES = [200, 100, 50, 20, 10];
const MONEDAS = [5, 2, 1, 0.5, 0.2, 0.1];

/** Apertura: se cuenta el cajón por denominación (RN-POS-003) y el
 * encargado que entrega el efectivo se identifica con su PIN.
 *
 * Las dos cosas son la misma idea: la caja arranca con un traspaso de
 * custodia entre dos personas (RN-MDP-002). Contar pieza por pieza es lo
 * que hace que el cierre signifique algo, y firmar con PIN es lo que hace
 * que un faltante tenga a quién preguntarle. */
export function DialogoApertura({
  abierto,
  pos,
  onAbrir,
  ocupado,
}: {
  abierto: boolean;
  pos: PosTarjeta[];
  onAbrir: (datos: {
    montoDeclarado: number;
    detalle: Record<string, number>;
    posVerificados: { pos_tarjeta_id: string; operativo: boolean; observacion?: string }[];
    encargado: { username: string; pin: string };
  }) => void;
  ocupado: boolean;
}) {
  const [conteo, setConteo] = useState<Record<string, number>>({});
  const [declarado, setDeclarado] = useState("");
  const [averiados, setAveriados] = useState<Record<string, string>>({});
  const [usuario, setUsuario] = useState("");
  const [pin, setPin] = useState("");
  const total = Object.entries(conteo).reduce(
    (a, [v, n]) => a + Number(v) * (n || 0),
    0,
  );
  // Lo contado menos lo que el encargado dice entregar. No bloquea abrir
  // (RN-POS-011): se muestra para que los dos lo vean antes de firmar, y el
  // servidor lo recalcula igual — acá es información, no el dato que manda.
  const diferencia = total - (Number(declarado) || 0);

  return (
    <Dialogo
      titulo="Apertura de caja"
      abierto={abierto}
      onCerrar={() => {}}
      bloqueante
    >
      <p className="pdv-nota">
        Cuenta el efectivo del cajón y registra cuántas piezas hay de cada
        denominación.
      </p>
      <ConteoDenominaciones conteo={conteo} onCambiar={setConteo} />

      <p className="pdv-etiqueta">El encargado declara entregar</p>
      <input
        className="pdv-campo"
        type="number"
        min={0}
        step="0.10"
        inputMode="decimal"
        placeholder="0.00"
        data-testid="apertura-declarado"
        value={declarado}
        onChange={(e) => setDeclarado(e.target.value)}
      />
      {declarado !== "" && diferencia !== 0 && (
        <p className="pdv-nota">
          Lo contado difiere en {soles(diferencia)} de lo declarado. Queda
          registrado y la caja abre igual.
        </p>
      )}

      {pos.length > 0 && (
        <>
          <p className="pdv-etiqueta">Terminales de tarjeta</p>
          <p className="pdv-nota">
            Marca el que no esté funcionando. Un POS averiado no impide abrir:
            queda reportado para que contabilidad mande el de emergencia.
          </p>
          {pos.map((p) => {
            const averiado = p.id in averiados;
            return (
              <div key={p.id}>
                <label className="pdv-check">
                  <input
                    type="checkbox"
                    checked={averiado}
                    onChange={(e) =>
                      setAveriados((previos) => {
                        const siguiente = { ...previos };
                        if (e.target.checked) siguiente[p.id] = "";
                        else delete siguiente[p.id];
                        return siguiente;
                      })
                    }
                  />
                  <span>
                    {p.serie}
                    {p.operador ? ` · ${p.operador}` : ""}
                    {p.es_emergencia ? " · emergencia" : ""} — averiado
                  </span>
                </label>
                {averiado && (
                  <input
                    className="pdv-campo"
                    placeholder="Qué le pasa (opcional)"
                    value={averiados[p.id]}
                    onChange={(e) =>
                      setAveriados((previos) => ({ ...previos, [p.id]: e.target.value }))
                    }
                  />
                )}
              </div>
            );
          })}
        </>
      )}

      <p className="pdv-etiqueta">Entrega el encargado</p>
      <div className="pdv-dos">
        <input
          className="pdv-campo"
          placeholder="Usuario del encargado"
          autoComplete="off"
          data-testid="apertura-usuario"
          value={usuario}
          onChange={(e) => setUsuario(e.target.value)}
        />
        <input
          className="pdv-campo"
          type="password"
          inputMode="numeric"
          placeholder="PIN"
          autoComplete="off"
          data-testid="apertura-pin"
          value={pin}
          onChange={(e) => setPin(e.target.value)}
        />
      </div>
      <p className="pdv-nota">
        El efectivo se entrega de una persona a otra: quien lo entrega firma
        con su PIN para que un faltante tenga a quién preguntarle.
      </p>

      <footer className="pdv-dialogo-pie">
        <div>
          <p className="pdv-etiqueta">Monto de apertura</p>
          <strong className="pdv-monto-grande">{soles(total)}</strong>
        </div>
        <button
          type="button"
          className="pdv-boton-pri"
          disabled={ocupado || !usuario.trim() || !pin.trim() || declarado === ""}
          onClick={() =>
            onAbrir({
              montoDeclarado: Number(declarado) || 0,
              detalle: conteo,
              posVerificados: pos.map((p) => ({
                pos_tarjeta_id: p.id,
                operativo: !(p.id in averiados),
                observacion: averiados[p.id]?.trim() || undefined,
              })),
              encargado: { username: usuario.trim(), pin },
            })
          }
        >
          Abrir caja
        </button>
      </footer>
    </Dialogo>
  );
}

/** El conteo pieza por pieza se pide igual al abrir y al cerrar la caja: en
 * los dos casos es lo que hace que el arqueo signifique algo (RN-POS-003). */
function ConteoDenominaciones({
  conteo,
  onCambiar,
}: {
  conteo: Record<string, number>;
  onCambiar: (c: Record<string, number>) => void;
}) {
  return (
    <>
      {[
        ["Billetes", BILLETES],
        ["Monedas", MONEDAS],
      ].map(([titulo, valores]) => (
        <div key={titulo as string}>
          <p className="pdv-etiqueta">{titulo as string}</p>
          <div className="pdv-denoms">
            {(valores as number[]).map((v) => (
              <label key={v} className="pdv-denom">
                <span>{v >= 1 ? `S/ ${v}` : `${v * 100} ctm`}</span>
                <input
                  type="number"
                  min={0}
                  data-testid={`denom-${v}`}
                  value={conteo[v] ?? 0}
                  onChange={(e) =>
                    onCambiar({ ...conteo, [v]: Math.max(0, +e.target.value || 0) })
                  }
                />
                <span className="pdv-denom-sub">
                  {(v * (conteo[v] ?? 0)).toFixed(2)}
                </span>
              </label>
            ))}
          </div>
        </div>
      ))}
    </>
  );
}

/** Cierre: mismo conteo pieza por pieza que la apertura, el reporte de lote
 * de cada terminal que abrió operativo (RN-POS-004) y la firma de quien
 * recibe el efectivo (RN-MDP-002).
 *
 * Los descuadres los calcula el servidor —conoce lo cobrado y los
 * movimientos del turno, el PDV no—; acá solo se le entrega lo contado y lo
 * declarado por cada POS. */
export function DialogoCierre({
  abierto,
  posVerificados,
  onCerrar,
  onCerrarCaja,
  ocupado,
}: {
  abierto: boolean;
  posVerificados: PosVerificado[];
  onCerrar: () => void;
  onCerrarCaja: (datos: {
    detalle: Record<string, number>;
    custodia: CustodiaDestino;
    atribucion: DescuadreAtribucion | "";
    reportesPos: { pos_tarjeta_id: string; monto_lote: string; referencia?: string }[];
    receptor: { username: string; pin: string };
  }) => void;
  ocupado: boolean;
}) {
  const [conteo, setConteo] = useState<Record<string, number>>({});
  // Tipados con la unión del contrato y no con `string`: son enums en la
  // base (RN-MDP-005) y el schema los valida con `pattern`. El `""` inicial
  // es "todavía no eligió", no un valor que pueda viajar.
  const [custodia, setCustodia] = useState<CustodiaDestino | "">("");
  const [atribucion, setAtribucion] = useState<DescuadreAtribucion | "">("");
  const [lotes, setLotes] = useState<Record<string, string>>({});
  const [usuario, setUsuario] = useState("");
  const [pin, setPin] = useState("");
  const total = Object.entries(conteo).reduce(
    (a, [v, n]) => a + Number(v) * (n || 0),
    0,
  );
  // Solo los que abrieron operativos: a un terminal averiado no se le pide
  // lote porque no cobró nada, y el servidor tampoco se lo pide.
  const operativos = posVerificados.filter((p) => p.operativo);

  useEffect(() => {
    if (!abierto) return;
    setConteo({});
    setCustodia("");
    setAtribucion("");
    setLotes({});
    setUsuario("");
    setPin("");
  }, [abierto]);

  return (
    <Dialogo titulo="Cierre de caja" abierto={abierto} onCerrar={onCerrar}>
      <p className="pdv-nota">
        Cuenta el efectivo del cajón al final del turno. El sistema compara
        contra lo cobrado y los movimientos registrados.
      </p>
      <ConteoDenominaciones conteo={conteo} onCambiar={setConteo} />

      {operativos.length > 0 && (
        <>
          <p className="pdv-etiqueta">Cierre de lote por terminal</p>
          <p className="pdv-nota">
            Saca el cierre de lote de cada POS y copia el total. Sin esto el
            cierre no cuadra las tarjetas.
          </p>
          {operativos.map((p) => (
            <label key={p.pos_tarjeta_id} className="pdv-etiqueta">
              <span>{p.serie}</span>
              <input
                className="pdv-campo"
                type="number"
                min={0}
                step="0.10"
                inputMode="decimal"
                placeholder="0.00"
                data-testid={`lote-${p.serie}`}
                value={lotes[p.pos_tarjeta_id] ?? ""}
                onChange={(e) =>
                  setLotes((previos) => ({
                    ...previos,
                    [p.pos_tarjeta_id]: e.target.value,
                  }))
                }
              />
            </label>
          ))}
        </>
      )}

      <p className="pdv-etiqueta">A dónde va el efectivo</p>
      {/* El destino, no el nombre de quien recibe: a quién se le entregó ya
          queda probado por el PIN de abajo, y escribirlo además era un dato
          suelto que no coincidía con nadie. */}
      <select
        className="pdv-campo"
        data-testid="cierre-custodia"
        value={custodia}
        onChange={(e) => setCustodia(esCustodia(e.target.value) ? e.target.value : "")}
      >
        <option value="">Elegir destino...</option>
        <option value="local_caja_fuerte">Caja fuerte del local</option>
        <option value="traslado_contabilidad">Traslado a contabilidad</option>
      </select>
      <p className="pdv-etiqueta">Recibe</p>
      <div className="pdv-dos">
        <input
          className="pdv-campo"
          placeholder="Usuario de quien recibe"
          autoComplete="off"
          data-testid="cierre-usuario"
          value={usuario}
          onChange={(e) => setUsuario(e.target.value)}
        />
        <input
          className="pdv-campo"
          type="password"
          inputMode="numeric"
          placeholder="PIN"
          autoComplete="off"
          data-testid="cierre-pin"
          value={pin}
          onChange={(e) => setPin(e.target.value)}
        />
      </div>

      <p className="pdv-etiqueta">Si hay descuadre, a quién se le atribuye</p>
      {/* Tres valores y no texto libre: es un enum en la base (RN-MDP-005), y
          además un descuadre se atribuye a alguien concreto — "no sé qué pasó"
          escrito de veinte maneras distintas no se puede sumar después. */}
      <select
        className="pdv-campo"
        value={atribucion}
        onChange={(e) =>
          setAtribucion(esAtribucion(e.target.value) ? e.target.value : "")
        }
      >
        <option value="">Sin atribuir todavía</option>
        <option value="cajero">Cajero</option>
        <option value="encargado">Encargado</option>
        <option value="tercero_reportado">Tercero reportado</option>
      </select>

      <footer className="pdv-dialogo-pie">
        <div>
          <p className="pdv-etiqueta">Efectivo contado</p>
          <strong className="pdv-monto-grande">{soles(total)}</strong>
        </div>
        <button
          type="button"
          className="pdv-boton-pri"
          disabled={
            ocupado ||
            !custodia ||
            !usuario.trim() ||
            !pin.trim() ||
            operativos.some((p) => !lotes[p.pos_tarjeta_id])
          }
          onClick={() => {
            // El botón ya está deshabilitado sin destino; el chequeo existe
            // para que el **tipo** lo sepa, no por desconfianza del
            // `disabled`. Sin él, `""` sería un `custodia` válido para TS y
            // el 422 volvería a aparecer recién en el servidor.
            if (!custodia) return;
            onCerrarCaja({
              detalle: conteo,
              custodia,
              atribucion,
              reportesPos: operativos.map((p) => ({
                pos_tarjeta_id: p.pos_tarjeta_id,
                monto_lote: String(Number(lotes[p.pos_tarjeta_id]) || 0),
              })),
              receptor: { username: usuario.trim(), pin },
            });
          }}
        >
          Cerrar caja
        </button>
      </footer>
    </Dialogo>
  );
}

const NOTAS_RAPIDAS = ["Sin cebolla", "Sin ají", "Bien cocida", "Para llevar aparte"];

/**
 * Configuración de la línea: variante, cantidad, nota a cocina y extras.
 * Todo sale de la carta (`item`), ya con precios resueltos para esta
 * sucursal y canal.
 *
 * Dos obligaciones distintas conviven acá:
 * - **Presentación** (Personal/Mediana/Familiar): si el producto tiene,
 *   elegir una es obligatorio y define el precio de la línea (RN-COM-022).
 * - **Grupos de extras**: obligatorios solo si el producto lo declaró
 *   (`grupo_minimo >= 1`, RN-COM-023).
 *
 * Lo que falta se dice en el pie y bloquea Guardar, en vez de dejar armar
 * una línea que el servidor va a rechazar al enviar el pedido.
 */
export function DialogoProducto({
  linea,
  item,
  enviado,
  onGuardar,
  onQuitar,
  onAnularLinea,
  onCerrar,
}: {
  linea: LineaBorrador | null;
  item: ItemDeCarta | null;
  /** La línea ya salió a cocina: quitarla es reponer inventario y exige
   * PIN de supervisor (RN-COM-020), no un descarte local. */
  enviado: boolean;
  onGuardar: (l: LineaBorrador) => void;
  onQuitar: (id: string) => void;
  onAnularLinea: (id: string, encargado: { username: string; pin: string }) => void;
  onCerrar: () => void;
}) {
  const [cantidad, setCantidad] = useState(1);
  const [nota, setNota] = useState("");
  const [extras, setExtras] = useState<Record<string, number>>({});
  const [varianteId, setVarianteId] = useState("");
  const [pidiendoPin, setPidiendoPin] = useState(false);
  const [usuario, setUsuario] = useState("");
  const [pin, setPin] = useState("");

  useEffect(() => {
    if (!linea) return;
    setCantidad(linea.cantidad);
    setNota(linea.nota);
    setExtras(
      Object.fromEntries(linea.extras.map((e) => [e.productoId, e.cantidad])),
    );
    // Al reabrir una línea ya armada, su producto ES la variante elegida.
    setVarianteId(
      item?.variantes.some((v) => v.producto_comercial_id === linea.productoId)
        ? linea.productoId
        : "",
    );
    setPidiendoPin(false);
    setUsuario("");
    setPin("");
  }, [linea, item]);

  if (!linea) return null;

  const variantes = item?.variantes ?? [];
  const variante = variantes.find((v) => v.producto_comercial_id === varianteId);
  const grupos = agruparExtras(item?.extras ?? []);
  const falta = queFalta(variantes, variante, grupos, extras);

  const guardar = () => {
    if (falta) return;
    const elegidos = (item?.extras ?? [])
      .filter((e) => (extras[e.producto_comercial_id] ?? 0) > 0)
      .map((e) => ({
        productoId: e.producto_comercial_id,
        nombre: e.nombre,
        precio: Number(e.precio_unitario),
        cantidad: extras[e.producto_comercial_id],
      }));
    onGuardar({
      ...linea,
      // La variante ES el producto que se vende: su id y su precio son los
      // que viajan al servidor, no los del padre.
      productoId: variante?.producto_comercial_id ?? linea.productoId,
      nombre: variante?.nombre ?? linea.nombre,
      precio: variante ? Number(variante.precio_unitario) : linea.precio,
      cantidad,
      nota: nota.trim(),
      extras: elegidos,
    });
  };

  return (
    <Dialogo titulo={linea.nombre} abierto onCerrar={onCerrar}>
      <Variantes
        variantes={variantes}
        producto={item}
        elegida={varianteId}
        onElegir={setVarianteId}
      />

      <p className="pdv-etiqueta">Cantidad</p>
      <div className="pdv-stepper">
        <button type="button" onClick={() => setCantidad(Math.max(1, cantidad - 1))}>
          −
        </button>
        <span>{cantidad}</span>
        <button type="button" onClick={() => setCantidad(cantidad + 1)}>
          +
        </button>
      </div>

      <GruposDeExtras grupos={grupos} elegidos={extras} onCambiar={setExtras} />

      <p className="pdv-etiqueta">Nota para cocina</p>
      <input
        className="pdv-campo"
        value={nota}
        placeholder="Sin cebolla, bien cocida…"
        onChange={(e) => setNota(e.target.value)}
      />
      <div className="pdv-chips">
        {NOTAS_RAPIDAS.map((n) => (
          <button
            key={n}
            type="button"
            className="pdv-chip"
            onClick={() =>
              setNota(nota.includes(n) ? nota : [nota, n].filter(Boolean).join(", "))
            }
          >
            {n}
          </button>
        ))}
      </div>

      {pidiendoPin && (
        <>
          <p className="pdv-etiqueta">Ya salió a cocina · PIN de supervisor</p>
          <div className="pdv-dos">
            <input
              className="pdv-campo"
              placeholder="Usuario del supervisor"
              autoComplete="off"
              value={usuario}
              onChange={(e) => setUsuario(e.target.value)}
            />
            <input
              className="pdv-campo"
              type="password"
              inputMode="numeric"
              placeholder="PIN"
              autoComplete="off"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
            />
          </div>
          <p className="pdv-nota">
            El insumo ya se descontó: quitar la línea lo repone (RN-COM-020).
          </p>
        </>
      )}

      <footer className="pdv-dialogo-pie">
        {pidiendoPin ? (
          <button
            type="button"
            className="pdv-boton-riesgo"
            disabled={!usuario.trim() || !pin.trim()}
            onClick={() =>
              onAnularLinea(linea.id, { username: usuario.trim(), pin })
            }
          >
            Confirmar anulación
          </button>
        ) : (
          <button
            type="button"
            className="pdv-boton-riesgo"
            onClick={() => (enviado ? setPidiendoPin(true) : onQuitar(linea.id))}
          >
            Quitar del pedido
          </button>
        )}
        {falta && <span className="pdv-falta">{falta}</span>}
        <button
          type="button"
          className="pdv-boton-pri"
          disabled={Boolean(falta)}
          onClick={guardar}
        >
          Guardar
        </button>
      </footer>
    </Dialogo>
  );
}

/** Tarjetas de presentación. Obligatorias cuando existen (RN-COM-022). */
function Variantes({
  variantes,
  producto,
  elegida,
  onElegir,
}: {
  variantes: VarianteDeCarta[];
  producto: ItemDeCarta | null;
  elegida: string;
  onElegir: (id: string) => void;
}) {
  if (variantes.length === 0) return null;
  const nombreProducto = producto?.nombre ?? "";
  return (
    <>
      <p className="pdv-etiqueta">Presentación · obligatorio</p>
      <div className="pdv-variantes">
        {variantes.map((v) => (
          <button
            key={v.producto_comercial_id}
            type="button"
            className="pdv-variante"
            aria-pressed={elegida === v.producto_comercial_id}
            onClick={() => onElegir(v.producto_comercial_id)}
          >
            <span className="pdv-variante-nombre">
              {etiquetaCorta(v.nombre, nombreProducto)}
            </span>
            <span className="pdv-variante-precio">{soles(v.precio_unitario)}</span>
          </button>
        ))}
      </div>
    </>
  );
}

/** La tarjeta dice "Familiar", no "Pizza Peperoni Familiar": el nombre del
 * producto ya está en el título del diálogo. El nombre completo se conserva
 * en la línea, que es lo que sale impreso en el ticket y el comprobante. */
function etiquetaCorta(nombre: string, nombreProducto: string): string {
  return nombre.toLowerCase().startsWith(nombreProducto.toLowerCase())
    ? nombre.slice(nombreProducto.length).trim() || nombre
    : nombre;
}

/** Extras agrupados, cada grupo diciendo si obliga a elegir y hasta
 * cuántas opciones admite (RN-COM-023). */
function GruposDeExtras({
  grupos,
  elegidos,
  onCambiar,
}: {
  grupos: GrupoDeExtras[];
  elegidos: Record<string, number>;
  onCambiar: (v: Record<string, number>) => void;
}) {
  return (
    <>
      {grupos.map((grupo) => (
        <div key={grupo.id ?? "sueltos"}>
          <p className="pdv-etiqueta">
            {grupo.nombre ?? "Extras"} ·{" "}
            {grupo.minimo >= 1 ? `obligatorio (elige ${grupo.minimo})` : "opcional"}
            {grupo.maximo ? ` · hasta ${grupo.maximo}` : ""}
          </p>
          <div className="pdv-lista">
            {grupo.extras.map((e) => (
              <FilaExtra
                key={e.producto_comercial_id}
                extra={e}
                grupo={grupo}
                elegidos={elegidos}
                onCambiar={onCambiar}
              />
            ))}
          </div>
        </div>
      ))}
    </>
  );
}

function FilaExtra({
  extra,
  grupo,
  elegidos,
  onCambiar,
}: {
  extra: ExtraDeCarta;
  grupo: GrupoDeExtras;
  elegidos: Record<string, number>;
  onCambiar: (v: Record<string, number>) => void;
}) {
  const n = elegidos[extra.producto_comercial_id] ?? 0;
  const tope = extra.maximo ?? 99;
  // El tope del grupo cuenta opciones distintas, no unidades: "hasta 3
  // toppings" no impide pedir doble de uno.
  const grupoLleno =
    grupo.maximo !== null && n === 0 && elegidosEn(grupo, elegidos) >= grupo.maximo;
  const poner = (cantidad: number) =>
    onCambiar({ ...elegidos, [extra.producto_comercial_id]: cantidad });

  return (
    <div className="pdv-extra">
      <span>
        {extra.nombre}
        <em>{soles(extra.precio_unitario)} c/u</em>
      </span>
      <div className="pdv-stepper chico">
        <button type="button" onClick={() => poner(Math.max(0, n - 1))}>
          −
        </button>
        <span>{n}</span>
        <button
          type="button"
          disabled={n >= tope || grupoLleno}
          onClick={() => poner(Math.min(tope, n + 1))}
        >
          +
        </button>
      </div>
    </div>
  );
}

type GrupoDeExtras = {
  id: string | null;
  nombre: string | null;
  minimo: number;
  maximo: number | null;
  extras: ExtraDeCarta[];
};

/** Los extras vienen planos del backend con su grupo adentro; acá se
 * agrupan para dibujarlos. Los sueltos (sin grupo) caen al final, siempre
 * opcionales. */
function agruparExtras(extras: ExtraDeCarta[]): GrupoDeExtras[] {
  const grupos: GrupoDeExtras[] = [];
  for (const extra of extras) {
    const existente = grupos.find((g) => g.id === extra.grupo_id);
    if (existente) {
      existente.extras.push(extra);
      continue;
    }
    grupos.push({
      id: extra.grupo_id,
      nombre: extra.grupo_nombre,
      minimo: extra.grupo_minimo,
      maximo: extra.grupo_maximo,
      extras: [extra],
    });
  }
  return grupos.sort((a, b) => Number(a.id === null) - Number(b.id === null));
}

function elegidosEn(grupo: GrupoDeExtras, extras: Record<string, number>): number {
  return grupo.extras.filter((e) => (extras[e.producto_comercial_id] ?? 0) > 0).length;
}

/** Qué le falta a la línea para poder guardarse. Mismo criterio que valida
 * el servidor al confirmar la venta, dicho en el momento en que se puede
 * corregir. */
function queFalta(
  variantes: VarianteDeCarta[],
  variante: VarianteDeCarta | undefined,
  grupos: GrupoDeExtras[],
  extras: Record<string, number>,
): string | null {
  if (variantes.length > 0 && !variante) return "Elige una presentación";
  for (const grupo of grupos) {
    if (elegidosEn(grupo, extras) < grupo.minimo) {
      return `Elige ${grupo.minimo} en ${grupo.nombre ?? "Extras"}`;
    }
  }
  return null;
}

const TIPOS = [
  ["mesa", "Mesa", "Consumo en salón · sin empaques"],
  ["takeout", "Para llevar", "Agrega empaques por producto"],
  ["delivery", "Delivery", "Empaques + tarifa · comanda con dirección"],
] as const;

export function DialogoTipo({
  abierto,
  borrador,
  mesas,
  onCerrar,
  onConfirmar,
}: {
  abierto: boolean;
  borrador: Borrador | null;
  mesas: MesaEnMapa[];
  onCerrar: () => void;
  onConfirmar: (cambios: Partial<Borrador>) => void;
}) {
  const [tipo, setTipo] = useState<Borrador["tipo"]>(null);
  const [mesaId, setMesaId] = useState<string | null>(null);
  const [comensales, setComensales] = useState(2);
  const [direccion, setDireccion] = useState("");

  useEffect(() => {
    if (!borrador) return;
    setTipo(borrador.tipo);
    setMesaId(borrador.mesaId);
    setComensales(borrador.comensales ?? 2);
    // La dirección del cliente registrado entra sola; solo se escribe si no
    // tiene ninguna.
    setDireccion(borrador.direccion ?? borrador.cliente?.direccion ?? "");
  }, [borrador]);

  const listo = tipo !== null && (tipo !== "mesa" || mesaId !== null);
  const mesa = mesas.find((m) => m.id === mesaId);

  return (
    <Dialogo titulo="Tipo de orden" abierto={abierto} onCerrar={onCerrar}>
      <div className="pdv-lista">
        {TIPOS.map(([clave, nombre, detalle]) => (
          <button
            key={clave}
            type="button"
            className={`pdv-opcion ${tipo === clave ? "on" : ""}`}
            onClick={() => setTipo(clave)}
          >
            <span>
              <strong>{nombre}</strong>
              <em>{detalle}</em>
            </span>
            {tipo === clave && <span aria-hidden>✓</span>}
          </button>
        ))}
      </div>

      {tipo === "mesa" && (
        <>
          <p className="pdv-etiqueta">Número de mesa · obligatorio</p>
          <div className="pdv-chips">
            {mesas.map((m) => (
              <button
                key={m.id}
                type="button"
                className={`pdv-chip ${mesaId === m.id ? "on" : ""}`}
                disabled={Boolean(m.venta_id) && m.id !== borrador?.mesaId}
                onClick={() => setMesaId(m.id)}
              >
                {m.numero}
              </button>
            ))}
          </div>
          <p className="pdv-etiqueta">Comensales · opcional</p>
          <div className="pdv-stepper">
            <button type="button" onClick={() => setComensales(Math.max(1, comensales - 1))}>
              −
            </button>
            <span>{comensales}</span>
            <button type="button" onClick={() => setComensales(comensales + 1)}>
              +
            </button>
          </div>
        </>
      )}

      {tipo === "delivery" && (
        <>
          <p className="pdv-etiqueta">Dirección de entrega</p>
          <input
            className="pdv-campo"
            value={direccion}
            placeholder="Jr. San Martín 456"
            onChange={(e) => setDireccion(e.target.value)}
          />
          <p className="pdv-nota">
            {borrador?.cliente
              ? borrador.cliente.direccion
                ? `Dirección registrada de ${borrador.cliente.nombre}.`
                : `${borrador.cliente.nombre} no tiene dirección registrada.`
              : "Sin cliente asignado: la dirección queda solo en este pedido."}
          </p>
        </>
      )}

      <footer className="pdv-dialogo-pie">
        <span />
        <button
          type="button"
          className="pdv-boton-pri"
          disabled={!listo}
          onClick={() =>
            onConfirmar({
              tipo,
              mesaId: tipo === "mesa" ? mesaId : null,
              mesaNumero: tipo === "mesa" ? (mesa?.numero ?? null) : null,
              comensales: tipo === "mesa" ? comensales : null,
              direccion: tipo === "delivery" ? direccion.trim() : null,
            })
          }
        >
          Confirmar
        </button>
      </footer>
    </Dialogo>
  );
}

export function DialogoCliente({
  abierto,
  onCerrar,
  onBuscar,
  onElegir,
  onCrear,
}: {
  abierto: boolean;
  onCerrar: () => void;
  onBuscar: (q: string) => Promise<ClienteBuscado[]>;
  onElegir: (c: ClienteBuscado) => void;
  onCrear: (datos: {
    nombre: string;
    telefono: string;
    numero_documento: string;
    direccion: string;
    fecha_nacimiento: string;
  }) => Promise<void>;
}) {
  const [q, setQ] = useState("");
  const [resultados, setResultados] = useState<ClienteBuscado[]>([]);
  const [creando, setCreando] = useState(false);
  const [nombre, setNombre] = useState("");
  const [telefono, setTelefono] = useState("");
  const [documento, setDocumento] = useState("");
  const [direccion, setDireccion] = useState("");
  const [cumpleanos, setCumpleanos] = useState("");

  useEffect(() => {
    if (!abierto) {
      setQ("");
      setResultados([]);
      setCreando(false);
      setDocumento("");
      setDireccion("");
      setCumpleanos("");
    }
  }, [abierto]);

  useEffect(() => {
    if (q.trim().length < 2) {
      setResultados([]);
      return;
    }
    // Rebote corto: en caja se teclea rápido y no hace falta una consulta
    // por tecla.
    const t = setTimeout(() => {
      onBuscar(q).then(setResultados).catch(() => setResultados([]));
    }, 250);
    return () => clearTimeout(t);
  }, [q, onBuscar]);

  return (
    <Dialogo titulo="Cliente" abierto={abierto} onCerrar={onCerrar}>
      {creando ? (
        <>
          <p className="pdv-etiqueta">Nombre</p>
          <input
            className="pdv-campo"
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
          />
          <p className="pdv-etiqueta">Teléfono</p>
          <input
            className="pdv-campo"
            inputMode="tel"
            value={telefono}
            onChange={(e) => setTelefono(e.target.value)}
          />
          <p className="pdv-nota">
            El documento es opcional: para registrar basta el teléfono. Se
            completa después si el cliente quiere factura o puntos.
          </p>
          <div className="pdv-dos">
            <div>
              <p className="pdv-etiqueta">DNI (opcional)</p>
              <input
                className="pdv-campo"
                inputMode="numeric"
                maxLength={8}
                value={documento}
                onChange={(e) => setDocumento(e.target.value.replace(/\D/g, ""))}
              />
            </div>
            <div>
              <p className="pdv-etiqueta">Cumpleaños (opcional)</p>
              <input
                className="pdv-campo"
                type="date"
                value={cumpleanos}
                onChange={(e) => setCumpleanos(e.target.value)}
              />
            </div>
          </div>
          <p className="pdv-etiqueta">Dirección (opcional)</p>
          <input
            className="pdv-campo"
            value={direccion}
            placeholder="Jr. San Martín 456"
            onChange={(e) => setDireccion(e.target.value)}
          />
          <footer className="pdv-dialogo-pie">
            <button type="button" onClick={() => setCreando(false)}>
              Volver
            </button>
            <button
              type="button"
              className="pdv-boton-pri"
              disabled={!nombre.trim() || telefono.trim().length < 6}
              onClick={() =>
                onCrear({
                  nombre: nombre.trim(),
                  telefono: telefono.trim(),
                  numero_documento: documento.trim(),
                  direccion: direccion.trim(),
                  fecha_nacimiento: cumpleanos,
                })
              }
            >
              Guardar cliente
            </button>
          </footer>
        </>
      ) : (
        <>
          <input
            className="pdv-campo"
            placeholder="Buscar por teléfono, documento o nombre"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <div className="pdv-lista">
            {resultados.map((c) => (
              <button
                key={c.id}
                type="button"
                className="pdv-opcion"
                onClick={() => onElegir(c)}
              >
                <span>
                  <strong>{c.nombre}</strong>
                  <em>
                    {[c.telefono, c.numero_documento].filter(Boolean).join(" · ") ||
                      "sin datos de contacto"}
                  </em>
                </span>
                {!c.identificado && <span className="pdv-badge">sin doc.</span>}
              </button>
            ))}
            {q.trim().length >= 2 && resultados.length === 0 && (
              <p className="pdv-nota">Sin resultados.</p>
            )}
          </div>
          <button
            type="button"
            className="pdv-boton-sec ancho"
            onClick={() => {
              setNombre(/^\d+$/.test(q.trim()) ? "" : q.trim());
              setTelefono(/^\d+$/.test(q.trim()) ? q.trim() : "");
              setCreando(true);
            }}
          >
            + Crear cliente nuevo
          </button>
        </>
      )}
    </Dialogo>
  );
}

/** El largo del documento decide el comprobante (RN-CPP-003), y se dice en
 * pantalla antes de confirmar: enterarse de que salió boleta cuando el
 * cliente quería factura ya es tarde. */
function leyendaDocumento(doc: string): string {
  if (doc.length === 11) return "Se emite FACTURA · el documento tiene 11 dígitos";
  if (doc.length === 8) return "Se emite BOLETA · el documento tiene 8 dígitos";
  if (doc.length > 0) {
    return "Documento incompleto: debe tener 8 (DNI) u 11 (RUC) dígitos";
  }
  return "Sin documento se emite boleta a nombre de Clientes varios.";
}

/** Todo el aritmético del cobro en un solo lugar, fuera del componente:
 * mezclarlo con el JSX es lo que hacía ilegible cuánto pesaba cada rama. */
function calcularCobro(
  total: number,
  pagos: Array<{ medioId: string; monto: number }>,
  monto: string,
  medioId: string,
  medios: MedioPago[],
) {
  const confirmado = pagos.reduce((a, p) => a + p.monto, 0);
  const enCurso = Math.max(0, Number(monto) || 0);
  const falta = Math.max(0, total - confirmado);
  // El vuelto solo existe en efectivo: en tarjeta o Yape no hay cajón que
  // devuelva plata, así que ahí un monto de más es un error de tecleo, no
  // un cobro válido (se bloquea en vez de registrarse).
  const esEfectivo = medios.find((m) => m.id === medioId)?.tipo === "efectivo";
  const excede = enCurso > falta && !esEfectivo;
  // Lo que realmente se le acredita a la venta nunca pasa del saldo — el
  // backend lo rechazaría igual (RN-COM-002) — el resto es vuelto físico,
  // no un pago de más.
  const aplicado = Math.min(enCurso, falta);
  const pagado = confirmado + aplicado;
  return {
    enCurso,
    falta,
    excede,
    aplicado,
    pagado,
    restante: Math.max(0, total - pagado),
    vuelto: esEfectivo ? Math.max(0, enCurso - falta) : 0,
  };
}

function documentoValido(doc: string): boolean {
  return [0, 8, 11].includes(doc.length);
}

function cobroBloqueado(
  ocupado: boolean,
  excede: boolean,
  pagado: number,
  total: number,
  docValido: boolean,
): boolean {
  return ocupado || excede || pagado < total || !docValido;
}

function FilaVueltoRestante({ vuelto, restante }: { vuelto: number; restante: number }) {
  const hayVuelto = vuelto > 0;
  return (
    <div className="pdv-total-fila fuerte">
      <span>{hayVuelto ? "Vuelto" : "Restante"}</span>
      <span className={hayVuelto ? "verde" : restante > 0 ? "rojo" : "verde"}>
        {soles(hayVuelto ? vuelto : restante)}
      </span>
    </div>
  );
}

/** Cobro: se elige medio, se escribe monto y se confirma. **No hace falta
 * "Agregar"** para el caso normal — el monto tecleado ya cuenta. Agregar es
 * para sumar un segundo medio que cubra el faltante del primero. */
export function DialogoCobro({
  abierto,
  total,
  medios,
  ocupado,
  onCerrar,
  onConfirmar,
}: {
  abierto: boolean;
  total: number;
  medios: MedioPago[];
  ocupado: boolean;
  onCerrar: () => void;
  onConfirmar: (
    pagos: Array<{ medioId: string; monto: number }>,
    doc: string,
    nombre: string,
    propina: number,
  ) => void;
}) {
  const [medio, setMedio] = useState<string>("");
  const [monto, setMonto] = useState("");
  const [pagos, setPagos] = useState<Array<{ medioId: string; monto: number }>>([]);
  const [doc, setDoc] = useState("");
  const [nombre, setNombre] = useState("");
  const [propina, setPropina] = useState("");

  useEffect(() => {
    if (!abierto) return;
    setPagos([]);
    setDoc("");
    setNombre("");
    setPropina("");
    setMedio(medios[0]?.id ?? "");
    setMonto(total.toFixed(2));
  }, [abierto, total, medios]);

  const { enCurso, falta, excede, aplicado, pagado, restante, vuelto } =
    calcularCobro(total, pagos, monto, medio, medios);
  const tipoDoc = leyendaDocumento(doc);
  const docValido = documentoValido(doc);
  const montosRapidos = [10, 20, 50, 100, 200];

  return (
    <Dialogo titulo="Cobrar" abierto={abierto} onCerrar={onCerrar} ancho="ancho">
      <div className="pdv-cobro">
        <div className="pdv-cobro-resumen">
          <p className="pdv-etiqueta">Total a cobrar</p>
          <strong className="pdv-monto-grande">{soles(total)}</strong>
          {pagos.map((p, i) => (
            <div key={i} className="pdv-pago-fila">
              <span>{medios.find((m) => m.id === p.medioId)?.nombre}</span>
              <span>
                {soles(p.monto)}
                <button
                  type="button"
                  onClick={() => setPagos(pagos.filter((_, j) => j !== i))}
                >
                  quitar
                </button>
              </span>
            </div>
          ))}
        </div>

        <div>
          <div className="pdv-chips">
            {medios.map((m) => (
              <button
                key={m.id}
                type="button"
                className={`pdv-chip ${medio === m.id ? "on" : ""}`}
                onClick={() => setMedio(m.id)}
              >
                {m.nombre}
              </button>
            ))}
          </div>
          <div className="pdv-chips">
            <button type="button" className="pdv-chip" onClick={() => setMonto(falta.toFixed(2))}>
              Exacto · {soles(falta)}
            </button>
            {montosRapidos
              .filter((m) => m >= falta)
              .map((m) => (
                <button
                  key={m}
                  type="button"
                  className="pdv-chip"
                  onClick={() => setMonto(m.toFixed(2))}
                >
                  {soles(m)}
                </button>
              ))}
          </div>
          <div className="pdv-cobro-monto">
            <input
              className="pdv-campo"
              inputMode="decimal"
              value={monto}
              placeholder="Monto S/"
              onChange={(e) => setMonto(e.target.value)}
            />
            <button
              type="button"
              className="pdv-boton-sec"
              disabled={enCurso <= 0 || excede}
              onClick={() => {
                setPagos([...pagos, { medioId: medio, monto: aplicado }]);
                setMonto(Math.max(0, falta - aplicado).toFixed(2));
              }}
            >
              Agregar
            </button>
          </div>
          {excede && (
            <p className="pdv-nota rojo">
              {medios.find((m) => m.id === medio)?.nombre} no da vuelto: el monto no
              puede superar lo que falta.
            </p>
          )}
          <div className="pdv-total-fila">
            <span>Pagado</span>
            <span>{soles(pagado)}</span>
          </div>
          <FilaVueltoRestante vuelto={vuelto} restante={restante} />

          <p className="pdv-etiqueta">Propina (opcional)</p>
          <input
            className="pdv-campo"
            inputMode="decimal"
            value={propina}
            placeholder="Monto S/"
            onChange={(e) => setPropina(e.target.value)}
          />
          <p className="pdv-nota">
            Entra a caja aparte, no al comprobante ni al total de la venta.
          </p>

          <p className="pdv-etiqueta">Comprobante</p>
          <div className="pdv-dos">
            <input
              className="pdv-campo"
              inputMode="numeric"
              maxLength={11}
              placeholder="DNI (8) o RUC (11)"
              value={doc}
              onChange={(e) => setDoc(e.target.value.replace(/\D/g, ""))}
            />
            <input
              className="pdv-campo"
              placeholder="Nombre / razón social"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
            />
          </div>
          <p className="pdv-nota">{tipoDoc}</p>
        </div>
      </div>

      <footer className="pdv-dialogo-pie">
        <span />
        <button
          type="button"
          className="pdv-boton-pri"
          disabled={cobroBloqueado(ocupado, excede, pagado, total, docValido)}
          onClick={() =>
            onConfirmar(
              aplicado > 0 ? [...pagos, { medioId: medio, monto: aplicado }] : pagos,
              doc,
              nombre.trim(),
              Math.max(0, Number(propina) || 0),
            )
          }
        >
          Confirmar pago
        </button>
      </footer>
    </Dialogo>
  );
}
