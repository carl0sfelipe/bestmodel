# web-next images for the nonprod stacks (dev/stag).
# Build context: repo root.
#
#   # stag: built image of a commit (runner stage), revision stamped in a label
#   docker build -f infra/docker/web-next.Dockerfile --target runner \
#     --build-arg REVISION=$(git rev-parse --short=12 HEAD) -t bestmodel-web:latest .
#
#   # dev: live dev server (devlive stage); deploy/docker-compose.devlive.yml
#   # bind-mounts the repo read-only at /repo
#   docker build -f infra/docker/web-next.Dockerfile --target devlive -t bestmodel-web:devlive .
#
# The root .dockerignore keeps the host node_modules out of the context, so the
# install below is the only one the stages ever see.

# deps: install the exact dependency set from the lockfile.
FROM node:22-alpine AS deps
WORKDIR /repo/apps/web-next
COPY apps/web-next/package.json apps/web-next/package-lock.json ./
RUN npm ci --no-audit --no-fund

# devlive: `next dev` over a read-only bind mount of the repo at /repo, so
# edits are visible in seconds. The overlay mounts anonymous volumes at
# node_modules (seeded from this image's install, which therefore wins over
# the read-only bind) and at .next (writeable compile cache).
FROM deps AS devlive
EXPOSE 3000
CMD ["npx", "next", "dev", "-H", "0.0.0.0", "-p", "3000"]

# builder: `next build` over exactly the files the app reads:
#   - apps/web-next (incl. public/data/derived/*.json, the catalog data that
#     lib/engine.ts imports, and content/blog, read at request time)
#   - docs/agent-quickstart.md, rendered verbatim by /cli
# API_ORIGIN is read by next.config.ts at build time (the /v1/* rewrite is
# baked into .next), so it must match what the gate routes to at runtime.
FROM deps AS builder
ENV API_ORIGIN=http://api:8000 \
    NEXT_TELEMETRY_DISABLED=1
COPY apps/web-next/ /repo/apps/web-next/
COPY docs/agent-quickstart.md /repo/docs/agent-quickstart.md
RUN npm run build

# runner: minimal `next start` image, non-root, stamped with its revision.
FROM node:22-alpine AS runner
ARG REVISION=unknown
LABEL org.opencontainers.image.revision=${REVISION}
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1
RUN addgroup -S nodejs && adduser -S nextjs -G nodejs
WORKDIR /repo/apps/web-next
COPY --from=builder --chown=nextjs:nodejs /repo/apps/web-next/node_modules ./node_modules
COPY --from=builder --chown=nextjs:nodejs /repo/apps/web-next/.next ./.next
COPY --from=builder --chown=nextjs:nodejs /repo/apps/web-next/public ./public
COPY --from=builder --chown=nextjs:nodejs /repo/apps/web-next/content ./content
COPY --from=builder --chown=nextjs:nodejs /repo/apps/web-next/package.json ./package.json
COPY --from=builder --chown=nextjs:nodejs /repo/docs/agent-quickstart.md /repo/docs/agent-quickstart.md
USER nextjs
EXPOSE 3000
CMD ["npx", "next", "start", "-p", "3000"]
