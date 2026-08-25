- **El buscador de Google en el campo de dirección no podía encenderse nunca**,
  con clave o sin ella (ADR-053, desde 0.6.0). El `<div>` donde se monta el
  buscador solo se dibujaba si `conMapa` ya era `true`
  (`{conMapa && <div ref={buscadorRef} ... />}`), pero el efecto que activa
  `conMapa` necesita que **ese mismo `<div>`** ya exista para engancharle el
  widget (`if (!buscadorRef.current) return;`). Huevo y gallina: el
  contenedor solo aparecía cuando el mapa ya estaba encendido, y el mapa solo
  se encendía si el contenedor ya existía — nunca pasaba. Se detectó
  depurando por qué staging seguía mostrando "El mapa no está disponible" con
  la clave de Google puesta, el SDK cargando en `200` y `window.google.maps`
  poblado en la consola: el fallo no era de configuración, era del
  componente. `frontend/components/direccion/campo-direccion.tsx`: el `<div>`
  del buscador pasa a renderizarse siempre (vacío mientras el SDK no
  responde, sin ocupar espacio visible). `frontend/uso/direccion.spec.ts`
  sigue en verde: prueba a propósito el camino **sin** clave, y ese no
  cambió.
