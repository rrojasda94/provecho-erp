"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  alCambiarCarrito,
  obtenerCarrito,
  totalDelCarrito,
  vaciarCarrito,
  type LineaCarrito,
} from "@/lib/carrito";

import { Girador } from "@/components/boton";
import { direccionDePunto } from "@/components/direccion/buscador-lugares";
import { CampoDireccion, UBICACION_VACIA, type Ubicacion } from "@/components/direccion/campo-direccion";
import { coordenadasDe } from "@/components/direccion/ubicacion";
import { cargarMaps } from "@/lib/google-maps";
import { vibrar } from "@/lib/haptica";
import { configMapas } from "@/lib/mapas";

import { confirmarPedido, cotizarPedido, type Cotizacion } from "./actions";

export type SucursalOpcion = { id: string; nombre: string; direccion: string | null };
export type Perfil = {
  nombres: string;
  apellidos: string;
  telefono: string | null;
  debe_cambiar_clave?: boolean;
};
export type Direccion = {
  id: string;
  etiqueta: string | null;
  direccion: string;
  predeterminada?: boolean;
} & Partial<Ubicacion>;

/** El ancla guardada de una dirección, en la forma que espera el campo. */
function anclaDe(d: Direccion): Ubicacion {
  return {
    ubicacion_place_id: d.ubicacion_place_id ?? null,
    ubicacion_lat: d.ubicacion_lat ?? null,
    ubicacion_lng: d.ubicacion_lng ?? null,
    ubicacion_plus_code: d.ubicacion_plus_code ?? null,
    ubicacion_distrito: d.ubicacion_distrito ?? null,
  };
}

type Modalidad = "delivery" | "takeout";
type MedioPago = "efectivo" | "izipay";

function CamposContacto({
  nombre,
  telefono,
  onNombre,
  onTelefono,
}: {
  nombre: string;
  telefono: string;
  onNombre: (v: string) => void;
  onTelefono: (v: string) => void;
}) {
  const CAMPO = "rounded border-2 border-negro px-3 py-2";
  return (
    <div className="flex gap-2">
      <input
        value={nombre}
        onChange={(e) => onNombre(e.target.value)}
        placeholder="Tu nombre"
        required
        className={`${CAMPO} flex-1`}
      />
      <input
        value={telefono}
        onChange={(e) => onTelefono(e.target.value)}
        placeholder="Teléfono"
        required
        className={`${CAMPO} flex-1`}
      />
    </div>
  );
}

function CamposComprobante({
  numeroDocumento,
  razonSocial,
  onDocumento,
  onRazonSocial,
}: {
  numeroDocumento: string;
  razonSocial: string;
  onDocumento: (v: string) => void;
  onRazonSocial: (v: string) => void;
}) {
  const esFactura = numeroDocumento.length === 11;
  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs font-bold uppercase text-humo">
        DNI (boleta) o RUC de 11 dígitos (factura)
      </label>
      <input
        value={numeroDocumento}
        onChange={(e) => onDocumento(e.target.value.replace(/\D/g, ""))}
        maxLength={11}
        placeholder="DNI o RUC"
        className="rounded border-2 border-negro px-3 py-2"
      />
      {esFactura && (
        <input
          value={razonSocial}
          onChange={(e) => onRazonSocial(e.target.value)}
          placeholder="Razón social"
          required
          className="rounded border-2 border-negro px-3 py-2"
        />
      )}
    </div>
  );
}

/** El GPS del navegador, y después la calle que hay en ese punto.
 *
 * Antes devolvía solo el par de coordenadas y dejaba el campo de texto vacío:
 * el repartidor recibía un pedido con un punto y sin dirección escrita. Ahora
 * el punto se traduce a una dirección (geocodificación inversa, la misma que
 * usa el pin arrastrable) y se escribe en el campo. Si Google no contesta, al
 * menos queda el punto y el cliente escribe la referencia.
 */
