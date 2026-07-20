# Marco legal y tributario — Compras (Grupo Majambo, Perú)

Referencia operativa para quien ejecuta compras, sin ser contador. Cubre lo
que cambia el proceso de compra (comprobantes, detracciones, régimen
Amazonía); no reemplaza al contador para la declaración misma.

> ⚠ **No es asesoría legal/tributaria.** Montos y normas vigentes a la fecha
> de redacción — verificar con el contador ante cualquier duda (SUNAT).

## 1. Régimen Amazonía (Ley 27037)

Grupo Majambo opera en San Martín (Tarapoto), región amparada por la **Ley
de Promoción de la Inversión en la Amazonía (27037)**:

- **IGV exonerado** en compras de bienes/servicios consumidos u operados
  **dentro** de la región Amazonía.
- Compras a proveedores **fuera** de la región (ej. Lima) **sí pagan IGV** —
  el proveedor lo factura normal; la empresa no lo recupera como crédito
  fiscal del mismo modo que fuera del régimen (validar con contador caso a
  caso).
- Cada proveedor se marca en el ERP con su condición (dentro/fuera de zona)
  para que el sistema aplique el tratamiento correcto automáticamente.

## 2. Comprobante de pago obligatorio (RN-CMP-005)

Toda compra se sustenta con comprobante válido:

| Comprobante | Cuándo lo emite el proveedor |
|---|---|
| Factura electrónica | Proveedor formal con RUC, es el estándar para la mayoría de compras |
| Recibo por Honorarios Electrónico (RHE) | Proveedor persona natural que presta un servicio (ej. técnico independiente) |
| Boleta de venta | Excepcional — proveedor pequeño sin factura; no da derecho a crédito fiscal de IGV |

Sin comprobante válido, la compra no se registra ni se paga — así sea un
gasto real y urgente. Sin excepción: es la única forma de sustentar el gasto
ante SUNAT.

## 3. Detracciones (SPOT)

Ciertos insumos y servicios están sujetos al **Sistema de Pago de
Obligaciones Tributarias (SPOT/detracciones)**: el comprador deposita un
porcentaje del precio en una cuenta del proveedor en el Banco de la Nación,
**antes** de usar el comprobante para sustentar costo/gasto o crédito fiscal
(RN-IMP-003).

- Aplica típicamente a: servicios de transporte de carga, servicios
  empresariales (mantenimiento, asesoría), algunos insumos agropecuarios —
  **la lista y porcentajes los define SUNAT y cambian**; el contador
  confirma qué proveedores/insumos están afectos.
- El encargado de compras marca en la OC si el ítem está sujeto a
  detracción; contabilidad ejecuta el depósito antes del uso del
  comprobante.

## 4. Plazos y forma de pago a proveedores

El grupo trabaja **mixto según proveedor**: insumos perecederos y compras
menores suelen ser al contado o contra entrega; proveedores mayoristas o
recurrentes pueden tener crédito pactado (15/30 días típico en el mercado
local — el plazo real se acuerda y registra por proveedor, no hay plazo
único de política).

- La condición de pago (contado / crédito y plazo) se define al dar de alta
  al proveedor y queda en su ficha — no se negocia distinto cada compra.
- Todo pago requiere comprobante recibido y conforme (RN-CMP-006/007);
  ningún pago sin comprobante, así el proveedor sea de confianza.

## 5. Compras centralizadas

Toda compra externa a proveedor entra por **Almacén Central** (compra
formal con OC) o por **caja chica de compras** (compra menor a proveedor
informal); ninguna sucursal compra directo a proveedor externo por su
cuenta — la distribución a sucursales sigue los SOPs ya documentados de
[Abastecimiento-Locales](../diagrams/Procesos/Logistica-Almacen/Abastecimiento-Locales/)
(fuera del alcance de esta área). Esto concentra volumen para mejor precio y
evita comprobantes duplicados o proveedores no evaluados.

## 6. Proveedores informales (mercado, supermercado)

No todo proveedor puede recibir una OC formal (verdulero de mercado,
compra puntual en supermercado). Para estos:

- No se emite OC; la compra se hace directo, al contado, contra
  **boleta o factura** (RN-CMP-005 sigue aplicando: sin comprobante no hay
  gasto sustentado).
- Se paga con la **caja chica de compras** (ver §7) — no con dinero
  personal del encargado a reembolsar después, salvo excepción documentada.
