### Added

- **El PDV trae el nombre del cliente de RENIEC o SUNAT, y el largo decide a
  cuál.** El botón «Buscar DNI / RUC» aparece en los dos puntos donde caja
  identifica a alguien que todavía no está registrado: al crear el cliente y al
  pedir el documento del comprobante. Un número de 8 dígitos va a RENIEC y trae
  nombre y fecha de nacimiento; uno de 11 va a SUNAT y trae razón social y
  domicilio fiscal — el mismo largo que ya decidía boleta o factura
  (RN-CPP-003). Antes el cajero escribía la razón social de oído y SUNAT
  rechazaba la que no coincidía.
- El campo de documento del alta en caja acepta ahora las dos cosas (era solo
  DNI): con 11 dígitos el cliente nace jurídico, que es lo que el servidor ya
  hacía y la pantalla no dejaba pedir.
- **RRHH → Contratación también trae el nombre de RENIEC.** La ficha del
  trabajador nacía con el nombre que el candidato escribió de sí mismo en el
  formulario público, y es el nombre con el que se firma el contrato y se
  declara a SUNAT. Ahora el diálogo de contratar muestra nombres y apellidos
  editables con «Buscar por DNI» al lado, y el servidor aplica RENIEC aunque
  nadie lo apriete (RN-PTS-004, mismo criterio que el alta de cliente y de
  proveedor).

Prellena, no decide: todo lo traído queda editable, y sin `FACTILIZA_TOKEN` —o
con el proveedor caído— el aviso manda a completar a mano y la venta o la
contratación siguen (ADR-005, ADR-041). El botón solo se le ofrece a quien
tiene `consulta.documento`: cada consulta gasta cuota de un proveedor pago.

### Fixed

- **La consulta de documento usaba el token equivocado.** Emisión y consulta
  son dos productos de Factiliza con **dos credenciales distintas**, y el ERP
  mandaba el de emisión a los dos hosts: contra `api.factiliza.com` eso es un
  401 aunque el token esté vigente, así que el botón «Buscar» nunca podía
  funcionar. Nueva variable `FACTILIZA_CONSULTA_DOCUMENTO_TOKEN`; sin ella se
  cae al de emisión, como antes.
- **Un token rechazado ya no se reporta como «respuesta ilegible».** El 401
  llega con el cuerpo vacío y caía en el parseo de JSON, que mandaba a buscar
  un error de formato donde lo que hay que revisar es la credencial.
