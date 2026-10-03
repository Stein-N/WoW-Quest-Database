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

# Negative ZoneOrSort values (QuestSort.dbc, Vanilla).
QUEST_SORTS = {
    -1: "Epic", -21: "Wailing Caverns (old)", -22: "Seasonal", -23: "Undercity (old)",
    -24: "Herbalism", -25: "Battlegrounds", -41: "Day of the Dead", -61: "Warlock",
    -81: "Warrior", -82: "Shaman", -101: "Fishing", -121: "Blacksmithing", -141: "Paladin",
    -161: "Mage", -162: "Rogue", -181: "Alchemy", -182: "Leatherworking", -201: "Engineering",
    -221: "Treasure Map", -241: "Tournament", -261: "Hunter", -262: "Priest", -263: "Druid",
    -264: "Tailoring", -284: "Special", -304: "Cooking", -324: "First Aid", -344: "Legendary",
    -364: "Darkmoon Faire", -365: "Ahn'Qiraj War", -366: "Lunar Festival", -367: "Reputation",
    -368: "Invasion", -369: "Midsummer", -370: "Brewfest", -374: "Noblegarden",
    -375: "Pilgrim's Bounty", -376: "Love is in the Air",
}

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
