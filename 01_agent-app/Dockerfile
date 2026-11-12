# Build multi-stage para Cloud Run, usando `output: "standalone"` (ver
# next.config.ts) — la imagen final solo lleva el server mínimo generado por
# Next, no node_modules completo.
#
# IMPORTANTE — variables NEXT_PUBLIC_*: Next.js las incrusta en el bundle de
# JS en BUILD TIME, no en runtime. Pasarlas como --build-arg (ver
# DEPLOYMENT.md) es obligatorio; configurarlas después como env vars de
# Cloud Run NO tiene efecto (el bundle ya quedó compilado sin ellas).
#
# Build (desde 01_agent-app/):
#   docker build \
#     --build-arg NEXT_PUBLIC_API_BASE=https://<gateway-url> \
#     --build-arg NEXT_PUBLIC_FIREBASE_API_KEY=... \
#     --build-arg NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=... \
#     --build-arg NEXT_PUBLIC_FIREBASE_PROJECT_ID=... \
#     -t <imagen> .

FROM node:22-slim AS builder
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG NEXT_PUBLIC_API_BASE
ARG NEXT_PUBLIC_FIREBASE_API_KEY
ARG NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN
ARG NEXT_PUBLIC_FIREBASE_PROJECT_ID
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_FIREBASE_API_KEY=$NEXT_PUBLIC_FIREBASE_API_KEY
ENV NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=$NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN
ENV NEXT_PUBLIC_FIREBASE_PROJECT_ID=$NEXT_PUBLIC_FIREBASE_PROJECT_ID

RUN npm run build

FROM node:22-slim AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

CMD ["node", "server.js"]
