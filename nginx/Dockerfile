FROM nginx:alpine
# nginx:alpine entrypoint runs envsubst on /etc/nginx/templates/*.template at startup,
# substituting env vars (e.g. $ORIGIN_SECRET) into the final nginx.conf.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
