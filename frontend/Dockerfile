FROM node:24.14.1-bookworm-slim@sha256:b506e7321f176aae77317f99d67a24b272c1f09f1d10f1761f2773447d8da26c
ENV NODE_ENV=production PORT=8080 STATIC_DIR=/app/dist BACKEND_URL=http://backend:8000
WORKDIR /app
COPY --chown=node:node dist /app/dist
COPY --chown=node:node server.mjs /app/server.mjs
USER node
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 CMD ["node", "-e", "fetch('http://127.0.0.1:8080/health').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"]
CMD ["node", "/app/server.mjs"]
