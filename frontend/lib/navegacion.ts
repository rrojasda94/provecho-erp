import { MODULOS } from "./modulos.ts";
import { puedeVerModulo } from "./permisos.ts";

/**
 * Segundo nivel de navegación: las pantallas de cada módulo.
 *
 * Vivía copiado dentro de los trece `app/(app)/<modulo>/layout.tsx`, uno por
 * archivo. Mientras el único consumidor era el sidebar daba igual; con la
 * paleta de comandos y el rastro leyendo lo mismo, tres copias de la verdad
 * se desincronizan en la primera pantalla que alguien agregue — y el síntoma
 * sería que la pantalla nueva existe pero no se puede buscar.
 *
 * El orden de cada lista es el del sidebar, y no es alfabético: es el orden
 * en que se trabaja.
 */
export type ItemSubmenu = { label: string; href: string };

export const SUBMENUS: Record<string, ItemSubmenu[]> = {
  catalogo: [
    { label: "Productos", href: "/catalogo/productos" },
    { label: "Atributos", href: "/catalogo/atributos" },
    { label: "Recetas", href: "/catalogo/recetas" },
    { label: "Medios de pago", href: "/catalogo/medios-pago" },
  ],
  compras: [
    { label: "Órdenes de compra", href: "/compras/ordenes-compra" },
    { label: "Proveedores", href: "/compras/proveedores" },
  ],
  contabilidad: [
    { label: "Asientos", href: "/contabilidad" },
    { label: "Periodos", href: "/contabilidad/periodos" },
    { label: "Plan de cuentas", href: "/contabilidad/plan-cuentas" },
    { label: "Comprobantes", href: "/contabilidad/comprobantes" },
    { label: "Pagos a proveedor", href: "/contabilidad/pagos" },
    { label: "Caja", href: "/contabilidad/caja" },
  ],
  gerencia: [
    { label: "Parámetros", href: "/gerencia/parametros" },
    { label: "Delivery", href: "/gerencia/delivery" },
    { label: "Tiempos del KDS", href: "/gerencia/kds" },
    { label: "Decisiones", href: "/gerencia/decisiones" },
    { label: "Divisas", href: "/gerencia/divisas" },
  ],
  inventario: [
    // Primero lo que se hace todos los días: pedir y contar.
    { label: "Requerimientos", href: "/inventario/solicitudes" },
    { label: "Conteos", href: "/inventario/conteos" },
    { label: "Artículos", href: "/inventario/articulos" },
    { label: "Categorías", href: "/inventario/categorias" },
    { label: "Unidades de medida", href: "/inventario/unidades-medida" },
    { label: "Lotes", href: "/inventario/lotes" },
    { label: "Ajustes", href: "/inventario/ajustes" },
    { label: "Devoluciones", href: "/inventario/devoluciones" },
  ],
  marketing: [
    { label: "Campañas", href: "/marketing" },
    { label: "Contenido", href: "/marketing/contenido" },
  ],
  organizacion: [
    { label: "Empresas", href: "/organizacion/empresas" },
    { label: "Marcas", href: "/organizacion/marcas" },
    { label: "Sucursales", href: "/organizacion/sucursales" },
    // Después de Sucursales porque es el paso siguiente: un local sin caja no
    // vende — el PDV arranca pidiendo el punto de venta (ADR-059).
    { label: "Puntos de venta", href: "/organizacion/puntos-venta" },
    { label: "Almacenes", href: "/organizacion/almacenes" },
  ],
  produccion: [{ label: "Órdenes", href: "/produccion" }],
  reportes: [
    { label: "Mis reportes", href: "/reportes" },
    { label: "Escalamientos", href: "/reportes/escalamientos" },
    { label: "Distribución", href: "/reportes/distribucion" },
    { label: "Emitidos", href: "/reportes/emitidos" },
  ],
  rrhh: [
    { label: "Contratación", href: "/rrhh/contratacion" },
    { label: "Trabajadores", href: "/rrhh/trabajadores" },
    { label: "Turnos", href: "/rrhh/turnos" },
    // El dispositivo autorizado a marcar por un local (ADR-073) — separado
    // de Turnos porque lo que se administra acá es la tablet, no el
    // horario laboral.
    { label: "Terminales", href: "/rrhh/terminales" },
    // El pad es pantalla completa fuera del shell, como el PDV: se abre en
    // la tablet del local con la cuenta del terminal, no desde acá. El
    // enlace existe para poder probarlo y dejarlo en favoritos.
    { label: "Pad de asistencia", href: "/asistencia" },
  ],
  usuarios: [
    { label: "Cuentas", href: "/usuarios" },
    { label: "Roles", href: "/usuarios/roles" },
    // Personas vive acá y no en RRHH porque no es solo el legajo: es la ficha
    // única que comparten trabajador, proveedor natural y cliente (RN-GEN-007),
    // y su backend es `users`.
    { label: "Personas", href: "/usuarios/personas" },
  ],
  ventas: [
    { label: "Jornada", href: "/ventas" },
    { label: "Clientes", href: "/ventas/clientes" },
    // Configurar el salón, no la identidad fiscal del local — eso es
    // "Puntos de venta" en Organización (ADR-059).
    { label: "Mesas", href: "/ventas/mesas" },
    // Las que se aplican solas (ADR-076). El cupón de la landing y el
    // descuento manual de caja son otra cosa y no viven acá.
    { label: "Promociones", href: "/ventas/promociones" },
    { label: "Abrir el PDV", href: "/pdv" },
  ],
};

export type Destino = {
  href: string;
  /** Lo que se busca: "Proveedores". */
  titulo: string;
  /** Dónde vive: "Compras". Desambigua "Clientes" de Ventas y de Marketing. */
  modulo: string;
  /**
   * Clave del módulo, no su `Icono`. Un componente no cruza la frontera
   * servidor→cliente: React serializa el árbol de props y una función no es
   * serializable ("Functions cannot be passed directly to Client
   * Components"). La paleta resuelve el ícono desde `MODULOS`, que importa
   * directo y por eso viaja en su propio bundle.
   */
  clave: string;
};

/**
 * Todo lo que la paleta de comandos puede abrir, ya filtrado por permiso.
 *
 * Se arma en el servidor y se manda al cliente: los permisos del usuario no
 * viajan al navegador más de lo que ya viajan, y la lista completa son ~50
 * entradas estáticas — no hay nada que buscar contra la API.
 */
export function destinos(permisos: string[]): Destino[] {
  return MODULOS.filter((m) => puedeVerModulo(permisos, m)).flatMap((m) => {
    const propio: Destino = {
      href: m.href,
      titulo: m.nombre,
      modulo: "Módulo",
      clave: m.clave,
    };
    const hijos = (SUBMENUS[m.clave] ?? [])
      // La entrada del módulo ya lleva a su primera pantalla; repetirla como
      // hija haría que buscar "compras" devuelva dos filas con el mismo
      // destino.
      .filter((s) => s.href !== m.href)
      .map((s) => ({ href: s.href, titulo: s.label, modulo: m.nombre, clave: m.clave }));
    return [propio, ...hijos];
  });
}
