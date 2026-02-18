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

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
