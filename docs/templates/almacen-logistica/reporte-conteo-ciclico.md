<!-- Plantilla: Reporte de conteo cíclico | Módulo Almacén-Logística | Ver README.md para convención de campos -->
<!-- Uso: SOP conteo-ciclico-almacen-central. -->

# REPORTE DE CONTEO CÍCLICO

**Zona/categoría contada:** [[ COMPLETAR ]] · **Fecha:** {{ hoy }} ·
**Contado por:** {{ emisor.nombres }} {{ emisor.apellidos }}

## Detalle de conteo

| Artículo | Stock sistema | Stock físico contado | Diferencia | ¿Dentro de margen? |
|---|---|---|---|---|
| [[ COMPLETAR ]] | [[ ]] | [[ ]] | [[ ]] | ☐ Sí ☐ No |
| [[ COMPLETAR ]] | [[ ]] | [[ ]] | [[ ]] | ☐ Sí ☐ No |

## Diferencias fuera de margen

**Artículos con diferencia fuera de margen:** [[ COMPLETAR ]] — pasan a
[ficha-ajuste-inventario.md](ficha-ajuste-inventario.md).

## Cierre

**Total de artículos contados:** [[ ]] · **Total con diferencia:** [[ ]] ·
**Ajustes generados (dentro de margen):** [[ ]]

---

<sub>Conteo debe hacerse sin ver el stock esperado primero (RN-INV-005).
Diferencia fuera de margen no se ajusta directo, pasa por
ficha-ajuste-inventario.md.</sub>
