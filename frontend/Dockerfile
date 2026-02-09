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
