-- etl/questie_export.lua
--
-- Exports one QuestieDB flavor as JSON, with Static Corrections and Derived Passes applied
-- exactly as QuestieDB's own generator applies them.
--
-- Must be run from the QuestieDB checkout root, because QuestieDB's generator modules load
-- each other through relative `dofile` paths:
--
--   cd vendor/QuestieDB
--   ./tools/lua-binary/linux-x64/lua ../../etl/questie_export.lua Vanilla ../../build/questie/classic
--
-- Output files in <outDir>:
--   Quest.json, Npc.json, Object.json, Item.json   { "<id>": { "<fieldName>": value, ... } }
--   l10n.json      { "<Type>": { "<id>": { "<field>": { "<locale>": value } } } }
--   support.json   zone maps, dungeons, quest XP, faction templates, drop tables
--   meta.json      field names per entity type and export statistics

local flavorName, outDir = arg[1], arg[2]
if not flavorName or not outDir then
  io.stderr:write("usage: lua questie_export.lua <Vanilla|Forever|...> <outDir>\n")
  os.exit(2)
end

local config = dofile("src/config.lua")
local flavorLoader = dofile("generator/flavor.lua")
local l10nGen = dofile("generator/l10n.lua")

local flavor = config.flavorByName[flavorName]
if not flavor then error("unknown flavor " .. flavorName) end

--------------------------------------------------------------------------------------------
-- JSON encoding
--------------------------------------------------------------------------------------------
--
-- Questie rows are positional Lua tables with nil holes, so a plain sequence check is not
-- enough. Tables whose integer keys are dense enough become arrays (holes -> null); tables
-- keyed by IDs (spawn lists keyed by zone, etc.) are forced to objects by the caller.

local escapes = {
  ['"'] = '\\"', ['\\'] = '\\\\', ['\b'] = '\\b', ['\f'] = '\\f',
  ['\n'] = '\\n', ['\r'] = '\\r', ['\t'] = '\\t',
}

local function encodeString(s)
  return '"' .. s:gsub('[%c"\\]', function(c)
    return escapes[c] or string.format("\\u%04x", c:byte())
  end) .. '"'
end

local function encodeNumber(n)
  if n ~= n or n == math.huge or n == -math.huge then return "null" end
  if n == math.floor(n) and math.abs(n) < 1e15 then return string.format("%d", n) end
  return string.format("%.14g", n)
end

local encode

