# The web server: builds the React app, then serves it with Caddy, which also proxies /api
# to the API container and gets HTTPS certificates automatically.
# Build context: prof-rating-frontend/ (see deploy/docker-compose.yml)

# Stage 1: build the static files with Node
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: only the built files go into the final image (no Node, no node_modules)
FROM caddy:2-alpine
COPY --from=build /app/dist /srv
