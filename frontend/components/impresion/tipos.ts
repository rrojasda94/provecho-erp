/** Contratos de impresión (ADR-066). Espejo de `sales/api/schemas.py`:
 * `EncabezadoImpresionOut` y `TicketComprobanteOut`.
 *
 * Los importes viajan como string —son `Decimal` en el servidor— y se
 * formatean para mostrar, nunca se suman en el cliente: el papel dice lo
 * mismo que el XML porque no recalcula nada. */

export type Encabezado = {
  marca: string;
  /** Ruta bajo `public/marcas/`, configurada en `marca.skins.ticket`. */
  logo: string | null;
  razon_social: string;
  ruc: string;
  domicilio_fiscal: string;
  contacto: string | null;
  sucursal: string;
  direccion: string;
  pie: string[];
};

export type TicketItem = {
  cantidad: string;
  descripcion: string;
  precio_unitario: string;
  importe: string;
};

export type TicketComprobante = {
  comprobante_id: string;
  venta_id: string | null;
  encabezado: Encabezado;
  documento: {
    tipo: string;
    titulo: string;
    serie: string;
    correlativo: number;
    serie_correlativo: string;
    fecha_emision: string;
    grupo_cobro: number;
    estado_emision: string;
    /** Franja mientras SUNAT no lo acepte; `null` cuando ya está aceptado. */
    aviso: string | null;
  };
  receptor: {
    tipo_doc: string;
    num_doc: string;
    nombre: string;
    direccion: string;
  };
  items: TicketItem[];
  totales: {
    gravadas: string;
    exoneradas: string;
    igv: string;
    igv_porcentaje: string;
    total: string;
    en_letras: string;
  };
  pie: {
    qr_texto: string;
    /** `data:image/svg+xml`. Se pinta con `<img>`, que no ejecuta nada. */
    qr_imagen: string;
    hash: string | null;
  };
};

/** Comanda de cocina y precuenta: texto plano de 48 columnas más el mismo
 * membrete. No se rearman en el cliente — el servidor ya decidió qué dice
 * cada línea y en qué orden (estaciones, restas, extras anidados). */
export type TicketTexto = {
  encabezado: Encabezado;
  texto: string;
};
