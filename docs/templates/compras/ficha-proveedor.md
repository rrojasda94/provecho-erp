<!-- Plantilla: Ficha de proveedor | Módulo Compras | Ver README.md para convención de campos -->
<!-- Uso: SOP alta-y-evaluacion-proveedor. Verificar RUC en SUNAT antes de llenar. -->

# FICHA DE PROVEEDOR

**Fecha de alta:** {{ hoy }} · **Registrado por:**
{{ emisor.nombres }} {{ emisor.apellidos }}

## 1. Datos del proveedor

| Campo | Dato |
|---|---|
| Razón social | [[ COMPLETAR ]] |
| RUC | [[ COMPLETAR ]] |
| Estado SUNAT (activo/habido) | ☐ Verificado el {{ hoy }} |
| Dirección fiscal | [[ COMPLETAR ]] |
| Ubicación | ☐ Dentro de región Amazonía (San Martín) ☐ Fuera de zona |
| Contacto (nombre, teléfono, correo) | [[ COMPLETAR ]] |
| Tipo de comprobante que emite | ☐ Factura ☐ RHE ☐ Boleta |

## 2. Qué provee

| Insumo/servicio | Unidad de medida | ¿Afecto a detracción (SPOT)? |
|---|---|---|
| [[ COMPLETAR ]] | [[ ]] | ☐ Sí ☐ No |
| [[ COMPLETAR ]] | [[ ]] | ☐ Sí ☐ No |

## 3. Condiciones acordadas

| Campo | Dato |
|---|---|
| Condición de pago | ☐ Contado/contra entrega ☐ Crédito — plazo: [[ COMPLETAR: días ]] |
| Medio de pago habitual | [[ COMPLETAR: transferencia / efectivo / cheque ]] |
| Plazo de entrega típico | [[ COMPLETAR ]] |
| Pedido mínimo (si aplica) | [[ COMPLETAR ]] |

## 4. Verificaciones adicionales (según el insumo)

- ☐ Registro sanitario / habilitación DIGESA-SENASA vigente (insumos alimentarios)
- ☐ Referencias comerciales contactadas: [[ COMPLETAR: quién, cuándo ]]

## 5. Clasificación (se actualiza en cada evaluación periódica)

☐ Preferente · ☐ En observación · ☐ A reemplazar — última evaluación:
[[ COMPLETAR: fecha, ver evaluacion-proveedor.md ]]

---

<sub>Alta requiere aprobación del administrador (SOP alta-y-evaluacion-proveedor,
paso 7). Verificar condición SUNAT (RUC activo/habido) antes de cada compra
de monto alto, no solo en el alta.</sub>
