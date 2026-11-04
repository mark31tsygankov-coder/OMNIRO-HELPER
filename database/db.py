import json, sqlite3, time
from pathlib import Path
from .paths import appdata_dir, data_sources, user_data_dir

SECTION_ORDER = ["transport", "realty", "weapons", "clothes", "jobs", "orgs",
                 "economy", "knowledge", "faq"]


def connect():
    c = sqlite3.connect(str(appdata_dir() / "omniro.db"))
    c.row_factory = sqlite3.Row
    c.executescript("""
    CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT);
    CREATE TABLE IF NOT EXISTS history(section TEXT, item_id TEXT, ts REAL,
        PRIMARY KEY(section,item_id));
    CREATE TABLE IF NOT EXISTS issued_keys(id TEXT PRIMARY KEY, name TEXT, device TEXT,
        created REAL, expires REAL, key TEXT, revoked INTEGER DEFAULT 0);
    """)
    return c


def get_setting(k, default=None):
    with connect() as c:
        r = c.execute("SELECT v FROM settings WHERE k=?", (k,)).fetchone()
    return json.loads(r["v"]) if r else default


def set_setting(k, v):
    with connect() as c:
        c.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (k, json.dumps(v)))


def add_history(section, item_id):
    with connect() as c:
        c.execute("INSERT OR REPLACE INTO history VALUES(?,?,?)", (section, item_id, time.time()))


def recent_history(limit=8):
    with connect() as c:
        return [(r["section"], r["item_id"]) for r in
                c.execute("SELECT * FROM history ORDER BY ts DESC LIMIT ?", (limit,))]


# ---- выданные ключи (для админ-панели) ----
def add_issued(rec):
    with connect() as c:
        c.execute("INSERT OR REPLACE INTO issued_keys VALUES(?,?,?,?,?,?,0)",
                  (rec["id"], rec["name"], rec["device"], rec["created"], rec["expires"], rec["key"]))


def list_issued():
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM issued_keys ORDER BY created DESC")]


def set_revoked(kid, flag=True):
    with connect() as c:
        c.execute("UPDATE issued_keys SET revoked=? WHERE id=?", (1 if flag else 0, kid))


def delete_issued(kid):
    with connect() as c:
        c.execute("DELETE FROM issued_keys WHERE id=?", (kid,))


# ---- каталог ----
class Catalog:
    def __init__(self):
        self.sections = {}
        self.errors = []
        self.load()

    def load(self):
        self.sections, self.errors = {}, []
        for folder in data_sources():
            for f in sorted(Path(folder).glob("*.json")):
                if f.name == "revoked.json":
                    continue
                try:
                    d = json.loads(f.read_text(encoding="utf-8"))
                    self._merge(d)
                except Exception as e:  # битый файл не должен ронять приложение
                    self.errors.append(f"{f.name}: {e}")

    def _merge(self, d):
        sid = d.get("section")
        if not sid or not isinstance(d.get("items", []), list):
            raise ValueError("нет поля section или items")
        cur = self.sections.get(sid)
        if cur is None:
            self.sections[sid] = {**d, "items": list(d.get("items", []))}
            return
        for k in ("title", "icon", "description", "updated", "source", "layout", "categories"):
            if k in d:
                cur[k] = d[k]
        by_id = {i.get("id"): n for n, i in enumerate(cur["items"])}
        for it in d.get("items", []):
            if it.get("id") in by_id:
                cur["items"][by_id[it["id"]]] = it
            else:
                cur["items"].append(it)

    def ordered(self):
        ids = [s for s in SECTION_ORDER if s in self.sections]
        ids += [s for s in self.sections if s not in ids]
        return [(i, self.sections[i]) for i in ids]

    def get_item(self, sid, iid):
        for it in self.sections.get(sid, {}).get("items", []):
            if it.get("id") == iid:
                return it

    def search(self, query, sections=None):
        toks = [t for t in query.lower().split() if t]
        res = []
        if not toks:
            return res
        for sid, sec in self.ordered():
            if sections and sid not in sections:
                continue
            for it in sec["items"]:
                hay = " ".join([str(it.get("name", "")), str(it.get("category", "")),
                                str(it.get("description", "")), str(it.get("price", "")),
                                " ".join(map(str, it.get("tags", []))),
                                " ".join(f"{k} {v}" for k, v in (it.get("stats") or {}).items())]).lower()
                if all(t in hay for t in toks):
                    res.append((sid, it))
        return res

    def import_file(self, path):
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        self._merge(dict(d))  # проверка структуры
        dest = user_data_dir() / Path(path).name
        dest.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        self.load()
        return d.get("section")
