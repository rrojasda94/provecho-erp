"use client";

import { useEffect, useRef, useState } from "react";

import { ErrorApi } from "@/lib/cliente-api";
import { apiKds, type Categoria, type Pantalla, type PantallaEnvio } from "@/lib/kds";

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

const VACIA: PantallaEnvio = { nombre: "", tipo: "preparacion", categoria_ids: null };

type Props = {
  sucursalId: string;
  inicial: Pantalla[];
  categorias: Categoria[];
  puedeConfigurar: boolean;
};

export default function EstacionesCliente({
  sucursalId,
  inicial,
  categorias,
  puedeConfigurar,
}: Props) {
  const [pantallas, setPantallas] = useState(inicial);
  const [editando, setEditando] = useState<Pantalla | null>(null);
  const [form, setForm] = useState<PantallaEnvio>(VACIA);
  const [error, setError] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);
  const dialogo = useRef<HTMLDialogElement>(null);

  const abrir = (pantalla: Pantalla | null) => {
    setEditando(pantalla);
    setForm(
      pantalla
        ? {
            nombre: pantalla.nombre,
            tipo: pantalla.tipo,
            categoria_ids: pantalla.categoria_ids,
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
      if (editando) await apiKds.editarPantalla(editando.id, cuerpo);
      else await apiKds.crearPantalla(sucursalId, cuerpo);
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

      {pantallas.length === 0 && (
        <p className="kds-nota">
          La sucursal todavía no tiene pantallas.
          {puedeConfigurar
            ? " Crea la primera con el botón de abajo."
            : " Pídele a un supervisor que configure al menos una."}
        </p>
      )}

      <div className="kds-selector">
        {pantallas.map((p) => (
          <div key={p.id} className={`kds-selector-item ${p.activo ? "" : "inactiva"}`}>
            <a href={`/kds?pantalla=${p.id}`}>
              <strong>{p.nombre}</strong>
              <em>
                {p.tipo === "despacho" ? "Despacho" : "Preparación"}
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
            pedido completo cuando hay algo listo.
          </p>

          <p className="kds-etiqueta">Categorías (ninguna = todas)</p>
          {categorias.length === 0 ? (
            <p className="kds-nota">
              No se pudieron cargar las categorías; la pantalla se creará sin filtro
              (atiende todas).
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
