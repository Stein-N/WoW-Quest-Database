# WoW Quest Database — data pipeline and website.
#
#   make data      export QuestieDB, fetch VMangos, build web/static/data
#   make dev       run the website locally (http://localhost:5173)
#   make build     static site in web/build (any web server)
#   make maps      extract world maps from the local WoW clients (WOW_DIR=…)
#   make lua ARGS="--flavor forever --type quest -o export/"   export data as Lua
#   make docker    build the Docker image (nginx serving the site), see README
#   make questcache CACHE="…/Cache/WDB"   import quest texts from a WoW client cache (FLAVOR=forever)

QUESTIE  := vendor/QuestieDB
LUA      := ./tools/lua-binary/linux-x64/lua
VMANGOS  := vendor/vmangos
SQLITE   := $(VMANGOS)/sqlite-dump/mangos.sqlite
WOW_DIR  ?= $(HOME)/Games/battlenet/drive_c/Program Files (x86)/World of Warcraft

.PHONY: data submodule questie vmangos site-data dev build maps lua docker questcache clean update

data: submodule questie vmangos site-data

submodule:
	git submodule update --init $(QUESTIE)

# LUA can be overridden with any Lua 5.1 interpreter (the Docker build uses lua5.1)
questie:
	mkdir -p build/questie/classic build/questie/forever
	cd $(QUESTIE) && $(LUA) ../../etl/questie_export.lua Vanilla ../../build/questie/classic
	cd $(QUESTIE) && $(LUA) ../../etl/questie_export.lua Forever ../../build/questie/forever

vmangos: $(SQLITE)

# Latest VMangos world DB snapshot (GitHub release `db_latest`, SQLite variant).
$(SQLITE):
	mkdir -p $(VMANGOS)
	python3 etl/fetch_vmangos.py $(VMANGOS)

site-data:
	python3 etl/build.py

# Pull newer QuestieDB and VMangos data, then rebuild.
update:
	git submodule update --remote $(QUESTIE)
	rm -rf $(VMANGOS)
	$(MAKE) data

web/node_modules:
	cd web && npm ci

dev: web/node_modules
	cd web && npm run dev

build: web/node_modules
	cd web && npm run build

maps:
	python3 etl/maps.py --wow-dir "$(WOW_DIR)" --product wow_classic_era --flavor classic
	python3 etl/maps.py --wow-dir "$(WOW_DIR)" --product wow_classic_beta --flavor forever

# Docker image serving the site with nginx; the data is built inside the image.
IMAGE ?= wow-quest-database
docker: submodule
	docker build -t $(IMAGE) --build-arg QUESTIE_REV="$$(git -C $(QUESTIE) log -1 --format='%h %cs')" .

# Quest texts from WoW client caches -> etl/corrections/questcache/<flavor>/<locale>.json
FLAVOR ?= forever
CACHE  ?= $(WOW_DIR)/_classic_beta_/Cache/WDB
questcache:
	python3 etl/import_questcache.py --flavor $(FLAVOR) "$(CACHE)"

# Lua export of the merged data, see etl/export_lua.py --help
lua:
	python3 etl/export_lua.py $(ARGS)

clean:
	rm -rf build web/build web/static/data
