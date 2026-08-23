- **Paquete de demo portable** (2026-08-09). `python scripts/empaquetar_demo.py`
  arma `ZIP_<versión>/provecho-demo-<versión>.zip` con el ERP entero —imágenes
  incluidas— para que alguien lo pruebe en su PC con doble clic en un `.bat`,
  sin internet, sin servidor y sin escribir un comando. Existe porque poner el
  sistema frente a quien lo va a usar no puede depender de que esa persona
  sepa levantar un compose y correr tres seeders: el servicio `init` migra y
  siembra en cada arranque (los seeders ya eran idempotentes) y el compose de
  demo no tiene `build:` porque en esa PC no hay código fuente.
  `docker-compose.demo.yml` **no sirve para publicar nada**: sus secretos
  están versionados a propósito.
- **Imagen de producción del frontend** (`frontend/Dockerfile`, etapa
  `runtime`, con `output: "standalone"`). La única imagen que existía corría
  `npm run dev`: ~1.5 GB y compilando cada pantalla la primera vez que alguien
  la abría, que quien prueba lee como que el sistema es lento. La etapa `dev`
  se conserva y `docker-compose.yml` la pide con `target: dev`.
- **`COOKIE_SECURE`** en el frontend. La cookie de sesión seguía a `NODE_ENV`,
  así que en un build de producción servido por http —la demo abierta desde la
  tablet del local, `http://192.168.x.x:3000`— el navegador la descartaba y el
  login fallaba **en silencio**, devolviendo al formulario sin error. Sin la
  variable el comportamiento no cambia.
- **Dos coherencias más en `tests/test_repo_coherencia.py`**: que el Node de la
  imagen del frontend sea el que el CI usa para `next build` (mismo riesgo que
  ya se vigilaba con Python), y que las imágenes que nombra el compose de la
  demo sean exactamente las que el empaquetador exporta — si no, el ZIP sale
  incompleto y el tester solo ve una pantalla que no carga.
