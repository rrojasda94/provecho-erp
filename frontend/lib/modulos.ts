/**
 * Catálogo de apps del home (F2.6, ADR-013). Cada entrada es un módulo con
 * backend real — el ícono del home y el ítem de sidebar salen de aquí, no se
 * hardcodean por pantalla. El guard real vive en el `layout.tsx` de cada
 * módulo; esto decide qué se ve.
 *
 * Un módulo se abre por **prefijo** (`inventory.` — cualquier permiso del
 * área alcanza) o por **permiso exacto** (`permiso`), cuando ver el módulo
 * ya es un privilegio. Catálogo usa el segundo: un cajero tiene `sales.leer`
 * y con el filtro por prefijo terminaba viendo la lista de productos y
 * chocando con un 403 al guardar. Que la API lo rechace no basta — lo que no
 * le corresponde administrar no debería siquiera aparecerle.
 */

export type Modulo = {
  clave: string;
  nombre: string;
  descripcion: string;
  href: string;
  /** Abre el módulo cualquier permiso que empiece así. */
  prefijoPermiso: string;
  /** Si está, manda sobre el prefijo: exige exactamente este permiso. */
  permiso?: string;
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
    href: "/compras/ordenes-compra",
    prefijoPermiso: "purchases.",
    icono: "🧾",
  },
  {
    clave: "inventario",
    nombre: "Inventario",
    descripcion: "Artículos, stock y movimientos",
    href: "/inventario/articulos",
    prefijoPermiso: "inventory.",
    icono: "📦",
  },
  {
    clave: "ventas",
    nombre: "Ventas",
    descripcion: "Jornada, comprobantes y punto de venta",
    // Entra por el back-office (jornada de la sucursal) y desde su sidebar se
    // abre el PDV, que es pantalla completa táctil fuera del shell (ADR-013).
    // Al revés —tile directo al PDV— dejaba sin puerta a lo administrativo.
    href: "/ventas",
    prefijoPermiso: "sales.",
    icono: "🛒",
  },
  {
    clave: "catalogo",
    nombre: "Catálogo",
    descripcion: "Productos comerciales, variantes y recetas",
    href: "/catalogo/productos",
    prefijoPermiso: "sales.",
    // Administrar la carta es acto de supervisor, no de quien vende con
    // ella: el mismo permiso que la API exige para escribir decide acá si
    // el módulo se ve.
    permiso: "sales.gestionar_catalogo",
    icono: "🍕",
  },
  {
    clave: "kds",
    nombre: "Cocina (KDS)",
    descripcion: "Cola de preparación y despacho por estación",
    // Igual que el PDV: pantalla completa táctil fuera del shell (ADR-013).
    href: "/kds",
    prefijoPermiso: "kds.",
    icono: "🍳",
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
    href: "/rrhh/trabajadores",
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
