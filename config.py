import os
import json
import tempfile

TPL_DIR = "templates_roblox"
CFG_FILE = "config_roblox.json"
os.makedirs(TPL_DIR, exist_ok=True)

RU = {
    "magnifier": "Лупа",
    "phone": "Бёрнер-телефон",
    "inverter": "Инвертор",
    "saw": "Ножовка",
    "handcuffs": "Наручники",
    "potion": "Зелье",
    "soda": "Газировка",
    "adrenaline": "Адреналин",
    "remote": "Пульт (4 игрока)",
    "voodoo": "Вуду-кукла",
    "mirror": "Зеркало",
    "cube": "Кости",
}
ITEMS = list(RU)

DEFAULT_CFG = {
    "items": None,
    "shells": None,
    "hp_me": None,
    "hp_o": [None, None, None],
    "items_o": [None, None, None],
    "thresh": 0.8,
    "min_area": 600,
}

cfg = json.loads(json.dumps(DEFAULT_CFG))  # глубокий клон


def _is_roi(v):
    return (isinstance(v, (list, tuple)) and len(v) == 4
            and all(isinstance(x, (int, float)) for x in v))


def _sanitize(raw):
    """Приводит загруженный конфиг к безопасному виду."""
    out = json.loads(json.dumps(DEFAULT_CFG))
    if not isinstance(raw, dict):
        return out

    if _is_roi(raw.get("items")):
        out["items"] = list(raw["items"])
    if _is_roi(raw.get("shells")):
        out["shells"] = list(raw["shells"])
    if _is_roi(raw.get("hp_me")):
        out["hp_me"] = list(raw["hp_me"])

    for key in ("hp_o", "items_o"):
        src = raw.get(key)
        if isinstance(src, list):
            for i in range(3):
                if i < len(src) and _is_roi(src[i]):
                    out[key][i] = list(src[i])

    try:
        t = float(raw.get("thresh", out["thresh"]))
        out["thresh"] = min(1.0, max(0.0, t))
    except (TypeError, ValueError):
        pass
    try:
        out["min_area"] = max(1, int(raw.get("min_area", out["min_area"])))
    except (TypeError, ValueError):
        pass
    return out


if os.path.exists(CFG_FILE):
    try:
        with open(CFG_FILE, "r", encoding="utf-8") as f:
            cfg = _sanitize(json.load(f))
    except Exception:
        pass


def save_cfg():
    """Атомарная запись, чтобы не убить конфиг при падении."""
    fd, tmp = tempfile.mkstemp(dir=".", prefix=".cfg_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
        os.replace(tmp, CFG_FILE)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass