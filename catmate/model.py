"""Pure domain logic: persistence, economy, clock, and needs. No Qt required."""
import copy
import json
import math
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from .catalog import ITEMS, gifts_today

DEFAULTS = {
    "version": 1, "name": "奶油", "coins": 200, "hunger": 78.0,
    "joy": 82.0, "energy": 90.0, "bond": 0, "outfit": "",
    "inventory": {"fish": 3, "freeze": 1, "puree": 2, "kibble": 5, "yarn": 1},
    "settings": {"salary": 35.0, "size": 240, "wander": True, "cursor_chase": False,
                 "perch": True, "idle_pause": True, "water": True, "water_minutes": 45,
                 "breaks": True, "break_minutes": 60, "focus_minutes": 25,
                 "birthday": "11-17", "quiet": False, "eco": False},
    "history": {}, "coin_remainder": 0.0, "apps": [], "position": None,
    "last_seen": "", "claimed": [],
}

def default_data_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CatMate"

def finite_number(value, fallback, low=0, high=1e12):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return fallback
    return max(low, min(high, value))

class Store:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory else default_data_dir()
        self.path = self.directory / "save.json"
        self.recovered = False
        self.data = copy.deepcopy(DEFAULTS)
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    raise ValueError("Save must be an object")
                self._merge(raw)
            except (ValueError, OSError, TypeError):
                self.recovered = True
                self.data = copy.deepcopy(DEFAULTS)
                self.directory.mkdir(parents=True, exist_ok=True)
                try:
                    self.path.rename(self.directory / f"save.corrupt-{time.time_ns()}.json")
                except OSError:
                    pass

    def _merge(self, raw):
        d = self.data
        for key in ("name", "outfit", "last_seen"):
            if isinstance(raw.get(key), str):
                d[key] = raw[key][:200]
        d["name"] = d["name"][:12] or "奶油"
        for key in ("coins", "bond"):
            d[key] = int(finite_number(raw.get(key), d[key]))
        for key in ("hunger", "joy", "energy"):
            d[key] = float(finite_number(raw.get(key), d[key], 0, 100))
        d["coin_remainder"] = finite_number(raw.get("coin_remainder"), 0, 0, 60)
        if isinstance(raw.get("settings"), dict):
            for k, v in raw["settings"].items():
                if k in d["settings"] and type(v) is type(d["settings"][k]):
                    d["settings"][k] = v
            for k, lo, hi in [("salary", 0, 100000), ("size", 120, 420),
                              ("water_minutes", 1, 240), ("break_minutes", 1, 240), ("focus_minutes", 1, 180)]:
                d["settings"][k] = finite_number(d["settings"][k], DEFAULTS["settings"][k], lo, hi)
            try:
                datetime.strptime("2000-" + d["settings"]["birthday"], "%Y-%m-%d")
            except ValueError:
                d["settings"]["birthday"] = DEFAULTS["settings"]["birthday"]
        if isinstance(raw.get("inventory"), dict):
            d["inventory"] = {k: int(finite_number(v, 0, 0, 9999)) for k, v in raw["inventory"].items() if k in ITEMS}
        if d["outfit"] not in ITEMS or ITEMS[d["outfit"]]["kind"] != "outfit" or not d["inventory"].get(d["outfit"]):
            d["outfit"] = ""
        if isinstance(raw.get("history"), dict):
            for day, record in raw["history"].items():
                try:
                    date.fromisoformat(day)
                    if not isinstance(record, dict):
                        continue
                    d["history"][day] = {k: finite_number(record.get(k), 0) for k in ("seconds", "income", "focus")}
                except (ValueError, TypeError):
                    continue
        if isinstance(raw.get("apps"), list):
            d["apps"] = [a for a in raw["apps"][:20] if isinstance(a, dict) and
                         isinstance(a.get("name"), str) and isinstance(a.get("path"), str)]
        if isinstance(raw.get("claimed"), list):
            d["claimed"] = [x for x in raw["claimed"] if isinstance(x, str)][-100:]
        p = raw.get("position")
        if isinstance(p, list) and len(p) == 2 and all(isinstance(x, int) for x in p):
            d["position"] = p

    def save(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.data["last_seen"] = datetime.now().isoformat()
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as stream:
            json.dump(self.data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, self.path)

class Companion:
    def __init__(self, store):
        self.store = store
        self.d = store.data
        self.working = False
        self.idle_paused = False
        self.focus_remaining = 0.0
        self.focus_duration = 0.0
        self.focus_paused = False
        self._water_elapsed = 0.0
        self._break_elapsed = 0.0
        self._pet_cooldown = 0.0

    def record(self, day=None):
        key = (day or date.today()).isoformat()
        return self.d["history"].setdefault(key, {"seconds": 0.0, "income": 0.0, "focus": 0})

    def buy(self, item_id):
        item = ITEMS.get(item_id)
        if not item:
            return False, "找不到这件物品。"
        if item["kind"] != "food" and self.d["inventory"].get(item_id, 0):
            return False, "已经拥有啦，可以一直使用。"
        if self.d["coins"] < item["price"]:
            return False, "猫爪币还不够，工作一会儿再来吧。"
        self.d["coins"] -= item["price"]
        inv = self.d["inventory"]
        inv[item_id] = inv.get(item_id, 0) + 1
        return True, f"已获得{item['name']}。"

    def feed(self, item_id):
        item = ITEMS.get(item_id)
        if not item or item["kind"] != "food" or not self.d["inventory"].get(item_id, 0):
            return False, "背包里还没有，先去补充一点吧。"
        if self.d["hunger"] >= 96:
            return False, "肚子圆滚滚的，等饿一点再吃吧。"
        self.d["inventory"][item_id] -= 1
        self.d["hunger"] = min(100, self.d["hunger"] + item["hunger"])
        self.d["joy"] = min(100, self.d["joy"] + item["joy"])
        self.d["bond"] += 2
        return True, f"吃到了{item['name']}，呼噜呼噜～"

    def equip(self, item_id):
        if item_id and (item_id not in ITEMS or ITEMS[item_id]["kind"] != "outfit" or not self.d["inventory"].get(item_id)):
            return False
        self.d["outfit"] = item_id
        return True

    def claim_gift(self, item_id, today=None):
        today = today or date.today()
        token = f"{today.year}:{item_id}"
        if item_id not in gifts_today(today, self.d["settings"]["birthday"]) or token in self.d["claimed"]:
            return False
        self.d["inventory"][item_id] = 1
        self.d["claimed"].append(token)
        return True

    def pet(self):
        if self._pet_cooldown > 0:
            return
        self.d["joy"] = min(100, self.d["joy"] + 2)
        self.d["bond"] += 1
        self._pet_cooldown = 8.0

    def start_focus(self, minutes=None):
        self.focus_duration = float(minutes or self.d["settings"]["focus_minutes"]) * 60
        self.focus_remaining = self.focus_duration
        self.focus_paused = False

    def tick(self, dt, now=None, sleeping=False, idle=False):
        """Return notification events. Large gaps (suspend) never accrue rewards."""
        if not 0 < dt <= 5:
            return []
        now = now or datetime.now()
        events = []
        self._pet_cooldown = max(0, self._pet_cooldown - dt)
        self.d["hunger"] = max(0, self.d["hunger"] - dt / 180)
        self.d["joy"] = max(0, self.d["joy"] - dt / 300)
        self.d["energy"] = max(0, min(100, self.d["energy"] + dt * (0.025 if sleeping else -0.005)))
        self.idle_paused = idle and self.d["settings"]["idle_pause"]
        if self.working and not self.idle_paused:
            # Split a tick crossing local midnight into the correct daily records.
            start = now - timedelta(seconds=dt)
            while start < now:
                midnight = datetime.combine(start.date() + timedelta(days=1), datetime.min.time())
                end = min(now, midnight)
                span = (end - start).total_seconds()
                record = self.record(start.date())
                record["seconds"] += span
                record["income"] += span * self.d["settings"]["salary"] / 3600
                start = end
            self.d["coin_remainder"] += dt
            minutes = int(self.d["coin_remainder"] // 60)
            self.d["coins"] += minutes * 2
            self.d["coin_remainder"] -= minutes * 60
            self._break_elapsed += dt
        if self.focus_remaining and not self.focus_paused and not self.idle_paused:
            self.focus_remaining = max(0, self.focus_remaining - dt)
            if self.focus_remaining == 0:
                self.d["coins"] += 50
                self.record(now.date())["focus"] += 1
                events.append(("focus", "专注完成 · +50 猫爪币", "辛苦啦，伸个懒腰，和小猫休息一下。"))
        if not idle:
            self._water_elapsed += dt
        s = self.d["settings"]
        if s["water"] and self._water_elapsed >= s["water_minutes"] * 60:
            self._water_elapsed = 0
            events.append(("water", "该喝水啦", "你喝水，我舔毛。一起休息一小会儿。"))
        if s["breaks"] and self._break_elapsed >= s["break_minutes"] * 60:
            self._break_elapsed = 0
            events.append(("break", "起来走走吧", "已经认真工作了一阵，看看远处，活动一下肩颈。"))
        return events

def duration_text(seconds):
    total = max(0, int(seconds))
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"
