- **BI integrado en Provecho: navegación, guest tokens y tres mejoras al
  tablero** (ADR-083, Fase D; RN-BI-007). Entrada `bi` en el home con
  permiso exacto `bi.acceder` (no por prefijo — entrar ya es un privilegio,
  mismo criterio que Catálogo). La página `/bi` es hoy un enlace a
  Superset, con `BI_URL` leída del servidor (nunca `NEXT_PUBLIC_*`, mismo
  criterio que la clave de Google Maps) y degradación explícita a "no
  configurado" mientras el droplet no exista.
- **Guest tokens para embeber, mecanismo listo y probado, sin dashboards
  reales todavía**: `src/shared/integrations/superset/client.py` (adaptador
  nuevo bajo `shared/integrations/`, con su propia cuenta de servicio de
  Superset — distinta del SSO humano de Fase B) y
  `GET /api/v1/bi/dashboards/{id}/guest-token`, protegido por `bi.acceder`
  y una whitelist explícita (`BI_DASHBOARDS_EMBEBIBLES`, vacía a propósito:
  no se inventó ningún dashboard de ejemplo). El widget de embebido del
  frontend queda pendiente hasta que existan tableros reales que apuntar.
- **Tres mejoras al tablero de ADR-024, sin tocar Superset**:
  - Filtro por marca (`marca_ids`): se resuelve a sucursales y se **une**
    con el filtro de sucursal existente, no lo reemplaza — los 14 reportes
    no cambiaron una sola línea.
  - `pie` y `area` como visuales, universales vía el valor por defecto de
    `VISUALES` — mismo Recharts que ya estaba instalado, cero dependencias
    nuevas.
  - Título de tarjeta editable: el campo ya se persistía, faltaba la UI.
- **Verificado de punta a punta en un navegador real** (Docker: Postgres +
  backend + frontend, admin/cajero1 de verdad — no solo lectura de
  código): las 5 visuales aparecen, `pie` renderiza sin romper con cero
  filas, el título se edita y persiste, el filtro de marcas aparece, `/bi`
  degrada correctamente sin configurar, y `cajero1` (sin `bi.acceder`) ve
  "Sin permiso".
- **Nota de entorno, no de código**: la primera pasada de esa verificación
  mostraba solo 3 de las 5 visuales — la causa fue que `localhost:8000`
  resolvía por IPv6 al contenedor de **otra sesión** de trabajo concurrente
  en la misma máquina, no al backend bajo prueba. Forzar IPv4
  (`API_INTERNAL_URL=http://127.0.0.1:8000`) lo resolvió; queda anotado en
  el ADR por si vuelve a pasar en un ensayo local futuro.
