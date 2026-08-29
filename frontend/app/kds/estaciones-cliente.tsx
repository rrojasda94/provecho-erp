"use client";

import Link from "next/link";

import { useEffect, useRef, useState } from "react";

import { ErrorApi } from "@/lib/cliente-api";
import {
  apiKds,
  type Categoria,
  type Pantalla,
  type PantallaEnvio,
  type SucursalKds,
} from "@/lib/kds";
import { Combobox } from "@/components/ui/combobox";

/**
 * Estaciones de la sucursal: es a la vez el selector de la cocina (elegir
 * en qué pantalla queda esta tablet) y la configuración de las pantallas.
 * Van juntas porque son la misma lista — separarlas obligaba a mantener dos
 * pantallas que muestran lo mismo, y quien configura una estación lo hace
 * mirando el mismo tablero que la usa.
 *
 * Crear/editar exige `kds.configurar`; la API lo valida igual, acá solo se
 * ocultan los controles (F2.28: el gate visual nunca es la autorización).
 */

const VACIA: PantallaEnvio = {
  nombre: "",
  tipo: "preparacion",
  categoria_ids: null,
  orden: 0,
};

/**
 * Elegir sucursal. Se usa dos veces y hacen cosas distintas —arriba navega a
 * otra cocina, en el diálogo muda la estación— pero el control es el mismo.
 */
function SelectorSucursal({
  id,
  valor,
  sucursales,
  onElegir,
  mostrar = true,
  nota,
}: {
  id: string;
  valor: string;
  sucursales: SucursalKds[];
  onElegir: (sucursalId: string) => void;
  /** Con una sola sucursal no hay nada que elegir. Se decide acá y no en
   * quien lo usa: son dos usos con la misma regla. */
  mostrar?: boolean;
  nota?: string;
}) {
  if (!mostrar || sucursales.length < 2) return null;
  return (
    <>
      <label className="kds-etiqueta" htmlFor={id}>
        Sucursal
      </label>
      <Combobox
        id={id}
        className="kds-campo"
        etiqueta="Sucursal"
        requerido
        value={valor}
        alCambiar={(v) => v && onElegir(v)}
        opciones={sucursales.map((s) => ({ valor: s.id, etiqueta: s.nombre }))}
      />
      {nota && <p className="kds-nota">{nota}</p>}
    </>
  );
}

type Props = {
  sucursalId: string;
  /** Las del usuario, y solo si tiene más de una. Vacío = no hay nada que
   * elegir y el selector no se dibuja. */
  sucursales: SucursalKds[];
  inicial: Pantalla[];
  categorias: Categoria[];
  puedeConfigurar: boolean;
};

