import Link from "next/link";

import { ProveedorConfigMapas } from "@/components/direccion/config-mapas";
import { configMapas } from "@/lib/mapas";

/**
 * Grupo de rutas **público**: lo que un cliente del restaurante abre desde su
 * teléfono, sin cuenta.
 *
 * A diferencia de `(app)`, este layout **no llama a `obtenerSesion()`**. No es
 * un olvido: quien escanea el QR de la mesa no es usuario del ERP y nunca va a
 * serlo, así que un guard acá lo mandaría a un login que no le sirve. El
 * layout raíz ya tolera no tener sesión (`obtenerPreferencias` devuelve los
 * valores por defecto en vez de redirigir).
 *
 * Tampoco lleva la clase `.erp`: esto no es una pantalla de trabajo. La voz es
 * la de la marca —crema y brasa, logotipo en Anton— que en el back office se
 * reservó para el PDV y el KDS (ver el bloque «mise en place» de
 * `globals.css`).
 *
 * Monta `ProveedorConfigMapas` porque el campo de dirección lo necesita: la
 * clave la lee el servidor y el contexto es cómo baja al cliente. Sin esto el
 * campo funciona igual, pero como `<input>` de texto pelado — que es también
 * lo que pasa cuando no hay clave configurada (ADR-053).
 */
export default function PublicoLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="publico">
      <ProveedorConfigMapas config={configMapas()}>{children}</ProveedorConfigMapas>
      <footer className="publico-pie">
        {/* El logo del grupo va en el pie y el de la marca arriba: el cliente
            vino por Charlie's, y Majambo es quién responde por sus datos. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/marcas/majambo.svg" alt="Grupo Majambo" className="publico-pie-logo" />
        <p className="publico-pie-legal">
          Una marca de Grupo Majambo. Operada por Inversiones Turísticas y
          Alimentarias Majambo EIRL.
        </p>
        <nav className="publico-pie-enlaces">
          <Link href="/reconocerte/terminos">Términos y condiciones</Link>
          <span aria-hidden>·</span>
          <a href="mailto:hola@majambo.com.pe">hola@majambo.com.pe</a>
        </nav>
      </footer>
    </div>
  );
}
