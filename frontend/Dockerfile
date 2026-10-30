FROM node:22-bookworm-slim AS build
WORKDIR /srv
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN npm ci
COPY src ./src
COPY public ./public
COPY next.config.ts tsconfig.json postcss.config.js tailwind.config.ts ./
RUN npm run lint && npm run build

FROM node:22-bookworm-slim AS runtime
WORKDIR /srv
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
COPY --from=build --chown=node:node /srv/.next/standalone ./
COPY --from=build --chown=node:node /srv/.next/static ./.next/static
COPY --from=build --chown=node:node /srv/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
