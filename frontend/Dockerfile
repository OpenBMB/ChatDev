# ---- Dependencies: install node_modules once (cached) ----
FROM node:24-alpine AS deps
WORKDIR /app
COPY package*.json ./
# Prefer reproducible installs; fall back if no lockfile
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

# ---- Dev runtime: hot-reload server ----
FROM node:24-alpine AS dev
WORKDIR /app
ENV NODE_ENV=development
COPY --from=deps /app/node_modules /app/node_modules
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]

# ---- Build: create production assets ----
FROM node:24-alpine AS build
WORKDIR /app
ENV NODE_ENV=production
ARG VITE_API_BASE_URL=http://backend:6400
ENV VITE_API_BASE_URL=""
COPY --from=deps /app/node_modules /app/node_modules
COPY . .
RUN npm run build

# ---- Prod runtime: serve static dist with nginx ----
FROM nginx:alpine AS prod
# For SPA deep links you might add a custom nginx.conf with index.html fallback.
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
