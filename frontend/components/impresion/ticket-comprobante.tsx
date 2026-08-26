"use client";

import type { Encabezado, TicketComprobante, TicketTexto } from "./tipos";

/** Sin símbolo: en el rollo de 80 mm cada columna de ítems que gana el
 * "S/ " se la quita a la descripción, y la moneda ya está dicha en los
 * totales y en la leyenda de monto en letras. */
const importe = (monto: string) =>
  Number(monto).toLocaleString("es-PE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

const soles = (monto: string) => `S/ ${importe(monto)}`;

/** Cantidades: `1` y no `1.000`, `0.5` y no `0.500`. */
const cantidad = (valor: string) => String(Number(valor));

const fechaHora = (iso: string) =>
  new Date(iso).toLocaleString("es-PE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

/** Membrete común a los tres documentos que salen del rollo. El logo se
 * sirve de `public/marcas/` y su ruta la configura la marca; si no hay,
 * queda el nombre, que es lo que importa. */
export function Membrete({ encabezado }: { encabezado: Encabezado }) {
  return (
    <header className="tk-membrete">
      {encabezado.logo ? (
        // eslint-disable-next-line @next/next/no-img-element -- `next/image`
        // optimiza para pantalla; acá el destino es una impresora térmica en
        // blanco y negro y el archivo ya es un SVG de pocos kB.
        <img className="tk-logo" src={encabezado.logo} alt={encabezado.marca} />
      ) : null}
      <strong className="tk-marca">{encabezado.marca}</strong>
      <span>{encabezado.razon_social}</span>
      <span>RUC {encabezado.ruc}</span>
      <span>{encabezado.domicilio_fiscal}</span>
      {encabezado.sucursal ? (
        <span>
          {encabezado.sucursal} — {encabezado.direccion}
        </span>
      ) : null}
      {encabezado.contacto ? <span>{encabezado.contacto}</span> : null}
    </header>
  );
}

/** El comprobante que el cliente se lleva: cabecera de marca, ítems con
 * precio, desglose de impuestos, total y el QR que exige SUNAT. */
export function TicketDeComprobante({ ticket }: { ticket: TicketComprobante }) {
  const { documento, receptor, totales } = ticket;
  return (
    <article className="tk">
      <Membrete encabezado={ticket.encabezado} />

      <div className="tk-titulo">
        <strong>{documento.titulo}</strong>
        <strong>{documento.serie_correlativo}</strong>
      </div>

      {documento.aviso ? <p className="tk-aviso">{documento.aviso}</p> : null}

      <dl className="tk-datos">
        <div>
          <dt>Fecha</dt>
          <dd>{fechaHora(documento.fecha_emision)}</dd>
        </div>
        <div>
          <dt>Cliente</dt>
          <dd>{receptor.nombre}</dd>
        </div>
        <div>
          <dt>Documento</dt>
          <dd>{receptor.num_doc}</dd>
        </div>
        {receptor.direccion && receptor.direccion !== "-" ? (
          <div>
            <dt>Dirección</dt>
            <dd>{receptor.direccion}</dd>
          </div>
        ) : null}
      </dl>

      <table className="tk-items">
        <thead>
          <tr>
            <th>Cant.</th>
            <th>Descripción</th>
            <th>P.U.</th>
            <th>Importe</th>
          </tr>
        </thead>
        <tbody>
          {ticket.items.map((item, i) => (
            <tr key={`${item.descripcion}-${i}`}>
              <td>{cantidad(item.cantidad)}</td>
              <td>{item.descripcion}</td>
              <td>{importe(item.precio_unitario)}</td>
              <td>{importe(item.importe)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <dl className="tk-totales">
        {/* Una venta exonerada (Ley 27037) no tiene gravadas ni IGV que
            mostrar, y una gravada no tiene exoneradas: se imprime la que
            existe y no las dos con un cero al lado. */}
        {Number(totales.gravadas) > 0 ? (
          <div>
            <dt>Op. gravadas</dt>
            <dd>{soles(totales.gravadas)}</dd>
          </div>
        ) : null}
        {Number(totales.exoneradas) > 0 ? (
          <div>
            <dt>Op. exoneradas</dt>
            <dd>{soles(totales.exoneradas)}</dd>
          </div>
        ) : null}
        <div>
          <dt>IGV ({cantidad(totales.igv_porcentaje)}%)</dt>
          <dd>{soles(totales.igv)}</dd>
        </div>
        <div className="tk-total">
          <dt>TOTAL</dt>
          <dd>{soles(totales.total)}</dd>
        </div>
      </dl>

      <p className="tk-letras">{totales.en_letras}</p>

      <footer className="tk-pie">
        {/* eslint-disable-next-line @next/next/no-img-element -- data: URI */}
        <img className="tk-qr" src={ticket.pie.qr_imagen} alt="Código QR SUNAT" />
        {ticket.pie.hash ? <span className="tk-hash">{ticket.pie.hash}</span> : null}
        {ticket.encabezado.pie.map((linea) => (
          <span key={linea}>{linea}</span>
        ))}
      </footer>
    </article>
  );
}

/** Comanda y precuenta: el servidor ya las armó en 48 columnas, acá solo se
 * les pone el membrete y se respetan los espacios (`<pre>`). Rearmar el
 * cuerpo en el cliente duplicaría el ruteo por estaciones y el prorrateo del
 * descuento, que ya viven en el servidor. */
export function TicketDeTexto({ ticket }: { ticket: TicketTexto }) {
  return (
    <article className="tk">
      <Membrete encabezado={ticket.encabezado} />
      <pre className="tk-texto">{ticket.texto}</pre>
    </article>
  );
}
