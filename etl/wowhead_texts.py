"""Helper for scripts/wowhead-texts.sh: quest lists, HTML parsing and storage of Wowhead texts.

    python3 etl/wowhead_texts.py plan [QUEST_ID ...] [--all-langs] [--refresh]
        one line per quest to fetch: "<quest id> <locale>,<locale>,..."
    python3 etl/wowhead_texts.py parse LOCALE QUEST_ID FILE [--flavor] [--dry-run]
    python3 etl/wowhead_texts.py block-check FILE                # exit 1 on a block/captcha page
    python3 etl/wowhead_texts.py names [--min 2]                 # suggest player names in the texts
    python3 etl/wowhead_texts.py fix-names NAME ...              # replace these names with $N

Wowhead's texts for new quests come from players' game clients, so some contain the uploader's
character name ("Thank you, Trogdorp") instead of the $N placeholder. `names` lists likely
candidates; the ones confirmed with `fix-names` go to player-names.json and are replaced in all
stored texts and in everything fetched later.

Texts are stored in etl/corrections/wowhead/<flavor>/<locale>.json in the same shape as the
client-cache texts; etl/build.py uses them only where QuestieDB, VMangos and the client cache
have nothing.
"""

import argparse
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT_FIELDS = ("name", "objectivesText", "details", "progress", "completion", "endText")
# stored with every entry; entries read by an older parser are fetched again
# (v2: sections are recognised by their heading - v1 took a "Completion" or "Rewards" section
# for the description when a quest has none)
PARSER_VERSION = 2

# no Italian: WoW Classic has no Italian client, Wowhead's /it/ pages show the English text
SITE_LOCALES = ["enUS", "deDE", "esES", "esMX", "frFR", "ptBR", "ruRU", "koKR", "zhCN", "zhTW"]
# texts that count as "present" for a language; without them the language is fetched
REQUIRED = ("name", "details")

# Wowhead shows the client placeholders as <name>, <class>, <race>; turn them back into $N/$C/$R
PLACEHOLDERS = {
    "N": ("name", "nombre", "nom", "nome", "имя", "이름", "名字", "名字"),
    "C": ("class", "klasse", "clase", "classe", "класс", "직업", "职业", "職業"),
    "R": ("race", "volk", "rasse", "raza", "razza", "raça", "раса", "종족", "种族", "種族"),
}


# section headings on Wowhead quest pages in every language (zhCN/zhTW pages show no progress
# or completion text at all)
SECTION_HEADINGS = {
    **dict.fromkeys(("description", "beschreibung", "descripción", "descrição", "описание", "서술", "描述"),
                    "details"),
    **dict.fromkeys(("progress", "fortschritt", "progreso", "progrès", "progresso", "прогресс", "진행 상황"),
                    "progress"),
    **dict.fromkeys(("completion", "vervollständigung", "terminación", "achèvement", "completo", "завершено",
                     "완료"), "completion"),
}

RU_CLASSES = ("Воин", "Паладин", "Охотник", "Разбойник", "Жрец", "Шаман", "Маг", "Чернокнижник", "Друид")

NAMES_PATH = ROOT / "etl" / "corrections" / "wowhead" / "player-names.json"


def player_names():
    return json.loads(NAMES_PATH.read_text(encoding="utf-8"))["names"] if NAMES_PATH.exists() else []


def replace_names(value, names):
    if not names or not value:
        return value
    if isinstance(value, list):
        return [replace_names(v, names) for v in value]
    pattern = r"(?<!\w)(?:" + "|".join(map(re.escape, sorted(names, key=len, reverse=True))) + r")(?!\w)"
    return re.sub(pattern, "$N", value)


def store_path(flavor, locale):
    return ROOT / "etl" / "corrections" / "wowhead" / flavor / f"{locale}.json"


def load_store(flavor, locale):
    path = store_path(flavor, locale)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"_comment": "Quest texts read from wowhead.com by scripts/wowhead-texts.sh. Used by etl/build.py "
                        "only where QuestieDB, VMangos and the client cache have no text.",
            "quests": {}}


