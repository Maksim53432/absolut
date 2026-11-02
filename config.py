import os
import json

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
    "cube": "Кости"
}  
ITEMS = list(RU)

cfg = {
    "items": None, 
    "shells": None, 
    "hp_me": None,
    "hp_o": [None, None, None], 
    "items_o": [None, None, None],
    "thresh": 0.8, 
    "min_area": 600
}

if os.path.exists(CFG_FILE):
    try:
        with open(CFG_FILE, "r") as f:
            cfg.update(json.load(f))
    except Exception:
        pass

def save_cfg():
    with open(CFG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)
