import { ModuloShell } from "@/components/shell/modulo-shell";
import { MODULOS } from "@/lib/modulos";

/**
 * Catálogo comercial: qué se vende y de qué está hecho.
 *
 * Módulo aparte del punto de venta a propósito. Quien cobra usa la carta;
 * quien la arma decide el costo y el margen del negocio, y son dos
 * responsabilidades distintas aunque compartan el backend `sales`. El gate
 * es el permiso exacto `sales.gestionar_catalogo` (ver `lib/modulos.ts`),
 * el mismo que la API exige para escribir: un cajero no ve el módulo ni
 * entrando por URL.
 */
const modulo = MODULOS.find((m) => m.clave === "catalogo")!;

export default function CatalogoLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModuloShell modulo={modulo}>
      {children}
    </ModuloShell>
  );
}
