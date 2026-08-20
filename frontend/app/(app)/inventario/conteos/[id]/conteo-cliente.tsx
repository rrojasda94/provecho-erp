"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { tienePermiso } from "@/lib/permisos";

import {
  anularConteoAction,
  cerrarConteoAction,
  registrarCantidadesAction,
} from "../actions";

export type ItemConteo = {
  sku_id: string;
  cantidad_contada: string | null;
  /** En NULL para quien cuenta a ciegas (RN-INV-005). */
  cantidad_sistema: string | null;
  diferencia: string | null;
};

export type ConteoDetalle = {
  id: string;
  almacen_id: string;
  categoria_id: string | null;
  tipo: string;
  estado: string;
  fecha_programada: string | null;
  observacion: string | null;
  items: ItemConteo[];
};

/**
 * La grilla de la toma de inventario.
 *
 * Se cuenta **a ciegas** por defecto: el stock esperado solo viaja a quien
 * tiene `inventory.ver_stock_esperado`, así que acá simplemente no está la
 * columna. Ver el número antes de contar es lo que convierte un conteo en una
 * confirmación de lo que el sistema ya creía.
 */
export function ConteoCliente({
  conteo,
  nombreDeAlmacen,
  etiquetaDeSku,
  permisos,
}: {
  conteo: ConteoDetalle;
  nombreDeAlmacen: Record<string, string>;
  etiquetaDeSku: Record<string, string>;
  permisos: string[];
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const [pendiente, ejecutar] = useTransition();
  const [contadas, setContadas] = useState<Record<string, string>>(() =>
    Object.fromEntries(conteo.items.map((i) => [i.sku_id, i.cantidad_contada ?? ""])),
  );

  const aCiegas = conteo.items.every((i) => i.cantidad_sistema === null);
  const editable =
    conteo.estado === "abierto" && tienePermiso(permisos, "inventory.contar");

  const guardar = () => {
    setError("");
    setAviso("");
    const cantidades = Object.entries(contadas)
      .filter(([, valor]) => valor.trim() !== "")
      .map(([sku_id, cantidad]) => ({ sku_id, cantidad: cantidad.trim() }));
    ejecutar(async () => {
      const r = await registrarCantidadesAction(conteo.id, cantidades);
      if (!r.ok) return setError(r.error);
      setAviso(`Guardado: ${cantidades.length} producto(s) anotados.`);
      router.refresh();
    });
  };

  const cerrar = () => {
    setError("");
    setAviso("");
    ejecutar(async () => {
      const r = await cerrarConteoAction(conteo.id);
      if (!r.ok) return setError(r.error);
      setAviso(resumenDelCierre(r.ajustes));
      router.refresh();
    });
  };

  const sinContar = conteo.items.filter(
    (i) => (contadas[i.sku_id] ?? "").trim() === "",
  ).length;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <Cabecera
          conteo={conteo}
          almacen={nombreDeAlmacen[conteo.almacen_id] ?? "—"}
          aCiegas={aCiegas && editable}
        />
        {editable && (
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              className={CLASE_BOTON}
              onClick={guardar}
              disabled={pendiente}
            >
              Guardar lo contado
            </button>
            <button
              type="button"
              className={CLASE_BOTON}
              onClick={cerrar}
              disabled={pendiente}
            >
              Cerrar conteo
            </button>
            <Anular conteoId={conteo.id} />
          </div>
        )}
      </div>

      {/* Un conteo parcial no declara faltante lo que nadie miró: los ítems
          sin cantidad se ignoran al cerrar, y eso hay que decirlo antes. */}
      {editable && sinContar > 0 && (
        <p className="text-xs text-gray">
          {sinContar} producto(s) sin anotar. Al cerrar se ignoran: un conteo
          parcial no puede declarar faltante lo que no se miró.
        </p>
      )}

      {error && <p className="text-sm text-secondary">{error}</p>}
      {aviso && <p className="text-sm text-primary">{aviso}</p>}

      <Tabla
        items={conteo.items}
        etiquetaDeSku={etiquetaDeSku}
        aCiegas={aCiegas}
        editable={editable}
        contadas={contadas}
        setContadas={setContadas}
      />
    </div>
  );
}