export default function EstacionesCliente({
  sucursalId,
  sucursales,
  inicial,
  categorias,
  puedeConfigurar,
}: Props) {
  const [pantallas, setPantallas] = useState(inicial);
  const [editando, setEditando] = useState<Pantalla | null>(null);
  const [form, setForm] = useState<PantallaEnvio>(VACIA);
  // A qué sucursal se muda la estación que se está editando. Solo aplica al
  // editar: una pantalla nueva nace en la sucursal que se está mirando.
  const [mudarA, setMudarA] = useState(sucursalId);
  const [error, setError] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);
  const dialogo = useRef<HTMLDialogElement>(null);

  const abrir = (pantalla: Pantalla | null) => {
    setEditando(pantalla);
    setMudarA(pantalla?.sucursal_id ?? sucursalId);
    setForm(
      pantalla
        ? {
            nombre: pantalla.nombre,
            tipo: pantalla.tipo,
            categoria_ids: pantalla.categoria_ids,
            orden: pantalla.orden,
          }
        : VACIA,
    );
    setError(null);
    dialogo.current?.showModal();
  };

  const cerrar = () => dialogo.current?.close();

  // El `<dialog>` nativo se cierra con Escape sin avisar a React: sin esto,
  // reabrirlo dejaba el formulario del intento anterior.
  useEffect(() => {
    const el = dialogo.current;
    if (!el) return;
    const alCerrar = () => setEditando(null);
    el.addEventListener("close", alCerrar);
    return () => el.removeEventListener("close", alCerrar);
  }, []);

  const guardar = async () => {
    if (!form.nombre.trim()) {
      setError("El nombre es obligatorio");
      return;
    }
    setGuardando(true);
    try {
      const cuerpo: PantallaEnvio = {
        ...form,
        nombre: form.nombre.trim(),
        // [] y null significan lo mismo en la API (todas las categorías);
        // se manda null para no dejar dos representaciones del mismo caso.
        categoria_ids: form.categoria_ids?.length ? form.categoria_ids : null,
      };
      if (editando) {
        await apiKds.editarPantalla(editando.id, {
          ...cuerpo,
          // Solo si cambió: mandarlo siempre haría que la API revisara la
          // cola en cada renombre.
          ...(mudarA !== editando.sucursal_id ? { sucursal_id: mudarA } : {}),
        });
      } else {
        await apiKds.crearPantalla(sucursalId, cuerpo);
      }
      setPantallas(await apiKds.pantallas(sucursalId));
      cerrar();
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo guardar la pantalla");
    } finally {
      setGuardando(false);
    }
  };

  /** Dar de baja no borra: una pantalla inactiva deja de aparecer en cocina
   * pero conserva su historial y se puede reactivar. */
  const alternarActiva = async (pantalla: Pantalla) => {
    try {
      await apiKds.editarPantalla(pantalla.id, { activo: !pantalla.activo });
      setPantallas(await apiKds.pantallas(sucursalId));
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo cambiar la pantalla");
    }
  };

  /** Borrar sí borra: la estación se va de la lista y su nombre queda
   * libre. Se pregunta porque no tiene deshacer, y la API la rechaza si
   * todavía tiene pedidos en cola. */
  const borrar = async (pantalla: Pantalla) => {
    if (!confirm(`¿Borrar la estación «${pantalla.nombre}»?`)) return;
    try {
      await apiKds.eliminarPantalla(pantalla.id);
      setPantallas(await apiKds.pantallas(sucursalId));
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo borrar la pantalla");
    }
  };

  const alternarCategoria = (id: string) =>
    setForm((f) => {
      const actuales = f.categoria_ids ?? [];
      return {
        ...f,
        categoria_ids: actuales.includes(id)
          ? actuales.filter((c) => c !== id)
          : [...actuales, id],
      };
    });

  return (
    <main className="kds-vacio">
      <h1>Estaciones de cocina</h1>
      <p>
        Elige en qué pantalla queda esta tablet — guarda el enlace en favoritos y
        vuelve directo a su cola.
      </p>

      {/* Esta es la raíz del KDS y era la trampa: quien entraba desde el
          lanzador de módulos no tenía ningún camino de vuelta al resto del
          ERP. */}
      <p>
        <Link className="kds-salir" href="/">
          Salir del KDS
        </Link>
      </p>

      {/* Solo con más de una sucursal asignada. Navega de verdad (la lista de
          pantallas la arma el servidor) en vez de refiltrar en el cliente:
          así el enlace de favoritos de la tablet ya trae su local. */}
      <SelectorSucursal
        id="kds-sucursal"
        valor={sucursalId}
        sucursales={sucursales}
        onElegir={(id) => {
          window.location.href = `/kds?sucursal=${id}`;
        }}
      />

      {pantallas.length === 0 && (
        <p className="kds-nota">
          La sucursal todavía no tiene pantallas.
          {puedeConfigurar
            ? " Crea la primera con el botón de abajo."
            : " Pídele a un administrador que configure al menos una."}
        </p>
      )}

      <div className="kds-selector">
        {pantallas.map((p) => (
          <div key={p.id} className={`kds-selector-item ${p.activo ? "" : "inactiva"}`}>
            <a href={`/kds?pantalla=${p.id}&sucursal=${sucursalId}`}>
              <strong>{p.nombre}</strong>
              <em>
                {p.tipo === "despacho" ? "Despacho" : `Preparación · paso ${p.orden}`}
                {" · "}
                {p.categoria_ids?.length
                  ? `${p.categoria_ids.length} categoría(s)`
                  : "todas las categorías"}
                {p.activo ? "" : " · inactiva"}
              </em>
            </a>
            {puedeConfigurar && (
              <div className="kds-selector-acciones">
                <button type="button" onClick={() => abrir(p)}>
                  Editar
                </button>
                <button type="button" onClick={() => alternarActiva(p)}>
                  {p.activo ? "Desactivar" : "Activar"}
                </button>
                <button type="button" onClick={() => borrar(p)}>
                  Borrar
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      {puedeConfigurar && (
        <button type="button" className="kds-boton pri ancho" onClick={() => abrir(null)}>
          Nueva pantalla
        </button>
      )}

      <dialog ref={dialogo} className="kds-dialogo">
        <header>
          <h3>{editando ? "Editar pantalla" : "Nueva pantalla"}</h3>
          <button type="button" onClick={cerrar} aria-label="Cerrar">
            ✕
          </button>
        </header>
        <div className="kds-dialogo-cuerpo">
          <label className="kds-etiqueta" htmlFor="kds-nombre">
            Nombre
          </label>
          <input
            id="kds-nombre"
            className="kds-campo"
            value={form.nombre}
            placeholder="Horno, Barra, Despacho…"
            onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))}
          />

          <SelectorSucursal
            id="kds-mudar"
            valor={mudarA}
            sucursales={sucursales}
            onElegir={setMudarA}
            // Solo al editar: una pantalla nueva nace en la sucursal que se
            // está mirando.
            mostrar={editando !== null}
            nota="Mover la estación a otro local se lleva su configuración y su historia. Con pedidos en cola no se puede: quedarían esperando en una cocina que ya no los mira."
          />

          <p className="kds-etiqueta">Tipo</p>
          <div className="kds-chips">
            {(["preparacion", "despacho"] as const).map((tipo) => (
              <button
                key={tipo}
                type="button"
                className={`kds-chip ${form.tipo === tipo ? "on" : ""}`}
                aria-pressed={form.tipo === tipo}
                onClick={() => setForm((f) => ({ ...f, tipo }))}
              >
                {tipo === "preparacion" ? "Preparación" : "Despacho"}
              </button>
            ))}
          </div>
          <p className="kds-nota">
            Preparación ve solo los ítems pendientes de sus categorías; despacho ve el
            pedido completo y en qué estación va cada línea.
          </p>

          {form.tipo === "preparacion" && (
            <>
              <label className="kds-etiqueta" htmlFor="kds-orden">
                Paso en la cocina
              </label>
              <input
                id="kds-orden"
                className="kds-campo"
                type="number"
                min={0}
                inputMode="numeric"
                value={form.orden}
                onChange={(e) =>
                  setForm((f) => ({ ...f, orden: Math.max(0, Number(e.target.value) || 0) }))
                }
              />
              <p className="kds-nota">
                El pedido recorre las estaciones de menor a mayor: armado 0, horno 1.
                Al marcarlo acá pasa a la siguiente que atienda su categoría, y si no
                hay ninguna queda listo — una bebida se salta el horno sola. Dos
                estaciones con el mismo número trabajan en paralelo.
              </p>
            </>
          )}

          {/* Despacho no filtra: verificar el pedido completo contra la comanda
              (RN-CUP-004) es imposible viendo la mitad de las líneas. Ofrecer el
              selector sería un control que no hace nada. */}
          {form.tipo === "despacho" ? (
            <p className="kds-nota">
              Despacho ve el pedido completo, sin filtrar por categoría: es lo que
              permite contrastarlo contra la comanda antes de entregarlo.
            </p>
          ) : (
            <>
              <p className="kds-etiqueta">Categorías (ninguna = todas)</p>
              {categorias.length === 0 ? (
                <p className="kds-nota">
                  No se pudieron cargar las categorías; la pantalla se creará sin
                  filtro (atiende todas).
                </p>
              ) : (
                <div className="kds-chips">
                  {categorias.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      className={`kds-chip ${form.categoria_ids?.includes(c.id) ? "on" : ""}`}
                      aria-pressed={form.categoria_ids?.includes(c.id) ?? false}
                      onClick={() => alternarCategoria(c.id)}
                    >
                      {c.nombre}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}

          {error && <p className="kds-error">{error}</p>}

          <div className="kds-dialogo-pie">
            <button type="button" className="kds-boton" onClick={cerrar}>
              Cancelar
            </button>
            <button
              type="button"
              className="kds-boton pri"
              onClick={guardar}
              disabled={guardando}
            >
              {guardando ? "Guardando…" : "Guardar"}
            </button>
          </div>
        </div>
      </dialog>
    </main>
  );
}
