- **Canal de alerta por correo en `reports`** (2026-09-09, ADR-033). El
  campo `canal` de `regla_distribucion`/`entrega_reporte` existía desde el
  principio sin nada más que la bandeja detrás; `email` es el primer canal
  real, despachado por `src/shared/integrations/email/smtp.py` (SMTP puro
  stdlib, sin dependencia nueva). El correo se **suma** a la bandeja, nunca
  la reemplaza — sin `SMTP_HOST` configurado el envío se omite en silencio y
  el resto de la distribución sigue igual que antes.