- Igual se registra en el ERP como compra (proveedor genérico o
  identificado por RUC/nombre si lo declara), para que quede en el
  historial de gasto y en la evaluación de gasto por categoría.

## 7. Caja chica de compras

Fondo fijo en efectivo para compras menores que no justifican el ciclo
completo de cotización/OC (mercado, ferretería, imprevistos operativos).

- Monto del fondo: [[ COMPLETAR: definir con administración/contabilidad ]].
- Cada gasto sale con su comprobante (boleta/factura) a nombre de la
  empresa — nunca sin comprobante, así sea un monto pequeño.
- **Rendición semanal a Contabilidad**: comprobantes + reposición del
  fondo al monto fijo original. Sin rendición, no hay reposición.
- Contabilidad concilia la rendición contra el fondo entregado y contra los
  registros de compra en el ERP.
- **Faltante no sustentado**: Contabilidad reporta a RRHH con el monto y el
  responsable; tras derecho a descargo, RRHH emite memorándum y aplica
  descuento por planilla del monto faltante (RN-CMP-017). Reincidencia
  (2+ veces) puede escalar a carta de amonestación (RN-RRHH-004). Ver
  detalle en el SOP
  [rendicion-caja-chica](../diagrams/Procesos/Compras/Caja-Chica/rendicion-caja-chica.md).

## 8. Selección de proveedores — criterios mínimos

- RUC activo y habido en SUNAT (se verifica en la consulta pública de RUC
  antes del alta — evita comprar a un proveedor con RUC de baja/no habido,
  que invalida el comprobante).
- Capacidad de emitir el comprobante que corresponde (factura si se necesita
  crédito fiscal). Proveedor informal (mercado/supermercado): solo
  boleta/factura simple, va por caja chica (§6).
- Para insumos alimentarios: registro sanitario/habilitación vigente cuando
  la norma lo exige (DIGESA/SENASA según el insumo).

## 9. Compra de activos y equipamiento

Además de insumos, el encargado de compras busca y negocia **equipamiento y
otros activos** (hornos, mobiliario, equipos de cocina, tecnología, etc.):

- El área que necesita el activo define el requerimiento (qué necesita y
  para qué); compras traduce eso en especificación técnica comparable entre
  proveedores.
- Toda compra de activo pasa por cotización comparativa (mínimo 2
  proveedores) — nunca por el camino simplificado de proveedor de confianza,
  por ser compras infrecuentes y de monto alto.
- **Gerencia valida** características y precio antes de aprobar la OC —
  además de la aprobación por umbral (RN-CMP-008), aquí valida también que
  la especificación responda a la necesidad real del área.
- El activo adquirido se registra como Activo No Corriente en el ERP (no
  como insumo), con su vida útil y frecuencia de mantenimiento
  (RN-MNT-001).

## 10. Quién hace qué

| Rol | Responsabilidad |
|---|---|
| **Encargado de compras** | Ejecuta todo el ciclo: proveedores, cotización, OC, seguimiento de recepción, sustento del comprobante, caja chica de compras. Busca y negocia activos/equipamiento. |
| **Administrador/gerente** | Aprueba OC sobre el umbral (RN-CMP: `purchases.aprobar`, monto
  [[ COMPLETAR: definir umbral en soles ]]); autoriza altas de proveedores nuevos; valida especificación y precio de activos/equipamiento junto al área solicitante. |
| **Almacén central** | Recibe físicamente, verifica cantidad/calidad contra la OC. |
| **Contabilidad** | Valida comprobantes, ejecuta detracciones, aplica tratamiento IGV Amazonía, **ejecuta el pago al proveedor** en el plazo indicado, concilia la rendición semanal de caja chica. |
| **Contador externo** | Declaración tributaria (PLAME, IGV/Renta) a partir de lo registrado por Contabilidad. |

## Referencias

- SOPs del área: [docs/diagrams/Procesos/Compras/](../diagrams/Procesos/Compras/)
- Plantillas: [docs/templates/compras/](../templates/compras/)
- Reglas de negocio: RN-CMP-*, RN-MNT-*, RN-RPT-*, RN-IMP-003 en [business-rules.md](../domain/business-rules.md)
- Spec técnica del módulo: [src/modules/purchases/README.md](../../src/modules/purchases/README.md)
