- **La remuneración de toda la plantilla se leía con solo `rrhh.leer`**
  (2026-08-30, hallazgo #6 de la auditoría backend↔frontend). El legajo
  escondía boletas y liquidaciones salvo `rrhh.nomina_gestionar`, pero
  `GET /rrhh/trabajadores` devolvía `remuneracion_base` a cualquiera con
  `rrhh.leer` — que es lo que tiene el rol `supervisor`. Esconder la nómina
  del legajo y dejar el sueldo base en el listado era censurar la puerta y
  dejar la ventana abierta. Ahora el campo viaja en `null` sin ese permiso,
  en el listado, en la ficha y en el `trabajador` embebido del legajo. Se
  censura a `null` en vez de agregar un `remuneracion_visible`: el legajo ya
  trae `nomina_visible` y era el único lugar donde hacía falta distinguir
  "no te lo muestro" de "no tiene sueldo cargado". Queda anotado en la deuda
  que el `PATCH` sigue pidiendo solo `rrhh.trabajador_gestionar`.
