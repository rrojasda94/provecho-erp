# Node 24: el mismo runtime que corre CI (`ci.yml`, jobs `frontend` y `e2e`).
# La imagen traía node:20, que ni siquiera es la que valida los tests —
# `npm test` usa el stripping de tipos de fábrica de `node --test`, que no
# existe antes de 22.18. Dos runtimes distintos para el mismo `package.json`
# significa que lo que pasa en CI no es lo que se despliega.
FROM node:24-alpine AS deps

WORKDIR /app
# `npm ci` (no `npm install`): instala EXACTAMENTE el árbol del lockfile, el
# mismo que resolvió CI. Con `npm install` y sin copiar el lock, cada build
# resolvía los `^` a lo último publicado ese día — un major de una
# dependencia se colaba en la imagen sin pasar por un PR.
COPY package.json package-lock.json ./
RUN npm ci

# --- Desarrollo -------------------------------------------------------------
# El `web` de `docker-compose.yml` apunta acá. Monta el código encima, así
# que este COPY solo existe para que la imagen también corra suelta.
FROM deps AS dev
RUN apk add --no-cache tzdata
ENV TZ=America/Lima
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

# --- Build de producción ----------------------------------------------------
FROM deps AS builder
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# --- Runtime de producción --------------------------------------------------
# `output: "standalone"` (next.config.mjs) deja en `.next/standalone` el
# servidor con solo las dependencias que realmente se importan. La alternativa
# —arrastrar `node_modules` entero— es un orden de magnitud más de imagen y
# mete las devDependencies (Playwright, TypeScript) en producción.
FROM node:24-alpine AS runner

WORKDIR /app
# `HOSTNAME=0.0.0.0`: sin esto el server de `standalone` escucha en el
# localhost del contenedor y nada de fuera lo alcanza — el mapeo de puertos
# parece roto y no lo está.
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0 \
    TZ=America/Lima

# `tzdata` + `TZ`: las imágenes alpine no traen la base de zonas, y sin
# ella `TZ` se ignora en silencio y el proceso se queda en UTC. Importa
# porque hay pantallas que formatean la fecha en el servidor: sin zona, un
# movimiento de las 20:00 hora Perú se dibuja como la 01:00 del día
# siguiente. Es defensa en profundidad — el arreglo de verdad es el
# `timeZone` explícito de `lib/fechas.ts`, que además vale en `npm run dev`
# y en el navegador.
RUN apk add --no-cache tzdata

# Sin privilegios, igual que la imagen del backend: una vulnerabilidad en la
# aplicación no debe traer consigo root dentro del contenedor.
RUN addgroup -g 10001 provecho && adduser -D -u 10001 -G provecho provecho

COPY --from=builder --chown=provecho:provecho /app/.next/standalone ./
# `standalone` no incluye los estáticos ni las fuentes self-hosted que
# `next/font` descarga en build: van aparte o la app carga sin CSS.
COPY --from=builder --chown=provecho:provecho /app/.next/static ./.next/static

USER provecho

# `/login` y no `/`: la raíz exige sesión y responde con una redirección, que
# como señal de salud no distingue "vivo" de "roto".
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:3000/login || exit 1

EXPOSE 3000
CMD ["node", "server.js"]