local function encodeObject(t, buf)
  local keys = {}
  for k in pairs(t) do keys[#keys + 1] = k end
  table.sort(keys, function(a, b)
    if type(a) == type(b) then return a < b end
    return type(a) == "number"
  end)
  buf[#buf + 1] = "{"
  for i, k in ipairs(keys) do
    if i > 1 then buf[#buf + 1] = "," end
    buf[#buf + 1] = encodeString(tostring(k))
    buf[#buf + 1] = ":"
    encode(t[k], buf)
  end
  buf[#buf + 1] = "}"
end

local function arrayLength(t)
  local count, max = 0, 0
  for k in pairs(t) do
    if type(k) ~= "number" or k < 1 or k ~= math.floor(k) then return nil end
    count = count + 1
    if k > max then max = k end
  end
  -- Positional rows have small holes; anything sparser is keyed data.
  if max > count * 2 + 4 then return nil end
  return max
end

function encode(v, buf, forceObject)
  local tv = type(v)
  if tv == "nil" then
    buf[#buf + 1] = "null"
  elseif tv == "boolean" then
    buf[#buf + 1] = tostring(v)
  elseif tv == "number" then
    buf[#buf + 1] = encodeNumber(v)
  elseif tv == "string" then
    buf[#buf + 1] = encodeString(v)
  elseif tv == "table" then
    local n = not forceObject and arrayLength(v)
    if n then
      buf[#buf + 1] = "["
      for i = 1, n do
        if i > 1 then buf[#buf + 1] = "," end
        encode(v[i], buf)
      end
      buf[#buf + 1] = "]"
    else
      encodeObject(v, buf)
    end
  else
    error("cannot encode " .. tv)
  end
end

local function writeJson(name, value)
  local buf = {}
  encode(value, buf, true)
  local f = assert(io.open(outDir .. "/" .. name, "wb"))
  f:write(table.concat(buf))
  f:close()
end

--------------------------------------------------------------------------------------------
-- Entities
--------------------------------------------------------------------------------------------

-- Structures whose top level is keyed by zone ID rather than positional.
local zoneKeyed = { spawnlist = true, waypointlist = true }

local function convertRow(meta, row)
  local out = {}
  for index, name in pairs(meta.names) do
    local value = row[index]
    if value ~= nil then
      local structure = meta.structures[index]
      if zoneKeyed[structure] then
        out[name] = setmetatable(value, { __jsonObject = true })
      elseif structure == "trigger" and type(value[2]) == "table" then
        setmetatable(value[2], { __jsonObject = true })
        out[name] = value
      else
        out[name] = value
      end
    end
  end
  return out
end

-- Honour the __jsonObject marker set above without touching the generic heuristic.
do
  local inner = encode
  encode = function(v, buf, forceObject)
    if type(v) == "table" then
      local mt = getmetatable(v)
      if mt and mt.__jsonObject then forceObject = true end
    end
    return inner(v, buf, forceObject)
  end
end

local loaded, stats = flavorLoader.load(flavor)
local metaOut = { flavor = flavor.name, expansion = flavor.expansion, types = {}, counts = {},
                  correctionsApplied = stats.applied }

for _, entityType in ipairs(config.entityTypes) do
  local entry = loaded[entityType.name]
  local rows, count = {}, 0
  for id, row in pairs(entry.entities) do
    rows[id] = convertRow(entry.meta, row)
    count = count + 1
  end
  writeJson(entityType.name .. ".json", rows)
  metaOut.types[entityType.name] = entry.meta.names
  metaOut.counts[entityType.name] = count
  io.stderr:write(("%s %s: %d\n"):format(flavor.name, entityType.name, count))
end

--------------------------------------------------------------------------------------------
-- Localization
--------------------------------------------------------------------------------------------

local l10nOut = {}
for _, entityType in ipairs(config.entityTypes) do
  local typeCfg = l10nGen.types[entityType.name]
  local entities = loaded[entityType.name].entities
  if typeCfg then
    local values = l10nGen.extract(config.paths.l10n, flavor, entityType.name, entities)
    local byId = {}
    for id, byField in pairs(values) do
      local fields = {}
      for fieldIndex, locales in pairs(byField) do
        local named = {}
        for localeIndex, value in pairs(locales) do
          named[config.locales[localeIndex]] = value
        end
        fields[typeCfg.fields[fieldIndex].name] = named
      end
      byId[id] = fields
    end
    l10nOut[entityType.name] = setmetatable(byId, { __jsonObject = true })
  end
end
writeJson("l10n.json", l10nOut)

--------------------------------------------------------------------------------------------
-- Support data
--------------------------------------------------------------------------------------------
--
-- Support files are Questie modules; run them in a sandbox with just enough stubs.

local supportRoot = flavor.expansion == "Forever" and "support/Forever" or "support"
local function supportPath(sub)
  return supportRoot .. "/" .. sub
end

local modules = {}
local function module(name)
  modules[name] = modules[name] or { private = {} }
  return modules[name]
end

local expansionIndex = config.expansionOrder[flavor.rules] or 1
modules.Expansions = {
  Current = expansionIndex, Era = 1, Classic = 1, Tbc = 2, TBC = 2, Wotlk = 3, Cata = 4, MoP = 5,
}

local function runSupport(path)
  local chunk = assert(loadfile(path))
  local env = setmetatable({
    QuestieLoader = {
      ImportModule = function(_, name) return module(name) end,
      CreateModule = function(_, name) return module(name) end,
    },
    UnitFactionGroup = function() return "Alliance" end,
  }, { __index = _G })
  setfenv(chunk, env)
  chunk()
end

local function evalString(s)
  if type(s) ~= "string" then return s end
  return assert(loadstring(s))()
end

local supportOut = {}
local dataSuffix = flavor.dataPrefix == "forever" and "classic" or flavor.dataPrefix

-- Zone symbols (e.g. ELWYNN_FOREST = 12) double as the only zone-name source in QuestieDB.
do
  local enum = {}
  local chunk = assert(loadfile("src/corrections/enum/zones.lua"))
  chunk(nil, { Enum = enum })
  local names = {}
  for symbol, id in pairs(enum.zoneIDs) do names[id] = symbol end
  supportOut.zoneSymbols = setmetatable(names, { __jsonObject = true })
  module("ZoneDB").zoneIDs = enum.zoneIDs
end


runSupport(supportPath("Zones/areaIdToUiMapId.lua"))
runSupport(supportPath("Zones/uiMapIdToAreaId.lua"))
runSupport(supportPath("Zones/subZoneToParentZone.lua"))
runSupport(supportPath("Zones/instanceIdToAreaId.lua"))
runSupport(supportPath("Zones/dungeons.lua"))
local zoneDB = module("ZoneDB")
local function asObject(t) return setmetatable(t or {}, { __jsonObject = true }) end
supportOut.areaIdToUiMapId = asObject(evalString(zoneDB.private.areaIdToUiMapId))
supportOut.areaIdToUiMapIdOverride = asObject(evalString(zoneDB.private.areaIdToUiMapIdOverride))
supportOut.uiMapIdToAreaId = asObject(evalString(zoneDB.private.uiMapIdToAreaId))
supportOut.uiMapIdToAreaIdOverride = asObject(evalString(zoneDB.private.uiMapIdToAreaIdOverride))
supportOut.subZoneToParentZone = asObject(evalString(zoneDB.private.subZoneToParentZone))
supportOut.subZoneToParentZoneOverride = asObject(evalString(zoneDB.private.subZoneToParentZoneOverride))
supportOut.instanceIdToAreaId = asObject(zoneDB.instanceIdToAreaId)
local dungeons = zoneDB.private.dungeons or zoneDB.dungeons
supportOut.dungeons = asObject(dungeons)

runSupport(supportPath("QuestXP/xpDB-" .. dataSuffix .. ".lua"))
supportOut.questXP = asObject(module("QuestXP").db)

runSupport(supportPath("FactionTemplates/factionTemplate" .. (dataSuffix:gsub("^%l", string.upper)) .. ".lua"))
supportOut.factionTemplate = asObject(module("QuestieDB").factionTemplate)

runSupport(supportPath("DropTables/" .. dataSuffix .. "ItemDrops.lua"))
local drops = module("Questie" .. (dataSuffix:gsub("^%l", string.upper)) .. "ItemDrops")
supportOut.itemDrops = asObject(evalString(drops.wowheadData))

writeJson("support.json", supportOut)
writeJson("meta.json", metaOut)
io.stderr:write("done: " .. outDir .. "\n")
