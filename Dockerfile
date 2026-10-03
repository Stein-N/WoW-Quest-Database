# Forever Database — static site served by nginx.
#
#   git submodule update --init          # QuestieDB must be checked out
#   make docker                          # or: docker build -t wow-quest-database .
#   docker run -d -p 8080:80 --restart unless-stopped wow-quest-database
#
# The data is built inside the image: QuestieDB (from vendor/QuestieDB) is exported with
# Lua 5.1, the latest VMangos world DB snapshot is downloaded, both are merged. Map images
# come from web/static/maps in the repository.

# Stages 1 and 2 produce plain files (JSON, HTML, JS), so they always run on the build
# machine's platform; only the final nginx stage is per target platform. Multi-arch builds
# (linux/amd64 + linux/arm64) therefore need no emulation.

# ---------------------------------------------------------------- 1. data
FROM --platform=$BUILDPLATFORM python:3.12-slim AS data

# lua5.1 from Debian instead of QuestieDB's bundled x86-64 binary, so ARM build hosts work too
RUN apt-get update \
 && apt-get install -y --no-install-recommends lua5.1 make ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /src

# VMangos snapshot first: this layer stays cached until the fetch script or VMANGOS_SNAPSHOT
# changes. Pass the current snapshot name (see data-version.json) to refresh it, or build with
# --no-cache.
ARG VMANGOS_SNAPSHOT=latest
COPY etl/fetch_vmangos.py etl/fetch_vmangos.py
RUN echo "VMangos snapshot: ${VMANGOS_SNAPSHOT}" && python3 etl/fetch_vmangos.py vendor/vmangos

# AzerothCore translations (pinned commit): cached until the fetch script changes
COPY etl/fetch_azerothcore.py etl/fetch_azerothcore.py
RUN python3 etl/fetch_azerothcore.py vendor/azerothcore

COPY Makefile ./
COPY etl etl
COPY vendor/QuestieDB vendor/QuestieDB
RUN test -f vendor/QuestieDB/src/config.lua \
 || { echo "vendor/QuestieDB is empty - run 'git submodule update --init' before building"; exit 1; }

# shown on the site as the QuestieDB version (the submodule's .git is not in the build context)
ARG QUESTIE_REV=""
ENV QUESTIE_REV=${QUESTIE_REV}
RUN make questie LUA=lua5.1 && make site-data

# ---------------------------------------------------------------- 2. site
FROM --platform=$BUILDPLATFORM node:24-alpine AS site
WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web ./
COPY --from=data /src/web/static/data ./static/data
# patch notes for the start page (kept out of the data stage so editing them doesn't rebuild data)
COPY CHANGELOG.json ./static/changelog.json
RUN npm run build

# ---------------------------------------------------------------- report (CI only)
# `docker buildx build --target report --output type=local,dest=...` exports just the uiMapId
# report and the data fingerprint for the release notes, reusing the cached data stage.
FROM scratch AS report
COPY --from=data /src/web/static/data/uimap-report.json /
COPY --from=data /src/build/data-digest.json /

# ---------------------------------------------------------------- pages (CI only)
# `docker buildx build --target pages --output type=local,dest=...` exports the finished static
# site for GitHub Pages (.github/workflows/pages.yml), built exactly like the image.
FROM scratch AS pages
COPY --from=site /src/web/build /

# ---------------------------------------------------------------- 3. serve
FROM nginx:1.27-alpine
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=site /src/web/build /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=60s --timeout=5s CMD wget -qO /dev/null http://127.0.0.1/ || exit 1
