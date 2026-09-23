# Node 24: mismo runtime que `frontend/Dockerfile` y que CI (`ci.yml`).
FROM node:24-alpine AS deps

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# --- Desarrollo -------------------------------------------------------------
FROM deps AS dev
RUN apk add --no-cache tzdata
ENV TZ=America/Lima
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

# --- Build de producción ----------------------------------------------------
FROM deps AS builder
COPY . .
# Fecha de esta compilación: el pie del sitio muestra su año ("© 2026"). Va acá
# y no en `runner` porque Next la congela en el bundle (`next.config.mjs`).
ARG FECHA_BUILD=""
ENV FECHA_BUILD=${FECHA_BUILD}
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# --- Runtime de producción --------------------------------------------------
FROM node:24-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0 \
    TZ=America/Lima

RUN apk add --no-cache tzdata

RUN addgroup -g 10001 provecho && adduser -D -u 10001 -G provecho provecho

COPY --from=builder --chown=provecho:provecho /app/.next/standalone ./
COPY --from=builder --chown=provecho:provecho /app/.next/static ./.next/static
COPY --from=builder --chown=provecho:provecho /app/public ./public

USER provecho

# `/salud` y no `/`: la portada llama a la API en el servidor y puede tardar
# más que el resto; el healthcheck solo pregunta "¿el proceso responde?".
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:3000/salud || exit 1

EXPOSE 3000
CMD ["node", "server.js"]
