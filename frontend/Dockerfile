FROM node:22-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173

# Servidor de desarrollo de Vite (el proxy /api -> backend se configura en vite.config.js)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
