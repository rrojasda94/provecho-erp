- **Módulo `supervision`: tareas de apertura/cierre, checklist y foto**
  (2026-09-17). El supervisor programa por categoría, momento
  (apertura/cierre) y frecuencia (diaria/interdiaria/semanal/mensual), con
  orden repetible para tareas en paralelo; una plantilla puede alcanzar a
  una sucursal o a toda una marca. El sistema genera la tarea del día
  automáticamente, el trabajador asignado marca su checklist y sube foto
  desde el celular — el servidor comprime la imagen y le lee la fecha EXIF
  antes de guardarla, sin confiar en lo que declare el cliente; una foto
  sin EXIF o fuera de ventana no bloquea completar, solo queda marcada para
  revisión. Al cerrar la jornada se genera un informe diario por sucursal
  que entra al catálogo centralizado de `reports` y se escala con el
  mecanismo ya existente. La foto se purga a los 30 días; la fila y el
  checklist se conservan. Costo aceptado: Pillow como dependencia nueva de
  la API, para leer EXIF y comprimir en el servidor (ADR-102).
