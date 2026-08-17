# Stage 1: Build React application using Node 20 (required for Vite 6 / Rolldown)
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm config set registry https://registry.npmmirror.com && npm config set strict-ssl false && npm install

COPY . .

# Set Vite build environment variable to use relative API endpoint
ENV VITE_API_URL=/api
RUN npm run build

# Stage 2: Serve static files with Nginx
FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
