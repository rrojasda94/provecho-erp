"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { obtenerCarrito, totalDelCarrito, vaciarCarrito, type LineaCarrito } from "@/lib/carrito";

import { confirmarPedido, cotizarPedido, type Cotizacion } from "./actions";

export type SucursalOpcion = { id: string; nombre: string; direccion: string | null };
export type Perfil = { nombres: string; apellidos: string; telefono: string | null };
export type Direccion = {
  id: string;
  etiqueta: string | null;
  direccion: string;
  ubicacion_lat?: string | null;
  ubicacion_lng?: string | null;
};

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

function useUbicacionActual() {
  const [estado, setEstado] = useState<"inicial" | "buscando" | "lista" | "error">("inicial");
  const [coords, setCoords] = useState<{ lat: string; lng: string } | null>(null);

  function pedir() {
    if (!("geolocation" in navigator)) {
      setEstado("error");
      return;
    }
    setEstado("buscando");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({ lat: String(pos.coords.latitude), lng: String(pos.coords.longitude) });
        setEstado("lista");
      },
      () => setEstado("error"),
      { timeout: 8000 },
    );
  }

  return { estado, coords, pedir };
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
  const [lineas] = useState<LineaCarrito[]>(() => obtenerCarrito());
  const [modalidad, setModalidad] = useState<Modalidad>("delivery");
  const [sucursalId, setSucursalId] = useState(sucursales[0]?.id ?? "");
  const [direccionTexto, setDireccionTexto] = useState("");
  const [nombre, setNombre] = useState(perfil ? `${perfil.nombres} ${perfil.apellidos}` : "");
  const [telefono, setTelefono] = useState(perfil?.telefono ?? "");
  const [medioPago, setMedioPago] = useState<MedioPago>("efectivo");
  const [numeroDocumento, setNumeroDocumento] = useState("");
  const [razonSocial, setRazonSocial] = useState("");
  const [cotizacion, setCotizacion] = useState<Cotizacion | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  const ubicacion = useUbicacionActual();

  const total = useMemo(() => totalDelCarrito(lineas), [lineas]);

  useEffect(() => {
    const promesa =
      modalidad === "takeout" && sucursalId
        ? cotizarPedido({ modalidad: "takeout", sucursal_id: sucursalId })
        : modalidad === "delivery" && ubicacion.coords
          ? cotizarPedido({
              modalidad: "delivery",
              ubicacion_lat: ubicacion.coords.lat,
              ubicacion_lng: ubicacion.coords.lng,
            })
          : Promise.resolve(null);
    promesa.then(setCotizacion);
  }, [modalidad, sucursalId, ubicacion.coords]);

  function elegirDireccionGuardada(d: Direccion) {
    setDireccionTexto(d.direccion);
  }

  async function confirmar() {
    setError("");
    if (lineas.length === 0) return;
    if (modalidad === "delivery" && !ubicacion.coords) {
      setError("Comparte tu ubicación para cotizar el delivery.");
      return;
    }
    setEnviando(true);
    const resultado = await confirmarPedido({
      modalidad,
      sucursal_id: modalidad === "takeout" ? sucursalId : undefined,
      items: lineas.map((l) => ({
        producto_comercial_id: l.productoComercialId,
        cantidad: l.cantidad,
      })),
      nombre_contacto: nombre,
      telefono_contacto: telefono,
      direccion_entrega: modalidad === "delivery" ? direccionTexto : undefined,
      ubicacion_lat: modalidad === "delivery" ? ubicacion.coords?.lat : undefined,
      ubicacion_lng: modalidad === "delivery" ? ubicacion.coords?.lng : undefined,
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
    router.push(`/pedido/${resultado.pedido.id}?token=${encodeURIComponent(token)}`);
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
                  className="rounded-full border-2 border-negro px-3 py-1 text-xs font-bold"
                >
                  {d.etiqueta ?? "Dirección"}
                </button>
              ))}
            </div>
          )}
          <input
            value={direccionTexto}
            onChange={(e) => setDireccionTexto(e.target.value)}
            placeholder="Jr./Av. y número, referencia"
            required
            className="rounded border-2 border-negro px-3 py-2"
          />
          <button
            type="button"
            onClick={ubicacion.pedir}
            className="self-start rounded border-2 border-negro px-3 py-1 text-xs font-bold uppercase hover:bg-crema-2"
          >
            {ubicacion.estado === "lista" ? "Ubicación lista ✓" : "Usar mi ubicación actual"}
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
      </section>

      <div className="flex items-center justify-between border-t-2 border-negro pt-4">
        <span className="font-bold uppercase">Total</span>
        <span className="font-display text-2xl text-verde">
          S/ {(total + Number(cotizacion?.costo_delivery ?? 0)).toFixed(2)}
        </span>
      </div>

      {error && <p className="text-sm text-rojo">{error}</p>}

      <button
        type="button"
        disabled={enviando || !nombre || !telefono}
        onClick={confirmar}
        className="sombra-dura rounded bg-verde px-4 py-3 font-bold uppercase text-negro hover:bg-verde-hover disabled:opacity-50"
      >
        {enviando ? "Confirmando..." : "Confirmar pedido"}
      </button>
    </div>
  );
}
