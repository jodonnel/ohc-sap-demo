FROM nginxinc/nginx-unprivileged:1.27-alpine

COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY index.html /var/www/html/index.html

USER root
RUN chmod -R 644 /var/www/html && find /var/www/html -type d -exec chmod 755 {} +
USER nginx

EXPOSE 8080