def save_store(flavor, locale, store):
    path = store_path(flavor, locale)
    path.parent.mkdir(parents=True, exist_ok=True)
    store["quests"] = dict(sorted(store["quests"].items(), key=lambda kv: int(kv[0])))
    # write a temporary file and rename it, so Ctrl+C never leaves a half-written file behind
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(store, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------- quest list

def site_texts(flavor):
    """{locale: {quest id: texts}} from the built site data (English from the quest shards)."""
    base = ROOT / "web" / "static" / "data" / flavor
    if not base.exists():
        sys.exit(f"{base} not found - run `make data` first")

    def read(folder):
        out = {}
        for shard in folder.glob("*.json"):
            out.update(json.loads(shard.read_text(encoding="utf-8")))
        return out
    texts = {"enUS": read(base / "quest")}
    for locale in SITE_LOCALES[1:]:
        texts[locale] = read(base / "l10n" / locale / "quest")
    return texts


def plan(flavor, quest_ids=None, all_langs=False, refresh=False):
    """[(quest id, [locales])]: what to fetch.

    Without quest IDs: every quest where some language lacks a name or description, with just
    those languages (all of them with all_langs). Languages already fetched are skipped unless
    refresh is set; that also covers pages Wowhead does not have (stored as notFound).
    """
    texts = site_texts(flavor)
    stored = {} if refresh else {loc: load_store(flavor, loc)["quests"] for loc in SITE_LOCALES}
    ids = quest_ids or sorted(int(q) for q in texts["enUS"])
    out = []
    for qid in ids:
        key = str(qid)
        if quest_ids or all_langs:
            wanted = list(SITE_LOCALES)
        else:
            wanted = [loc for loc in SITE_LOCALES
                      if not all(texts[loc].get(key, {}).get(f) for f in REQUIRED)]
        # already fetched by the current parser? (older entries are fetched again)
        current = lambda loc: stored.get(loc, {}).get(key, {}).get("v", 1) >= PARSER_VERSION
        stale = [loc for loc in SITE_LOCALES if key in stored.get(loc, {}) and not current(loc)]
        wanted = [loc for loc in SITE_LOCALES if (loc in wanted or loc in stale) and not current(loc)]
        if wanted:
            out.append((qid, wanted))
    return out


# ---------------------------------------------------------------------------- parsing

def clean(fragment):
    """HTML fragment -> plain text in the client's format ($B line breaks, $N/$C/$R)."""
    text = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)

    def placeholder(m):
        word = m.group(1).strip().lower()
        for code, words in PLACEHOLDERS.items():
            if word in words:
                return f"${code}"
        return m.group(0)
    text = re.sub(r"<([^<>]{1,20})>", placeholder, text)
    # Russian grammar codes keep the class: |3-6($C); Wowhead shows the uploader's class instead
    text = re.sub(r"\|3-(\d)\((" + "|".join(RU_CLASSES) + r")\)", r"|3-\1($C)", text)
    lines = [" ".join(line.split()) for line in text.split("\n")]
    text = "\n".join(lines).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.replace("\n", "$B") or None


def block_reason(page):
    # a real quest page (it has the title heading) is never a block page; normal pages mention
    # "recaptcha" for the comment form, so only look for block markers on the other ones
    if re.search(r'<h1[^>]*class="[^"]*heading-size-1', page):
        return None
    if re.search(r"cf-chl|challenge-platform|<title>\s*Just a moment|captcha", page, re.I):
        return "bot check / captcha page"
    if re.search(r"Access denied|You have been blocked|rate limit", page, re.I):
        return "access denied / rate limited"
    return None


def parse(page):
    """Quest texts from a Wowhead quest page (None values for what is not shown)."""
    out = dict.fromkeys(TEXT_FIELDS)
    m = re.search(r'<h1[^>]*class="[^"]*heading-size-1[^"]*"[^>]*>(.*?)</h1>', page, re.S)
    if not m:
        return None
    out["name"] = clean(m.group(1))
    after_title = page[m.end():]

    # objectives text: the text right after the title, before the first table/heading/script
    m_obj = re.match(r"(.*?)(?=<(?:table|h2|h3|div|script|ul)\b)", after_title, re.S)
    if m_obj:
        out["objectivesText"] = clean(m_obj.group(1))

    # sections are only told apart by their (localized) heading; a quest without description
    # starts with "Completion", and the rewards section must never be taken for a text
    for h in re.finditer(r'<h2[^>]*class="[^"]*heading-size-3[^"]*"[^>]*>(.*?)</h2>(.*?)(?=<h2\b|<script\b|<div class="pad)',
                         after_title, re.S):
        field = SECTION_HEADINGS.get(re.sub(r"<[^>]+>", "", h.group(1)).strip().lower())
        if field == "details" and not out["details"]:
            out["details"] = clean(h.group(2))
        elif field in ("progress", "completion") and not out[field] and 'id="lknlksndgg' not in h.group(2):
            out[field] = clean(h.group(2))  # shown directly instead of as a collapsed block

    # progress and completion are usually collapsed blocks with fixed ids
    for field in ("progress", "completion"):
        m2 = re.search(rf'<div[^>]*id="lknlksndgg-{field}"[^>]*>(.*?)</div>', page, re.S)
        if m2:
            out[field] = clean(m2.group(1))
    out["objectivesText"] = [out["objectivesText"]] if out["objectivesText"] else None
    return out


# ---------------------------------------------------------------------------- player names

# a capitalised word addressed directly: "Thank you, Trogdorp," / "Danke, Digawen, gute Arbeit"
VOCATIVE = re.compile(r"(?:^|[,!.?]\s|\$B)\s*(?:\w+\s){0,3}?\w*,\s+([A-ZÀ-ÖØ-ÞА-Я][a-zà-öø-ÿа-я]{2,11})(?=[,.!?])")


