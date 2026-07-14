# Codnixy AI Trade — frontend (Next.js 16, standalone)
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Gol = URL-uri relative (/api/...) — Caddy servește frontend și backend
# de pe același domeniu, deci nu există CORS.
ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
