"""Static game enums that neither QuestieDB nor the VMangos world DB carry as named data."""

FLAVORS = {
    # site id -> QuestieDB flavor name / export dir
    "forever": {"questie": "Forever", "label": "WoW Forever"},
}

# QuestieDB l10n locales; VMangos `locales_*` loc1..loc8 map onto all but ptBR.
LOCALES = ["deDE", "esES", "esMX", "frFR", "koKR", "ptBR", "ruRU", "zhCN", "zhTW"]
VMANGOS_LOCALE_INDEX = {
    "koKR": 1, "frFR": 2, "deDE": 3, "zhCN": 4, "zhTW": 5, "esES": 6, "esMX": 7, "ruRU": 8,
}

RACES = {
    1: "Human", 2: "Orc", 4: "Dwarf", 8: "Night Elf", 16: "Undead", 32: "Tauren",
    64: "Gnome", 128: "Troll", 256: "Goblin", 512: "Blood Elf", 1024: "Draenei",
}
ALLIANCE_RACES = 1 | 4 | 8 | 64 | 1024
HORDE_RACES = 2 | 16 | 32 | 128 | 256 | 512

CLASSES = {
    1: "Warrior", 2: "Paladin", 4: "Hunter", 8: "Rogue", 16: "Priest", 32: "Death Knight",
    64: "Shaman", 128: "Mage", 256: "Warlock", 1024: "Druid",
}

# Negative ZoneOrSort values: name and group for the zone list (after QuestieDB's sortKeys enum,
# src/corrections/enum/quests.lua).
QUEST_SORT_INFO = {
    # classes
    -61: ("Warlock", "class"), -81: ("Warrior", "class"), -82: ("Shaman", "class"),
    -141: ("Paladin", "class"), -161: ("Mage", "class"), -162: ("Rogue", "class"),
    -261: ("Hunter", "class"), -262: ("Priest", "class"), -263: ("Druid", "class"),
    -372: ("Death Knight", "class"), -395: ("Monk", "class"),
    # professions and skills
    -24: ("Herbalism", "profession"), -101: ("Fishing", "profession"), -121: ("Blacksmithing", "profession"),
    -181: ("Alchemy", "profession"), -182: ("Leatherworking", "profession"),
    -201: ("Engineering", "profession"), -264: ("Tailoring", "profession"), -304: ("Cooking", "profession"),
    -324: ("First Aid", "profession"), -371: ("Inscription", "profession"),
    -373: ("Jewelcrafting", "profession"), -377: ("Archaeology", "profession"), -398: ("Riding", "profession"),
    # holidays and world events
    -21: ("Hallow's End", "event"), -22: ("Seasonal", "event"), -41: ("Day of the Dead", "event"),
    -364: ("Darkmoon Faire", "event"), -365: ("Ahn'Qiraj War", "event"), -366: ("Lunar Festival", "event"),
    -368: ("Invasion", "event"), -369: ("Midsummer", "event"), -370: ("Brewfest", "event"),
    -374: ("Noblegarden", "event"), -375: ("Pilgrim's Bounty", "event"),
    -376: ("Love is in the Air", "event"), -378: ("Children's Week", "event"),
    -402: ("Harvest Festival", "event"), -404: ("Winter Veil", "event"),
    -641: ("Nightmare Incursions", "event"), -644: ("Blackrock Eruption", "event"),
    # other categories
    -1: ("Epic", "other"), -23: ("Undercity (old)", "other"), -25: ("Battlegrounds", "other"),
    -221: ("Treasure Map", "other"), -241: ("Tournament", "other"), -284: ("Special", "other"),
    -344: ("Legendary", "other"), -367: ("Reputation", "other"), -662: ("Titan Reforged", "other"),
    -660: ("The High Order", "other"), -666: ("Camping", "other"), -676: ("Night Elf", "other"),
}
QUEST_SORTS = {k: name for k, (name, _group) in QUEST_SORT_INFO.items()}
QUEST_SORT_GROUPS = {k: group for k, (_name, group) in QUEST_SORT_INFO.items()}

# quest_template.Type (QuestInfo.dbc)
QUEST_TYPES = {
    1: "Group", 21: "Life", 41: "PvP", 62: "Raid", 81: "Dungeon", 82: "World Event",
    83: "Legendary", 84: "Escort", 85: "Heroic",
}

SKILLS = {
    6: "Frost", 8: "Fire", 26: "Arms", 38: "Combat", 39: "Subtlety", 40: "Poisons",
    43: "Swords", 44: "Axes", 45: "Bows", 46: "Guns", 54: "Maces", 55: "Two-Handed Swords",
    95: "Defense", 98: "Language: Common", 109: "Language: Orcish", 129: "First Aid",
    136: "Staves", 160: "Two-Handed Maces", 162: "Unarmed", 164: "Blacksmithing",
    165: "Leatherworking", 171: "Alchemy", 172: "Two-Handed Axes", 173: "Daggers",
    176: "Thrown", 182: "Herbalism", 185: "Cooking", 186: "Mining", 197: "Tailoring",
    202: "Engineering", 226: "Crossbows", 228: "Wands", 229: "Polearms", 333: "Enchanting",
    356: "Fishing", 393: "Skinning", 473: "Fist Weapons", 633: "Lockpicking",
    762: "Riding",
}

ITEM_QUALITIES = ["Poor", "Common", "Uncommon", "Rare", "Epic", "Legendary", "Artifact"]