def name_candidates(flavor, minimum):
    """{word: [quest ids]} for words that look like player names in stored Wowhead texts."""
    known = set()
    search_files = [ROOT / "web" / "static" / "data" / flavor / "search.json"]
    search_files += (ROOT / "web" / "static" / "data" / flavor / "l10n").glob("*/search.json")
    for path in search_files:
        if path.exists():
            for kind_names in json.loads(path.read_text(encoding="utf-8")).values():
                for entry in (kind_names.values() if isinstance(kind_names, dict) else kind_names):
                    name = entry if isinstance(entry, str) else (entry[1] if isinstance(entry, list) and len(entry) > 1 else "")
                    if isinstance(name, str):
                        known.update(re.findall(r"\w+", name))
    already = set(player_names())
    found = {}
    for locale in SITE_LOCALES:
        for qid, texts in load_store(flavor, locale)["quests"].items():
            for field in ("details", "progress", "completion", "endText"):
                for word in VOCATIVE.findall(texts.get(field) or ""):
                    if word not in known and word not in already:
                        found.setdefault(word, set()).add(f"{locale}:{qid}")
    return {w: sorted(q) for w, q in sorted(found.items(), key=lambda kv: -len(kv[1])) if len(q) >= minimum}


def fix_names(flavor, new_names):
    names = sorted(set(player_names()) | set(new_names))
    NAMES_PATH.parent.mkdir(parents=True, exist_ok=True)
    NAMES_PATH.write_text(json.dumps({"_comment": "Player character names found in Wowhead texts; replaced "
                                      "with $N by etl/wowhead_texts.py.", "names": names},
                                     ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    changed = 0
    for locale in SITE_LOCALES:
        store = load_store(flavor, locale)
        for qid, texts in store["quests"].items():
            fixed = {k: (replace_names(v, names) if k in TEXT_FIELDS else v) for k, v in texts.items()}
            if fixed != texts:
                store["quests"][qid] = fixed
                changed += 1
        if store["quests"]:
            save_store(flavor, locale, store)
    print(f"{len(names)} names in {NAMES_PATH.relative_to(ROOT)}; {changed} stored texts updated")


# ---------------------------------------------------------------------------- commands

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--flavor", default="forever", choices=["classic", "forever"])
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan")
    pl.add_argument("quests", type=int, nargs="*")
    pl.add_argument("--all-langs", action="store_true")
    pl.add_argument("--refresh", action="store_true")
    p = sub.add_parser("parse")
    p.add_argument("locale")
    p.add_argument("quest", type=int)
    p.add_argument("file")
    p.add_argument("--dry-run", action="store_true")
    b = sub.add_parser("block-check")
    b.add_argument("file")
    nm = sub.add_parser("names")
    nm.add_argument("--min", type=int, default=2, help="minimum number of texts a name appears in")
    fx = sub.add_parser("fix-names")
    fx.add_argument("names", nargs="+")
    args = ap.parse_args()

    if args.cmd == "plan":
        for qid, locales in plan(args.flavor, args.quests, args.all_langs, args.refresh):
            print(qid, ",".join(locales))
    elif args.cmd == "names":
        candidates = name_candidates(args.flavor, args.min)
        for word, where in candidates.items():
            print(f"{word:14s} {len(where):4d}x  e.g. {', '.join(where[:4])}")
        if candidates:
            print("\nConfirm real player names with: python3 etl/wowhead_texts.py fix-names NAME ...")
    elif args.cmd == "fix-names":
        fix_names(args.flavor, args.names)
    elif args.cmd == "block-check":
        reason = block_reason(Path(args.file).read_text(encoding="utf-8", errors="replace"))
        if reason:
            print(reason)
            sys.exit(1)
    elif args.cmd == "parse":
        page = Path(args.file).read_text(encoding="utf-8", errors="replace")
        texts = parse(page)
        if texts is None:
            print(f"{args.locale} {args.quest}: no quest title found (quest not on Wowhead?)", file=sys.stderr)
            texts = {"notFound": True}
        names = player_names()
        entry = {k: replace_names(v, names) for k, v in texts.items() if v}
        if args.dry_run:
            print(json.dumps({args.locale: entry}, ensure_ascii=False, indent=1))
            return
        store = load_store(args.flavor, args.locale)
        store["quests"][str(args.quest)] = {**entry, "fetched": datetime.now(timezone.utc).date().isoformat(),
                                            "v": PARSER_VERSION}
        save_store(args.flavor, args.locale, store)
        fields = ", ".join(k for k in TEXT_FIELDS if k in entry) or "nothing"
        print(f"{args.locale} {args.quest}: {fields}")


if __name__ == "__main__":
    main()