function useUbicacionActual(alUbicar: (texto: string, ancla: Ubicacion) => void) {
  const [estado, setEstado] = useState<"inicial" | "buscando" | "lista" | "error">("inicial");
  const { apiKey } = configMapas();

  async function resolver(lat: number, lng: number) {
    try {
      const maps = await cargarMaps(apiKey);
      const hallado = await direccionDePunto(maps, lat, lng);
      if (hallado) {
        alUbicar(hallado.texto, hallado.ancla);
        setEstado("lista");
        return;
      }
    } catch {
      // Sin clave, sin internet o sin cuota: se sigue con el punto pelado.
    }
    alUbicar("", {
      ...UBICACION_VACIA,
      ubicacion_lat: String(lat),
      ubicacion_lng: String(lng),
    });
    setEstado("lista");
  }

  function pedir() {
    if (!("geolocation" in navigator)) {
      setEstado("error");
      return;
    }
    setEstado("buscando");
    navigator.geolocation.getCurrentPosition(
      (pos) => void resolver(pos.coords.latitude, pos.coords.longitude),
      () => setEstado("error"),
      { timeout: 8000 },
    );
  }

  return { estado, pedir };
}

export function CheckoutCliente({
  sucursales,
  perfil,
  direcciones,
}: {
  sucursales: SucursalOpcion[];
  perfil: Perfil | null;
  direcciones: Direccion[];
}) {
  const router = useRouter();
  // Estado inicial vacío a propósito: `obtenerCarrito()` lee `localStorage`,
  // que en el render del servidor no existe. Arrancar en `[]` y recién leer
  // el carrito real en un efecto mantiene el primer render del cliente
  // idéntico al del servidor — leerlo directo en el `useState` (como estaba
  // antes) hidrataba con datos distintos a los del HTML del servidor y
  // React descartaba el árbol entero (mismo síntoma que el `<a>` anidado:
  // el botón "Confirmar pedido" desaparecía un instante y el e2e nunca lo
  // encontraba a tiempo).
  const [lineas, setLineas] = useState<LineaCarrito[]>([]);
  useEffect(() => {
    const actualizar = () => setLineas(obtenerCarrito());
    actualizar();
    return alCambiarCarrito(actualizar);
  }, []);
  const [modalidad, setModalidad] = useState<Modalidad>("delivery");
  const [sucursalId, setSucursalId] = useState(sucursales[0]?.id ?? "");

  // La dirección predeterminada de la cuenta entra puesta, **con su punto en
  // el mapa**. Antes las direcciones guardadas se ofrecían como pastillas que
  // solo copiaban el texto y tiraban las coordenadas, así que a quien ya
  // tenía su casa cargada el sitio igual le exigía prender el GPS.
  const predeterminada =
    direcciones.find((d) => d.predeterminada) ?? direcciones[0] ?? null;
  // `semilla.version` es la `key` del campo: cambiarla lo remonta con otro
  // texto y otro pin. Es el mismo recurso que usa el PDV cuando el DNI del
  // cliente trae su dirección (`app/pdv/dialogos.tsx`).
  const [semilla, setSemilla] = useState({
    version: 0,
    texto: predeterminada?.direccion ?? "",
    ancla: predeterminada ? anclaDe(predeterminada) : UBICACION_VACIA,
  });
  const [direccionTexto, setDireccionTexto] = useState(predeterminada?.direccion ?? "");
  const [ancla, setAncla] = useState<Ubicacion>(
    predeterminada ? anclaDe(predeterminada) : UBICACION_VACIA,
  );

  function sembrarDireccion(texto: string, nueva: Ubicacion) {
    setSemilla((s) => ({ version: s.version + 1, texto, ancla: nueva }));
    setDireccionTexto(texto);
    setAncla(nueva);
  }
  const [nombre, setNombre] = useState(perfil ? `${perfil.nombres} ${perfil.apellidos}` : "");
  const [telefono, setTelefono] = useState(perfil?.telefono ?? "");
  // El efectivo es para quien tiene cuenta (RN-WEB-013): un invitado arranca
  // en Izipay y, si elige efectivo, se le invita a registrarse.
  const [medioPago, setMedioPago] = useState<MedioPago>(perfil ? "efectivo" : "izipay");
  const efectivoSinCuenta = medioPago === "efectivo" && !perfil;
  const [numeroDocumento, setNumeroDocumento] = useState("");
  const [razonSocial, setRazonSocial] = useState("");
  const [respuesta, setRespuesta] = useState<{
    clave: string;
    cotizacion: Cotizacion | null;
  } | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  const ubicacion = useUbicacionActual(sembrarDireccion);
  // De dónde salgan las coordenadas da igual: elegir una sugerencia de
  // Google, arrastrar el pin, usar una dirección guardada o prender el GPS.
  const punto = coordenadasDe(ancla);

  const total = useMemo(() => totalDelCarrito(lineas), [lineas]);

  const itemsCotizar = useMemo(
    () => lineas.map((l) => ({ producto_comercial_id: l.productoComercialId, cantidad: l.cantidad })),
    [lineas],
  );

  // Una cotización se identifica por lo que la determina. Guardar el
  // resultado junto a su clave resuelve dos cosas de una: se sabe si lo que
  // está en pantalla corresponde a lo que el cliente eligió recién (si no,
  // está cotizando) y una respuesta lenta de una consulta vieja no pisa a la
  // nueva — antes cambiar de local dos veces seguidas podía dejar el precio
  // del primero.
  const puedeCotizar = Boolean(
    (modalidad === "takeout" && sucursalId) || (modalidad === "delivery" && punto),
  );
  const claveCotizacion = JSON.stringify([
    modalidad,
    modalidad === "takeout" ? sucursalId : punto,
    itemsCotizar,
  ]);
  const cotizacion = respuesta?.clave === claveCotizacion ? respuesta.cotizacion : null;
  const cotizando = puedeCotizar && respuesta?.clave !== claveCotizacion;

  useEffect(() => {
    if (!puedeCotizar) return;
    let vigente = true;
    const [modalidadActual, origen, items] = JSON.parse(claveCotizacion) as [
      Modalidad,
      string | { lat: number; lng: number },
      { producto_comercial_id: string; cantidad: number }[],
    ];
    const promesa =
      modalidadActual === "takeout"
        ? cotizarPedido({
            modalidad: "takeout",
            sucursal_id: origen as string,
            items,
          })
        : cotizarPedido({
            modalidad: "delivery",
            ubicacion_lat: String((origen as { lat: number; lng: number }).lat),
            ubicacion_lng: String((origen as { lat: number; lng: number }).lng),
            items,
          });
    promesa.then((c) => {
      if (vigente) setRespuesta({ clave: claveCotizacion, cotizacion: c });
    });
    return () => {
      vigente = false;
    };
  }, [claveCotizacion, puedeCotizar]);

  function elegirDireccionGuardada(d: Direccion) {
    sembrarDireccion(d.direccion, anclaDe(d));
  }

  async function confirmar() {
    setError("");
    if (lineas.length === 0) return;
    if (modalidad === "delivery" && !punto) {
      setError(
        "Elige tu dirección de la lista que aparece al escribirla, o toca " +
          "“Usar mi ubicación actual”: necesitamos el punto en el mapa para cotizar el delivery.",
      );
      return;
    }
    setEnviando(true);
    const resultado = await confirmarPedido({
      modalidad,
      sucursal_id: modalidad === "takeout" ? sucursalId : undefined,
      items: lineas.map((l) => ({
        producto_comercial_id: l.productoComercialId,
        cantidad: l.cantidad,
        extras: l.extras.map((e) => ({ producto_comercial_id: e.id, cantidad: e.cantidad })),
        valores_variante_ids: l.valores.map((v) => v.id),
      })),
      nombre_contacto: nombre,
      telefono_contacto: telefono,
      direccion_entrega: modalidad === "delivery" ? direccionTexto : undefined,
      // El ancla completa y no solo el par de coordenadas: el `place_id`
      // identifica la puerta sin ambigüedad y el distrito puede cambiar la
      // tarifa. El backend ya los aceptaba; el sitio nunca se los mandaba.
      ...(modalidad === "delivery"
        ? {
            ubicacion_lat: punto ? String(punto.lat) : undefined,
            ubicacion_lng: punto ? String(punto.lng) : undefined,
            ubicacion_place_id: ancla.ubicacion_place_id ?? undefined,
            ubicacion_plus_code: ancla.ubicacion_plus_code ?? undefined,
            ubicacion_distrito: ancla.ubicacion_distrito ?? undefined,
          }
        : {}),
      medio_pago: medioPago,
      numero_documento: numeroDocumento || undefined,
      nombre_o_razon_social: numeroDocumento.length === 11 ? razonSocial : undefined,
    });
    setEnviando(false);
    if (!resultado.ok) {
      setError(resultado.error);
      return;
    }
    vaciarCarrito();
    const token = resultado.pedido.token_acceso ?? "";
    // Con Izipay el pedido espera el pago: primero la pantalla de cobro.
    const cobro = resultado.pedido.pago_estado === "pendiente" ? "/pago" : "";
    router.push(`/pedido/${resultado.pedido.id}${cobro}?token=${encodeURIComponent(token)}`);
  }

  if (lineas.length === 0) {
    return (
      <div className="mx-auto max-w-lg px-4 py-16 text-center">
        <p className="text-humo">Tu carrito está vacío.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-4 py-8">
      <h1 className="font-display text-2xl uppercase text-negro">Checkout</h1>

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-bold uppercase text-humo">¿Cómo lo quieres?</h2>
        <div className="flex gap-2">
          {(["delivery", "takeout"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setModalidad(m)}
              className={`flex-1 rounded border-2 border-negro py-2 font-bold uppercase ${
                modalidad === m ? "bg-verde text-negro" : "bg-white"
              }`}
            >
              {m === "delivery" ? "Delivery" : "Recojo en local"}
            </button>
          ))}
        </div>
      </section>

      {modalidad === "delivery" ? (
        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-bold uppercase text-humo">Dirección de entrega</h2>
          {direcciones.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {direcciones.map((d) => (
                <button
                  key={d.id}
                  type="button"
                  onClick={() => elegirDireccionGuardada(d)}
                  className={`rounded-full border-2 border-negro px-3 py-1 text-xs font-bold transition-transform active:scale-95 ${
                    direccionTexto === d.direccion ? "bg-verde" : "bg-white"
                  }`}
                >
                  {d.etiqueta ?? "Dirección"}
                </button>
              ))}
            </div>
          )}
          {/* El mismo campo del PDV: autocompletado de Google y pin arrastrable
              para corregir la puerta. La `key` lo remonta cuando la dirección
              llega de afuera (una guardada, o el GPS). */}
          <CampoDireccion
            key={semilla.version}
            etiqueta=""
            requerido
            defaultValue={semilla.texto}
            ubicacion={semilla.ancla}
            onCambio={(texto, nueva) => {
              setDireccionTexto(texto);
              setAncla(nueva);
            }}
          />
          <button
            type="button"
            onClick={ubicacion.pedir}
            disabled={ubicacion.estado === "buscando"}
            aria-busy={ubicacion.estado === "buscando"}
            className="flex items-center gap-2 self-start rounded border-2 border-negro px-3 py-1 text-xs font-bold uppercase transition-transform hover:bg-crema-2 active:scale-95 disabled:opacity-60"
          >
            {/* El estado "buscando" se calculaba y no se mostraba: el GPS puede
                tardar ocho segundos y el botón se veía muerto todo ese rato. */}
            {ubicacion.estado === "buscando" && <Girador className="h-3 w-3" />}
            {ubicacion.estado === "buscando"
              ? "Buscando tu ubicación..."
              : ubicacion.estado === "lista"
                ? "Ubicación lista ✓"
                : "Usar mi ubicación actual"}
          </button>
          {ubicacion.estado === "error" && (
            <p className="text-xs text-rojo">
              No pudimos obtener tu ubicación. Actívala para cotizar el delivery.
            </p>
          )}
        </section>
      ) : (
        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-bold uppercase text-humo">Local para recoger</h2>
          <select
            value={sucursalId}
            onChange={(e) => setSucursalId(e.target.value)}
            className="rounded border-2 border-negro px-3 py-2"
          >
            {sucursales.map((s) => (
              <option key={s.id} value={s.id}>
                {s.nombre} — {s.direccion}
              </option>
            ))}
          </select>
        </section>
      )}

      {cotizacion && (
        <p className="rounded border-2 border-verde bg-crema-2 px-3 py-2 text-sm">
          Listo en {cotizacion.eta_min}–{cotizacion.eta_max} min
          {cotizacion.costo_delivery && ` · Delivery S/ ${cotizacion.costo_delivery}`}
        </p>
      )}

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-bold uppercase text-humo">Contacto</h2>
        <CamposContacto nombre={nombre} telefono={telefono} onNombre={setNombre} onTelefono={setTelefono} />
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-bold uppercase text-humo">Comprobante</h2>
        <CamposComprobante
          numeroDocumento={numeroDocumento}
          razonSocial={razonSocial}
          onDocumento={setNumeroDocumento}
          onRazonSocial={setRazonSocial}
        />
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-bold uppercase text-humo">Cómo pagas</h2>
        <div className="flex gap-2">
          {(["efectivo", "izipay"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMedioPago(m)}
              className={`flex-1 rounded border-2 border-negro py-2 font-bold uppercase ${
                medioPago === m ? "bg-verde text-negro" : "bg-white"
              }`}
            >
              {m === "efectivo" ? "Efectivo" : "Izipay"}
            </button>
          ))}
        </div>
        {efectivoSinCuenta && (
          <p className="rounded border-2 border-rojo bg-crema-2 px-3 py-2 text-sm">
            Para pagar en efectivo necesitas una cuenta: así podemos responder por tu pedido.{" "}
            <Link href="/cuenta/registro" className="font-bold text-verde underline">
              Regístrate (tu carrito se guarda)
            </Link>{" "}
            o paga con Izipay.
          </p>
        )}
      </section>

      <div className="flex items-center justify-between border-t-2 border-negro pt-4">
        <span className="font-bold uppercase">Total</span>
        <span
          className="flex items-center gap-2 font-display text-2xl text-verde"
          aria-busy={cotizando}
        >
          {/* Mientras se recalcula el delivery el número cambia solo: el giro
              avisa que todavía no es el definitivo. */}
          {cotizando && <Girador className="h-4 w-4 text-humo" />}
          S/ {(total + Number(cotizacion?.costo_delivery ?? 0)).toFixed(2)}
        </span>
      </div>

      {error && (
        <p role="alert" className="text-sm text-rojo">
          {error}
        </p>
      )}

      <button
        type="button"
        disabled={enviando || !nombre || !telefono || efectivoSinCuenta}
        aria-busy={enviando}
        onClick={() => {
          vibrar(15);
          void confirmar();
        }}
        className="sombra-dura flex items-center justify-center gap-2 rounded bg-verde px-4 py-3 font-bold uppercase text-negro hover:bg-verde-hover disabled:opacity-50"
      >
        {enviando && <Girador />}
        {enviando ? "Confirmando..." : "Confirmar pedido"}
      </button>
    </div>
  );
}