ITEM_CLASSES = {
    0: ("Consumable", {}),
    1: ("Container", {0: "Bag", 1: "Soul Bag", 2: "Herb Bag", 3: "Enchanting Bag",
                      4: "Engineering Bag"}),
    2: ("Weapon", {0: "Axe", 1: "Two-Handed Axe", 2: "Bow", 3: "Gun", 4: "Mace",
                   5: "Two-Handed Mace", 6: "Polearm", 7: "Sword", 8: "Two-Handed Sword",
                   10: "Staff", 13: "Fist Weapon", 14: "Miscellaneous", 15: "Dagger",
                   16: "Thrown", 17: "Spear", 18: "Crossbow", 19: "Wand", 20: "Fishing Pole"}),
    4: ("Armor", {0: "Miscellaneous", 1: "Cloth", 2: "Leather", 3: "Mail", 4: "Plate",
                  5: "Buckler", 6: "Shield", 7: "Libram", 8: "Idol", 9: "Totem"}),
    5: ("Reagent", {}),
    6: ("Projectile", {2: "Arrow", 3: "Bullet"}),
    7: ("Trade Goods", {0: "Trade Goods", 1: "Parts", 2: "Explosives", 3: "Devices"}),
    9: ("Recipe", {0: "Book", 1: "Leatherworking", 2: "Tailoring", 3: "Engineering",
                   4: "Blacksmithing", 5: "Cooking", 6: "Alchemy", 7: "First Aid",
                   8: "Enchanting", 9: "Fishing"}),
    11: ("Quiver", {2: "Quiver", 3: "Ammo Pouch"}),
    12: ("Quest", {}),
    13: ("Key", {0: "Key", 1: "Lockpick"}),
    15: ("Miscellaneous", {0: "Junk"}),
}

INVENTORY_TYPES = {
    1: "Head", 2: "Neck", 3: "Shoulder", 4: "Shirt", 5: "Chest", 6: "Waist", 7: "Legs",
    8: "Feet", 9: "Wrist", 10: "Hands", 11: "Finger", 12: "Trinket", 13: "One-Hand",
    14: "Off Hand", 15: "Ranged", 16: "Back", 17: "Two-Hand", 18: "Bag", 19: "Tabard",
    20: "Chest", 21: "Main Hand", 22: "Off Hand", 23: "Held In Off-hand", 24: "Projectile",
    25: "Thrown", 26: "Ranged", 27: "Quiver", 28: "Relic",
}

BONDING = {1: "Binds when picked up", 2: "Binds when equipped", 3: "Binds when used",
           4: "Quest Item"}

STAT_TYPES = {
    0: "Mana", 1: "Health", 3: "Agility", 4: "Strength", 5: "Intellect", 6: "Spirit",
    7: "Stamina",
}

DAMAGE_SCHOOLS = {0: "", 1: "Holy", 2: "Fire", 3: "Nature", 4: "Frost", 5: "Shadow",
                  6: "Arcane"}

SPELL_TRIGGERS = {0: "Use", 1: "Equip", 2: "Chance on hit", 4: "Use", 5: "Learn"}

CREATURE_RANKS = {0: "Normal", 1: "Elite", 2: "Rare Elite", 3: "Boss", 4: "Rare"}

# creature_template.npc_flags (Vanilla UNIT_NPC_FLAG_*)
NPC_FLAGS = {
    1: "Gossip", 2: "Quest Giver", 4: "Vendor", 8: "Flight Master", 16: "Trainer",
    32: "Spirit Healer", 64: "Spirit Guide", 128: "Innkeeper", 256: "Banker",
    512: "Petitioner", 1024: "Tabard Designer", 2048: "Battlemaster", 4096: "Auctioneer",
    8192: "Stable Master", 16384: "Repair",
}


def bitmask_names(mask, table):
    return [name for bit, name in table.items() if mask & bit]


# Instance kind for the zone list where VMangos' map_template cannot tell it: the area sits on a
# continent map there (Blackrock Mountain, Onyxia's Lair, ...) or the instance is not in 1.12.
# None = not an instance list entry (shown with the zones).
INSTANCE_TYPES = {
    # Classic, area on a continent map in VMangos
    1583: "dungeon", 1584: "dungeon", 1477: "dungeon", 2159: "raid",
    2917: None, 2918: None,  # Hall of Legends, Champions' Hall
    # Season of Discovery / Forever additions
    15475: "dungeon", 15828: "dungeon", 16074: "dungeon", 15531: "raid", 16236: "raid",
    # later expansions (QuestieDB lists them; no Forever quests so far)
    3457: "raid", 3923: "raid", 3836: "raid", 3607: "raid", 3845: "raid", 3606: "raid", 3959: "raid",
    3805: "raid", 4075: "raid", 4273: "raid", 4812: "raid", 4722: "raid", 4493: "raid", 4500: "raid",
    4603: "raid", 4987: "raid", 5600: "raid", 5094: "raid", 5334: "raid", 5638: "raid", 5723: "raid",
    5892: "raid", 6125: "raid", 6297: "raid", 6067: "raid", 6622: "raid", 6738: "raid",
}
MAP_TYPE_NAMES = {1: "dungeon", 2: "raid", 3: "battleground"}

# Quest zones that are the outdoor area of an instance: QuestieDB files these instances' quests
# under them, so the zone list shows them with the instances.
QUEST_ZONE_INSTANCES = {
    133: "dungeon",   # Gnomeregan
    978: "dungeon",   # Zul'Farrak
    1417: "dungeon",  # Sunken Temple
    1517: "dungeon",  # Uldaman
    1717: "dungeon",  # Razorfen Kraul
}
