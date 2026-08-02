/**
 * Catálogo de apps del home (F2.6, ADR-013). Cada entrada es un módulo con
 * backend real — el ícono del home y el ítem de sidebar salen de aquí, no se
 * hardcodean por pantalla. `prefijoPermiso` decide si el módulo aparece en el
 * grid (filtro de UX, ver `lib/permisos.ts`); el guard real vive en el
 * `layout.tsx` de cada módulo.
 */

export type Modulo = {
  clave: string;
  nombre: string;
  descripcion: string;
  href: string;
  prefijoPermiso: string;
  icono: string; // emoji: cero dependencias, ya es texto accesible por defecto
};

export const MODULOS: Modulo[] = [
  {
    clave: "dashboard",
    nombre: "Dashboard",
    descripcion: "Ventas del día, stock bajo mínimo, cajas abiertas",
    href: "/dashboard",
    prefijoPermiso: "dashboard.",
    icono: "📊",
  },
  {
    clave: "compras",
    nombre: "Compras",
    descripcion: "Proveedores y órdenes de compra",
    href: "/compras/proveedores",
    prefijoPermiso: "purchases.",
    icono: "🧾",
  },
  {
    clave: "inventario",
    nombre: "Inventario",
    descripcion: "Artículos, stock y movimientos",
    href: "/inventario",
    prefijoPermiso: "inventory.",
    icono: "📦",
  },
  {
    clave: "ventas",
    nombre: "Ventas",
    descripcion: "Punto de venta y comprobantes",
    href: "/ventas",
    prefijoPermiso: "sales.",
    icono: "🛒",
  },
  {
    clave: "produccion",
    nombre: "Producción",
    descripcion: "Órdenes de producción y consumo",
    href: "/produccion",
    prefijoPermiso: "production.",
    icono: "🏭",
  },
  {
    clave: "contabilidad",
    nombre: "Contabilidad",
    descripcion: "Plan de cuentas, asientos y caja",
    href: "/contabilidad",
    prefijoPermiso: "accounting.",
    icono: "📚",
  },
  {
    clave: "rrhh",
    nombre: "RRHH",
    descripcion: "Trabajadores, contratos y contratación",
    href: "/rrhh",
    prefijoPermiso: "rrhh.",
    icono: "👥",
  },
  {
    clave: "marketing",
    nombre: "Marketing",
    descripcion: "Campañas, contenido y leads",
    href: "/marketing",
    prefijoPermiso: "marketing.",
    icono: "📣",
  },
  {
    clave: "gerencia",
    nombre: "Gerencia",
    descripcion: "Parámetros operativos y aprobaciones",
    href: "/gerencia/parametros",
    prefijoPermiso: "gerencia.",
    icono: "🏛️",
  },
  {
    clave: "usuarios",
    nombre: "Usuarios",
    descripcion: "Cuentas, roles y permisos",
    href: "/usuarios",
    prefijoPermiso: "users.",
    icono: "🔐",
  },
];
