FROM node:20-alpine

WORKDIR /app
# Con el lock: `npm ci` instala exactamente las versiones que el repo fijó y
# que probó el CI. `npm install` sin lock resolvía los rangos de nuevo en cada
# build, así que la imagen podía traer paquetes que nadie verificó.
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

EXPOSE 3000
CMD ["npm", "run", "dev"]
