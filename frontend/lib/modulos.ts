import {
  BookOpen,
  Building2,
  Calculator,
  ChefHat,
  ClipboardList,
  Factory,
  Gauge,
  Inbox,
  KeyRound,
  Megaphone,
  Package,
  Receipt,
  SlidersHorizontal,
  Users,
  type LucideIcon,
} from "lucide-react";

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
 *
 * Cada módulo declara además su **área de negocio**. No es decoración: es la
 * división con la que el grupo ya trabaja y con la que está escrita la
 * documentación (`docs/compras/`, `docs/rrhh/`…). El home agrupa por área en
 * vez de escupir doce fichas iguales. Agrupa, nada más: un color por área se
 * probó y se descartó por ADR-013 §8 — ver el bloque `--hue` de
 * `app/globals.css`.
 */

export type ClaveArea = "operacion" | "comercial" | "abastecimiento" | "administracion";

export type Area = {
  clave: ClaveArea;
  nombre: string;
  /** Qué pregunta responde el área. Se muestra bajo el título en el home. */
  resumen: string;
};

/** Orden del home: de lo que pasa ahora mismo a lo que se decide con calma. */
export const AREAS: Area[] = [
  { clave: "operacion", nombre: "Operación", resumen: "Lo que está pasando en el local ahora" },
  { clave: "comercial", nombre: "Comercial", resumen: "Lo que se vende y cómo se ofrece" },
  { clave: "abastecimiento", nombre: "Abastecimiento", resumen: "Lo que entra y lo que hay" },
  { clave: "administracion", nombre: "Administración", resumen: "Lo que se registra y se decide" },
];

export type Modulo = {
  clave: string;
  nombre: string;
  descripcion: string;
  href: string;
  /** Abre el módulo cualquier permiso que empiece así. */
  prefijoPermiso: string;
  /** Si está, manda sobre el prefijo: exige exactamente este permiso. */
  permiso?: string;
  area: ClaveArea;
  /**
   * Ícono de trazo, no emoji. El emoji no costaba dependencias, pero cada
   * sistema lo dibuja distinto —el 🍕 de una tablet Android no se parece al
   * de Windows— y en la grilla del home doce emojis de colores compiten
   * entre sí. `lucide-react` ya estaba instalado (calendario, diálogos,
   * reportes): esto no suma nada al bundle. La accesibilidad no depende del
   * ícono, que va `aria-hidden`, sino del nombre que lo acompaña.
   */
  Icono: LucideIcon;
};

export const MODULOS: Modulo[] = [
  {
    clave: "dashboard",
    nombre: "Dashboard",
    descripcion: "Ventas del día, stock bajo mínimo, cajas abiertas",
    href: "/dashboard",
    prefijoPermiso: "dashboard.",
    area: "operacion",
    Icono: Gauge,
  },
  {
    clave: "kds",
    nombre: "Cocina (KDS)",
    descripcion: "Cola de preparación y despacho por estación",
    // Igual que el PDV: pantalla completa táctil fuera del shell (ADR-013).
    href: "/kds",
    prefijoPermiso: "kds.",
    area: "operacion",
    Icono: ChefHat,
  },
  {
    clave: "produccion",
    nombre: "Producción",
    descripcion: "Órdenes de producción y consumo",
    href: "/produccion",
    prefijoPermiso: "production.",
    area: "operacion",
    Icono: Factory,
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
    area: "comercial",
    Icono: Receipt,
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
    area: "comercial",
    Icono: BookOpen,
  },
  {
    clave: "marketing",
    nombre: "Marketing",
    descripcion: "Campañas, contenido y leads",
    href: "/marketing",
    prefijoPermiso: "marketing.",
    area: "comercial",
    Icono: Megaphone,
  },
  {
    clave: "compras",
    nombre: "Compras",
    descripcion: "Proveedores y órdenes de compra",
    href: "/compras/ordenes-compra",
    prefijoPermiso: "purchases.",
    area: "abastecimiento",
    Icono: ClipboardList,
  },
  {
    clave: "inventario",
    nombre: "Inventario",
    descripcion: "Artículos, stock y movimientos",
    href: "/inventario/articulos",
    prefijoPermiso: "inventory.",
    area: "abastecimiento",
    Icono: Package,
  },
  {
    clave: "contabilidad",
    nombre: "Contabilidad",
    descripcion: "Plan de cuentas, asientos y caja",
    href: "/contabilidad",
    prefijoPermiso: "accounting.",
    area: "administracion",
    Icono: Calculator,
  },
  {
    clave: "rrhh",
    nombre: "RRHH",
    descripcion: "Trabajadores, contratos y contratación",
    href: "/rrhh/trabajadores",
    prefijoPermiso: "rrhh.",
    area: "administracion",
    Icono: Users,
  },
  {
    clave: "gerencia",
    nombre: "Gerencia",
    descripcion: "Parámetros operativos y aprobaciones",
    href: "/gerencia/parametros",
    prefijoPermiso: "gerencia.",
    area: "administracion",
    Icono: SlidersHorizontal,
  },
  {
    clave: "usuarios",
    nombre: "Usuarios",
    descripcion: "Cuentas, roles, permisos y personas",
    href: "/usuarios",
    prefijoPermiso: "users.",
    area: "administracion",
    Icono: KeyRound,
  },
  {
    clave: "organizacion",
    nombre: "Organización",
    descripcion: "Empresas, marcas, sucursales y almacenes",
    href: "/organizacion/empresas",
    // Módulo propio y no una sección de Gerencia o Usuarios: el permiso real
    // es `organizacion.gestionar`, y colgarlo de otro prefijo se lo
    // escondería justo a quien sí lo tiene.
    prefijoPermiso: "organizacion.",
    area: "administracion",
    Icono: Building2,
  },
  {
    clave: "reportes",
    nombre: "Reportes",
    // No confundir con el Dashboard: allá se *consultan* reportes bajo
    // demanda (ADR-024), acá se ve lo que el ERP *emite* solo y a quién le
    // llega (ADR-033).
    descripcion: "Qué reporta el ERP, a quién le llega y qué se entregó",
    href: "/reportes",
    prefijoPermiso: "reports.",
    area: "administracion",
    Icono: Inbox,
  },
];
