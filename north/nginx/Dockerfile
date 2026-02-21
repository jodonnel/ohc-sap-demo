FROM nginxinc/nginx-unprivileged:1.27-alpine

# Build context is north/ — stage/ and assets/ are relative to that
COPY stage/ /var/www/html/
COPY assets/ /var/www/html/assets/

# Ensure all static files are world-readable
USER root
RUN chmod -R 644 /var/www/html && find /var/www/html -type d -exec chmod 755 {} +
USER nginx

EXPOSE 8080