/** El cierre no mueve stock: deja pedidos los ajustes, que aprueba otro. */
function resumenDelCierre(ajustes: number): string {
  return ajustes === 0
    ? "Conteo cerrado sin diferencias."
    : `Conteo cerrado. Se pidieron ${ajustes} ajuste(s), que aprueba alguien más.`;
}

function Cabecera({
  conteo,
  almacen,
  aCiegas,
}: {
  conteo: ConteoDetalle;
  almacen: string;
  aCiegas: boolean;
}) {
  return (
    <div>
      <Link href="/inventario/conteos" className="text-xs text-gray underline">
        ← Conteos
      </Link>
      <h1 className="font-heading text-xl italic uppercase text-dark">
        Toma de inventario
      </h1>
      <p className="text-xs text-gray">
        {almacen} · {conteo.categoria_id ? "una categoría" : "todo el almacén"} ·{" "}
        <span className="font-semibold">{conteo.estado}</span>
        {aCiegas ? " · a ciegas" : ""}
      </p>
    </div>
  );
}

function Tabla({
  items,
  etiquetaDeSku,
  aCiegas,
  editable,
  contadas,
  setContadas,
}: {
  items: ItemConteo[];
  etiquetaDeSku: Record<string, string>;
  aCiegas: boolean;
  editable: boolean;
  contadas: Record<string, string>;
  setContadas: React.Dispatch<React.SetStateAction<Record<string, string>>>;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[32rem] text-sm">
        <thead className="text-left text-xs uppercase text-gray">
          <tr>
            <th className="py-2">Producto</th>
            <th className="py-2">Contado</th>
            {!aCiegas && (
              <>
                <th className="py-2">Sistema</th>
                <th className="py-2">Diferencia</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <Fila
              key={item.sku_id}
              item={item}
              etiqueta={etiquetaDeSku[item.sku_id] ?? item.sku_id}
              aCiegas={aCiegas}
              editable={editable}
              valor={contadas[item.sku_id] ?? ""}
              alEscribir={(valor) =>
                setContadas((previo) => ({ ...previo, [item.sku_id]: valor }))
              }
            />
          ))}
          {items.length === 0 && (
            <tr>
              <td colSpan={4} className="py-6 text-center text-gray">
                Este almacén no tiene stock registrado de esa categoría.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function Fila({
  item,
  etiqueta,
  aCiegas,
  editable,
  valor,
  alEscribir,
}: {
  item: ItemConteo;
  etiqueta: string;
  aCiegas: boolean;
  editable: boolean;
  valor: string;
  alEscribir: (valor: string) => void;
}) {
  return (
    <tr className="border-t border-black/5">
      <td className="py-2">{etiqueta}</td>
      <td className="py-2">
        {editable ? (
          <input
            aria-label={`Contado de ${etiqueta}`}
            className="w-24"
            inputMode="decimal"
            value={valor}
            onChange={(e) => alEscribir(e.target.value)}
          />
        ) : (
          (item.cantidad_contada ?? "—")
        )}
      </td>
      {!aCiegas && (
        <>
          <td className="py-2">{item.cantidad_sistema ?? "—"}</td>
          <td className="py-2">{item.diferencia ?? "—"}</td>
        </>
      )}
    </tr>
  );
}

const CLASE_BOTON =
  "inline-flex items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/85 disabled:pointer-events-none disabled:opacity-50";

function Anular({ conteoId }: { conteoId: string }) {
  return (
    <DialogoFormulario
      titulo="Anular conteo"
      disparador="Anular"
      claseDisparador="rounded-lg border border-black/10 px-3 py-1.5 text-sm font-semibold text-secondary"
      accion={anularConteoAction.bind(null, conteoId)}
      etiquetaEnvio="Anular"
      ayuda="Cerrarlo vacío diría «se contó y no había diferencias», que es lo contrario de lo que pasó. Anularlo lo saca sin poner al día el calendario."
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Por qué se anula
        <input name="motivo" maxLength={500} placeholder="Se abrió por error" />
      </label>
    </DialogoFormulario>
  );
}
