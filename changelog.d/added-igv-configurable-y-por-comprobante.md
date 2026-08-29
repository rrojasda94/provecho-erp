- **El IGV se elige, y una operación puntual puede apartarse del régimen de la
  empresa** (2026-08-29, ADR-080 enmendada). El régimen estaba deducido de
  `empresa.zona_tributaria` con la misma línea copiada en dos sitios —el
  asiento contable y el comprobante electrónico—, así que no había dónde
  elegirlo y no había forma de registrar el caso que ocurre todos los meses:
  Grupo Majambo vende exonerado por Amazonía y aun así **compra con IGV** a
  proveedores de fuera de la región. Ese crédito fiscal no aparecía en ningún
  lado. Ahora el régimen lo decide un solo lugar (`src/shared/tributos.py`) en
  tres niveles: la casilla de la operación, el default de la empresa —un
  select nuevo en Organización → Empresas— y, si nadie eligió nada, la zona
  tributaria, que es lo que se venía haciendo. Ninguna empresa existente
  cambia de régimen al desplegar.
- **El IGV se reconoce con el comprobante, no con la operación.** La venta al
  confirmarse y la compra al recibirse asientan sin IGV; lo asientan el
  comprobante emitido (débito fiscal) y la conformidad del comprobante de
  compra (crédito fiscal). Es lo que exige la norma —el crédito solo se toma
  con el comprobante válido y anotado— y de paso arregla un problema de orden
  que no tenía otra salida: el asiento salía antes de que existiera el
  documento donde se marca si la operación va gravada. Para una empresa
  exonerada los dos asientos quedan en cero y el libro no cambia.
- **El evento de comprobante emitido mandaba el total de la venta entera, no
  el de su cuenta.** Con la cuenta dividida (RN-COM-018) cada comprobante
  viajaba con el total completo, así que contabilidad habría reconocido el IGV
  una vez por comprobante sobre toda la venta. Ahora manda su propio importe.
