# Multi-etapa. `dev` es lo que levanta `docker-compose.yml` (código montado,
# `next dev`); `runtime` es la imagen que se reparte en el paquete de demo
# (`docker-compose.demo.yml`): build de producción con `output: "standalone"`,
# sin dependencias de desarrollo. Son ~250 MB contra ~1.5 GB, y sobre todo no
# compila cada pantalla la primera vez que alguien la abre — con `next dev` el
# primer clic en el PDV se queda pensando varios segundos, y quien está
# probando lo lee como que el sistema es lento.
#
# node 24 es la versión con la que el job `frontend` del CI corre `next build`.
# Construir la imagen con otra sería enviar un build que nadie probó (el mismo
# error que el PR #49 con Python; lo vigila `tests/test_repo_coherencia.py`).

FROM node:24-alpine AS deps
WORKDIR /app
# Con el lock: `npm ci` instala exactamente las versiones que el repo fijó y
# que probó el CI. `npm install` sin lock resolvía los rangos de nuevo en cada
# build, así que la imagen podía traer paquetes que nadie verificó.
COPY package.json package-lock.json ./
RUN npm ci

FROM deps AS dev
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

FROM deps AS build
COPY . .
RUN npm run build

FROM node:24-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
# Sin esto el servidor de Next escucha en `localhost` DENTRO del contenedor:
# el puerto queda publicado y ninguna conexión entra.
ENV HOSTNAME=0.0.0.0
ENV PORT=3000
# `output: "standalone"` deja en `.next/standalone` el servidor con solo las
# dependencias que el runtime usa. Los estáticos quedan fuera a propósito y se
# copian aparte.
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
# Sin privilegios, igual que la imagen del backend.
USER node
EXPOSE 3000
CMD ["node", "server.js"]
