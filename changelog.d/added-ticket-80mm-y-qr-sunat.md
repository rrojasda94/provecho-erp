- **La boleta y la factura se imprimen desde el ERP** (2026-08-25, ADR-067). No
  había ningún modelo de comprobante: lo único imprimible era el PDF de
  Factiliza, cuyo diseño decide el proveedor y que hay que bajar y abrir en un
  visor. Ahora `GET /sales/comprobantes/{id}/ticket` devuelve la
  representación impresa para rollo de 80 mm —membrete de marca, ítems con
  precio, desglose de impuestos, total en letras y el **QR que exige SUNAT**
  (nueve campos de la RS 097-2012)— y sale **aunque SUNAT todavía no haya
  contestado**, con su franja `PENDIENTE DE ENVÍO A SUNAT`: la emisión es
  asíncrona a propósito (RN-COM-003) y hacer esperar al cliente en caja es lo
  que esa decisión evita. El ticket **no recalcula nada**: lee el mismo payload
  que se le manda a Factiliza, así que el papel y el XML no pueden discrepar en
  un céntimo de redondeo. El PDF sigue a un click y sigue siendo la copia
  formal.
- **Un solo ancho de papel: 48 columnas.** Todas las ticketeras del grupo son
  de 80 mm, pero la comanda salía a 32 columnas (58 mm) y la precuenta a 40:
  tres documentos del mismo local con tres márgenes, y un tercio del rollo en
  blanco en cocina. El ancho vive ahora en `src/shared/impresion.py` y lo
  comparten los tres, junto con el mismo membrete.
- **El membrete se configura por marca, no por local.** Logo y líneas de
  cortesía en `marca.skins["ticket"]` —la columna JSONB que ya existía para el
  branding del PDV, sin migración—; razón social, RUC, domicilio fiscal y
  sucursal salen del padrón y no se teclean: un local que escribe su propio
  encabezado termina imprimiendo el RUC de la empresa equivocada.
- **Botones de impresión donde se necesitan**: PDV → Cobrados (comprobante) y
  PDV → Cuentas (comanda, que cuenta como reimpresión y queda auditada), y una
  pestaña nueva **Contabilidad → Comprobantes** con el registro de ventas del
  día o del rango, importe, estado ante SUNAT, reimpresión y descarga de
  PDF/XML. El listado (`GET /sales/comprobantes`) acepta `sales.leer` **o**
  `accounting.leer`: el contador tiene que ver el documento fuente del asiento
  sin que haya que darle el módulo de ventas entero.
- **Impresión sin diálogo**: no es código de la aplicación sino la bandera
  `--kiosk-printing` del navegador. Documentado en
  `docs/engineering/impresion-termica.md` junto con la configuración de la
  ticketera. Sin la bandera todo funciona igual, con el diálogo de por medio.
