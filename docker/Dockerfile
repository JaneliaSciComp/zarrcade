# Zarrcade SPA - Multi-stage build
# Stage 1: Build the SPA
FROM node:20-alpine AS builder

WORKDIR /app/web

# Copy package files first for better caching
COPY web/package*.json ./
RUN npm ci

# Copy source and build
COPY web/ ./
RUN npm run build

# Stage 2: Production nginx server
FROM nginx:alpine AS production

LABEL org.opencontainers.image.source="https://github.com/JaneliaSciComp/zarrcade"
LABEL org.opencontainers.image.description="Zarrcade - Web gallery for OME-Zarr images"

# Copy built SPA from builder
COPY --from=builder /app/web/dist /usr/share/nginx/html

# Copy nginx configuration
COPY docker/nginx.conf /etc/nginx/nginx.conf

# Copy default config.json (can be overridden at runtime via volume mount)
COPY web/public/config.json /usr/share/nginx/html/config.json

# Copy icons
COPY web/public/icons /usr/share/nginx/html/icons

# Make sure everything nginx serves is readable regardless of the host file
# perms at COPY time (otherwise a restrictive host umask leaves files 0600
# and the nginx worker user gets 403 on everything).
RUN chmod -R a+rX /usr/share/nginx/html

# nginx:alpine runs any *.sh in /docker-entrypoint.d/ before starting nginx.
# envsubst ships with nginx:alpine (from the gettext package), so no extra deps.
COPY docker/entrypoint.sh /docker-entrypoint.d/20-zarrcade-config-url.sh
RUN chmod +x /docker-entrypoint.d/20-zarrcade-config-url.sh

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
