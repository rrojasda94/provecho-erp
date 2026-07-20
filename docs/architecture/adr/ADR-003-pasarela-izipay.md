# ADR-003 — Pasarela de pago: Izipay

- Estado: aceptado
- Fecha: 2026-07-04

## Contexto

El ERP necesita cobrar con tarjeta y links de pago en Perú. Candidatas:
Izipay y Mercadopago.

## Decisión

**Izipay** (decisión del negocio). Procesador local peruano, integración
directa con POS físicos ya usados en los locales.

## Consecuencias

- Adaptador único en `src/shared/integrations/izipay/` implementando el puerto
  de pagos del módulo `sales`.
- El puerto de pagos queda agnóstico: si a futuro se agrega otro proveedor,
  se implementa otro adaptador sin tocar el dominio.
- Variables `IZIPAY_*` en `.env`; webhooks de Izipay validados por firma.
