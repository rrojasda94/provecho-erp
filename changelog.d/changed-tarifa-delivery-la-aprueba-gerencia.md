- **La tarifa del delivery dejó de vivir en el `.env`** (2026-08-25, addendum de
  ADR-054). `DELIVERY_TARIFA_BASE`, `DELIVERY_PRECIO_POR_KM` y
  `DELIVERY_DISTANCIA_MAXIMA_KM` eran configuración de **despliegue** para algo
  que es un **precio**: cambiar cuánto cuesta un reparto exigía entrar al
  servidor por SSH, editar un archivo y reiniciar contenedores. Lo decide
  Gerencia, y Gerencia no tiene —ni debe tener— la llave del servidor. Es
  además lo que ADR-014 ya había rechazado al elegir dónde viven los valores
  operativos; a la tarifa se le escapó porque nació junto a las claves de
  Google, que sí son configuración de despliegue.

  Los tres pasan a `parametro_empresa` **por empresa**, con los códigos
  `sales/delivery_tarifa_base`, `sales/delivery_precio_por_km` y
  `sales/delivery_distancia_maxima_km`: se proponen y se aprueban en
  *Gerencia → Parámetros*, y `settings` queda como **valor de arranque** —rige
  mientras Gerencia no apruebe el suyo, mismo criterio que
  `inventory/margen_error_ajuste`. Cero migraciones, cero endpoints y cero
  pantallas nuevas: la tabla, el flujo proponer/aprobar/rechazar, el permiso
  `sales.proponer_parametro` y la pantalla genérica ya existían.

  `cotizar()` recibe la tarifa como argumento en vez de ir a buscarla a la
  configuración global — que era lo que le impedía cobrarle distinto a dos
  empresas; `tarifa_de_sucursal()` hace el salto sucursal → empresa, el mismo
  que ya hacía `sales/alertas.py`. Tres parámetros simples y no uno compuesto
  porque el formulario de propuesta arma un solo valor por vez: un compuesto
  solo se podría sembrar desde el código, justo lo contrario del objetivo.

  Costo aceptado: `DELIVERY_DISTRITOS_RESTRINGIDOS` **no** se migra —es una
  lista y el formulario no arma listas— y la tarifa sigue siendo una sola por
  empresa: dos sucursales de la misma empresa cobran igual. Los dos quedan
  anotados en la deuda del módulo.
