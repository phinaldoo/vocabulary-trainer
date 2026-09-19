FROM node:22.19.0-alpine3.22 AS dependencies

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts

FROM dependencies AS test
COPY frontend/ ./
CMD ["npm", "test"]

FROM dependencies AS builder
COPY frontend/ ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.31.6-alpine AS runtime

COPY --chown=nginx:nginx frontend/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=builder --chown=nginx:nginx /app/dist /usr/share/nginx/html

USER nginx
EXPOSE 8080
