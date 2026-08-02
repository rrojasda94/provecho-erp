"use client";

import { useEffect, useRef, useState } from "react";

import {
  soles,
  type ClienteBuscado,
  type ItemDeCarta,
  type MedioPago,
  type MesaEnMapa,
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
  onAbrir,
  ocupado,
}: {
  abierto: boolean;
  onAbrir: (
    monto: number,
    detalle: Record<string, number>,
    encargado: { username: string; pin: string },
  ) => void;
  ocupado: boolean;
}) {
  const [conteo, setConteo] = useState<Record<string, number>>({});
  const [usuario, setUsuario] = useState("");
  const [pin, setPin] = useState("");
  const total = Object.entries(conteo).reduce(
    (a, [v, n]) => a + Number(v) * (n || 0),
    0,
  );

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
      <p className="pdv-etiqueta">Entrega el encargado</p>
      <div className="pdv-dos">
        <input
          className="pdv-campo"
          placeholder="Usuario del encargado"
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
          disabled={ocupado || !usuario.trim() || !pin.trim()}
          onClick={() => onAbrir(total, conteo, { username: usuario.trim(), pin })}
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

/** Cierre: mismo conteo pieza por pieza que la apertura, más a quién se le
 * entrega el efectivo contado. El descuadre lo calcula el servidor —
 * conoce lo cobrado y los movimientos del turno, el PDV no. */
export function DialogoCierre({
  abierto,
  onCerrar,
  onCerrarCaja,
  ocupado,
}: {
  abierto: boolean;
  onCerrar: () => void;
  onCerrarCaja: (montoReal: number, detalle: Record<string, number>, custodia: string) => void;
  ocupado: boolean;
}) {
  const [conteo, setConteo] = useState<Record<string, number>>({});
  const [custodia, setCustodia] = useState("");
  const total = Object.entries(conteo).reduce(
    (a, [v, n]) => a + Number(v) * (n || 0),
    0,
  );

  useEffect(() => {
    if (!abierto) return;
    setConteo({});
    setCustodia("");
  }, [abierto]);

  return (
    <Dialogo titulo="Cierre de caja" abierto={abierto} onCerrar={onCerrar}>
      <p className="pdv-nota">
        Cuenta el efectivo del cajón al final del turno. El sistema compara
        contra lo cobrado y los movimientos registrados.
      </p>
      <ConteoDenominaciones conteo={conteo} onCambiar={setConteo} />
      <p className="pdv-etiqueta">Se entrega a</p>
      <input
        className="pdv-campo"
        placeholder="Nombre de quien recibe el efectivo"
        value={custodia}
        onChange={(e) => setCustodia(e.target.value)}
      />

      <footer className="pdv-dialogo-pie">
        <div>
          <p className="pdv-etiqueta">Efectivo contado</p>
          <strong className="pdv-monto-grande">{soles(total)}</strong>
        </div>
        <button
          type="button"
          className="pdv-boton-pri"
          disabled={ocupado || !custodia.trim()}
          onClick={() => onCerrarCaja(total, conteo, custodia.trim())}
        >
          Cerrar caja
        </button>
      </footer>
    </Dialogo>
  );
}

const NOTAS_RAPIDAS = ["Sin cebolla", "Sin ají", "Bien cocida", "Para llevar aparte"];

/** Configuración de la línea: cantidad, nota a cocina y extras. Los extras
 * salen de la carta (`item.extras`), ya con su precio resuelto para esta
 * sucursal y canal. */
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
    setPidiendoPin(false);
    setUsuario("");
    setPin("");
  }, [linea]);

  if (!linea) return null;

  const guardar = () => {
    const elegidos = (item?.extras ?? [])
      .filter((e) => (extras[e.producto_comercial_id] ?? 0) > 0)
      .map((e) => ({
        productoId: e.producto_comercial_id,
        nombre: e.nombre,
        precio: Number(e.precio_unitario),
        cantidad: extras[e.producto_comercial_id],
      }));
    onGuardar({ ...linea, cantidad, nota: nota.trim(), extras: elegidos });
  };

  return (
    <Dialogo titulo={linea.nombre} abierto onCerrar={onCerrar}>
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

      {(item?.extras.length ?? 0) > 0 && (
        <>
          <p className="pdv-etiqueta">Extras</p>
          <div className="pdv-lista">
            {item!.extras.map((e) => {
              const n = extras[e.producto_comercial_id] ?? 0;
              const tope = e.maximo ?? 99;
              return (
                <div key={e.producto_comercial_id} className="pdv-extra">
                  <span>
                    {e.nombre}
                    <em>{soles(e.precio_unitario)} c/u</em>
                  </span>
                  <div className="pdv-stepper chico">
                    <button
                      type="button"
                      onClick={() =>
                        setExtras({
                          ...extras,
                          [e.producto_comercial_id]: Math.max(0, n - 1),
                        })
                      }
                    >
                      −
                    </button>
                    <span>{n}</span>
                    <button
                      type="button"
                      disabled={n >= tope}
                      onClick={() =>
                        setExtras({
                          ...extras,
                          [e.producto_comercial_id]: Math.min(tope, n + 1),
                        })
                      }
                    >
                      +
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

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
        <button type="button" className="pdv-boton-pri" onClick={guardar}>
          Guardar
        </button>
      </footer>
    </Dialogo>
  );
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
