FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# Run Vite in dev mode for local development
CMD ["npm", "run", "dev", "--", "--host"]
