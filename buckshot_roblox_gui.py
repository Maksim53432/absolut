"""
Советник для Roblox BUCKSHOT (crookit) с меню (tkinter).
Установка:  pip install mss opencv-python numpy pillow
Запуск:     python buckshot_roblox_gui.py
"""
import os, json, time, ctypes
import tkinter as tk
from tkinter import ttk, messagebox
import cv2, numpy as np, mss
from PIL import Image, ImageTk

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

TPL_DIR, CFG_FILE = "templates_roblox", "config_roblox.json"
os.makedirs(TPL_DIR, exist_ok=True)

# 9 предметов Roblox BUCKSHOT (пульт есть только за столом на 4 игроков)
RU = {"magnifier": "Лупа", "phone": "Бёрнер-телефон", "inverter": "Инвертор",
      "saw": "Ножовка", "handcuffs": "Наручники", "potion": "Зелье",
      "soda": "Газировка", "adrenaline": "Адреналин", "remote": "Пульт (4 игрока)",
      "voodoo": "Вуду-кукла", "mirror": "Зеркало", "cube": "Кости"}  
ITEMS = list(RU)
TEMPLATES = dict(RU)

cfg = {"items": None, "shells": None, "hp_me": None,
       "hp_o": [None, None, None], "items_o": [None, None, None],
       "thresh": 0.8, "min_area": 600}
if os.path.exists(CFG_FILE):
    cfg.update(json.load(open(CFG_FILE)))


def save_cfg():
    json.dump(cfg, open(CFG_FILE, "w"))


def monitor():
    with mss.mss() as s:
        return s.monitors[1]


def grab(roi=None):
    area = monitor() if roi is None else {"left": roi[0], "top": roi[1], "width": roi[2], "height": roi[3]}
    with mss.mss() as s:
        return np.array(s.grab(area))


def count(gray, name):
    path = os.path.join(TPL_DIR, name + ".png")
    if not os.path.exists(path):
        return 0
    t = cv2.imread(path, 0)
    if t is None or t.shape[0] > gray.shape[0] or t.shape[1] > gray.shape[1]:
        return 0
    r = cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(r >= cfg["thresh"])
    pts = []
    for p in zip(xs, ys):
        if all(abs(p[0] - q[0]) > t.shape[1] // 2 or abs(p[1] - q[1]) > t.shape[0] // 2 for q in pts):
            pts.append(p)
    return len(pts)


def count_shells(bgr):
    """Красные патроны = боевые, тёмно-серые = холостые. Возвращает (боевых, холостых)."""
    h, s, v = cv2.split(cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV))
    red = (((h <= 10) | (h >= 170)) & (s >= 120) & (v >= 70)).astype(np.uint8) * 255
    dark = ((v <= 70) & (s <= 95)).astype(np.uint8) * 255

    def blobs(m):
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return [(cv2.contourArea(c), cv2.boundingRect(c)[2]) for c in cs
                if cv2.contourArea(c) >= cfg["min_area"]]

    R, D = blobs(red), blobs(dark)
    if not R + D:
        return 0, 0
    amax = max(a for a, _ in R + D)
    R, D = [b for b in R if b[0] >= 0.4 * amax], [b for b in D if b[0] >= 0.4 * amax]
    base = min(w for _, w in R + D)        # ширина одного патрона

    def n(b):                               # слипшиеся патроны считаем по ширине
        r = b[1] / base
        return int(round(r)) if r >= 1.6 else 1
    return sum(n(b) for b in R), sum(n(b) for b in D)


def count_bolts(bgr):
    """Считает светящиеся молнии HP: бледные яркие вытянутые пятна. Название игрока и значок
    рядом отсеиваются по форме и размеру; панели под наклоном тоже читаются."""
    h, s, v = cv2.split(cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV))
    m = ((v >= 150) & (s <= 110)).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    blobs = []
    for c in cs:
        _, _, w, hh = cv2.boundingRect(c)
        a = cv2.contourArea(c)
        if a >= 8 and hh >= 1.25 * w and hh <= 4.5 * w and hh >= 6:   # вытянутые, не линии и не буквы
            blobs.append(a)
    if not blobs:
        return 0
    amax = max(blobs)
    return sum(1 for a in blobs if a >= 0.5 * amax)


def select_region(root):
    root.withdraw(); root.update(); time.sleep(0.3)
    shot = grab(); mon = monitor()
    img = Image.fromarray(cv2.cvtColor(shot, cv2.COLOR_BGRA2RGB))
    top = tk.Toplevel(root)
    top.attributes("-fullscreen", True); top.attributes("-topmost", True)
    cv = tk.Canvas(top, cursor="cross", highlightthickness=0); cv.pack(fill="both", expand=True)
    top.update_idletasks()
    sw, sh = top.winfo_screenwidth(), top.winfo_screenheight()
    photo = ImageTk.PhotoImage(img.resize((sw, sh)))
    cv.create_image(0, 0, image=photo, anchor="nw"); cv.image = photo
    cv.create_text(sw // 2, 30, fill="red", font=("Arial", 18, "bold"),
                   text="Выделите область мышкой (Esc — отмена)")
    res, s = {}, {}

    def down(e):
        s["x"], s["y"] = e.x, e.y
        s["r"] = cv.create_rectangle(e.x, e.y, e.x, e.y, outline="red", width=2)

    def move(e):
        if "r" in s:
            cv.coords(s["r"], s["x"], s["y"], e.x, e.y)

    def up(e):
        if "r" not in s:
            return
        k = img.width / sw
        x1, x2 = sorted((s["x"], e.x)); y1, y2 = sorted((s["y"], e.y))
        x, y, w, h = int(x1 * k), int(y1 * k), int((x2 - x1) * k), int((y2 - y1) * k)
        if w > 3 and h > 3:
            res["roi"] = (mon["left"] + x, mon["top"] + y, w, h)
            res["crop"] = cv2.cvtColor(shot[y:y + h, x:x + w], cv2.COLOR_BGRA2BGR)
        top.destroy()

    cv.bind("<ButtonPress-1>", down); cv.bind("<B1-Motion>", move); cv.bind("<ButtonRelease-1>", up)
    top.bind("<Escape>", lambda e: top.destroy())
    root.wait_window(top)
    root.deiconify()
    return (res["roi"], res["crop"]) if "roi" in res else None


class App:
    def __init__(self, root):
        self.root = root
        root.title("BUCKSHOT (Roblox) советник")
        root.attributes("-topmost", True); root.attributes("-alpha", 0.95)
        root.resizable(False, False)
        self.live, self.blank = tk.IntVar(value=0), tk.IntVar(value=0)
        self.me, self.maxhp = tk.IntVar(value=3), tk.IntVar(value=4)
        self.opp_hp = [tk.IntVar(value=3) for _ in range(3)]     # HP соперников (игроки 2-4)
        self.opp_n = [tk.IntVar(value=0) for _ in range(3)]      # сколько предметов у каждого
        self.opp_det = [{} for _ in range(3)]                    # какие именно предметы у каждого
        self.cuffed = [tk.BooleanVar() for _ in range(3)]
        self.tsel = tk.StringVar(value="Авто")
        self.sawed, self.voodoo_on = tk.BooleanVar(), tk.BooleanVar()
        self.mode = tk.StringVar(value="1 на 1")
        self.items = {n: tk.IntVar(value=0) for n in ITEMS}
        self.phone_pos = tk.IntVar(value=2)
        self.known, self.phone, self.spent = None, {}, 0
        # авто-чтение
        self.auto = tk.BooleanVar(value=True)
        self.track_shells = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Авто-чтение включено")
        self.pend, self.prev = {}, {}
        self.pend_shells, self.shells_gone = None, True
        self.pend_track, self.last_shell, self.start_total = None, None, 0
        self.new_round = False
        self.cal = None
        self.build()
        self.refresh()
        self.root.after(700, self.tick)

    # ---------- интерфейс ----------
    def build(self):
        pad = dict(padx=6, pady=3)
        bar = ttk.Frame(self.root, padding=(8, 6, 8, 0)); bar.pack(fill="x")
        ttk.Checkbutton(bar, text="⚡ Авто-чтение", variable=self.auto).pack(side="left")
        ttk.Checkbutton(bar, text="Патроны видны (следить)", variable=self.track_shells).pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="⚙ Калибровка", command=self.open_cal).pack(side="right")
        ttk.Label(self.root, textvariable=self.status, foreground="gray").pack(anchor="w", padx=10)
        m = ttk.Frame(self.root, padding=8); m.pack()

        self.advice = tk.Label(m, text="", font=("Arial", 15, "bold"), fg="#b00020",
                               wraplength=430, justify="left", height=4, anchor="w")
        self.advice.grid(row=0, column=0, columnspan=4, sticky="we", **pad)

        ttk.Label(m, text="Стол").grid(row=1, column=0)
        cb = ttk.Combobox(m, textvariable=self.mode, values=["1 на 1", "4 игрока"], state="readonly", width=9)
        cb.grid(row=1, column=1); cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Label(m, text="Макс. HP").grid(row=1, column=2)
        ttk.Spinbox(m, from_=1, to=6, width=4, textvariable=self.maxhp, command=self.refresh).grid(row=1, column=3)

        ttk.Label(m, text="Боевых").grid(row=2, column=0)
        ttk.Spinbox(m, from_=0, to=8, width=4, textvariable=self.live, command=self.refresh).grid(row=2, column=1)
        ttk.Label(m, text="Холостых").grid(row=2, column=2)
        ttk.Spinbox(m, from_=0, to=8, width=4, textvariable=self.blank, command=self.refresh).grid(row=2, column=3)

        ttk.Label(m, text="Мои HP").grid(row=3, column=0)
        ttk.Spinbox(m, from_=0, to=6, width=4, textvariable=self.me, command=self.refresh).grid(row=3, column=1)
        ttk.Checkbutton(m, text="Ствол спилен", variable=self.sawed, command=self.refresh).grid(row=3, column=2, columnspan=2, sticky="w")

        pf = ttk.LabelFrame(m, text="Соперники"); pf.grid(row=4, column=0, columnspan=4, sticky="we", **pad)
        for c, t in enumerate(("Игрок", "HP", "Предметов", "Наручники")):
            ttk.Label(pf, text=t, foreground="gray").grid(row=0, column=c, padx=4)
        for i in range(3):
            ttk.Label(pf, text=f"Игрок {i + 2}").grid(row=i + 1, column=0, padx=4)
            ttk.Spinbox(pf, from_=0, to=6, width=3, textvariable=self.opp_hp[i], command=self.refresh).grid(row=i + 1, column=1)
            ttk.Spinbox(pf, from_=0, to=12, width=3, textvariable=self.opp_n[i], command=self.refresh).grid(row=i + 1, column=2)
            ttk.Checkbutton(pf, variable=self.cuffed[i], command=self.refresh).grid(row=i + 1, column=3)
        ttk.Label(pf, text="Цель").grid(row=4, column=0, pady=3)
        tc = ttk.Combobox(pf, textvariable=self.tsel, values=["Авто", "Игрок 2", "Игрок 3", "Игрок 4"], state="readonly", width=9)
        tc.grid(row=4, column=1, columnspan=2); tc.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        fr = ttk.LabelFrame(m, text="Мои предметы"); fr.grid(row=5, column=0, columnspan=4, sticky="we", **pad)
        for i, n in enumerate(ITEMS):
            ttk.Label(fr, text=RU[n]).grid(row=i // 2, column=(i % 2) * 2, sticky="w", padx=4)
            ttk.Spinbox(fr, from_=0, to=8, width=3, textvariable=self.items[n], command=self.refresh).grid(row=i // 2, column=(i % 2) * 2 + 1)
        ttk.Checkbutton(fr, text="Вуду активно", variable=self.voodoo_on, command=self.refresh).grid(row=7, column=0, columnspan=2, sticky="w", padx=4)
        ttk.Button(fr, text="Использовал ВУДУ", command=self.use_voodoo).grid(row=7, column=2, columnspan=2, sticky="we", padx=4, pady=2)

        ttk.Button(m, text="📷 Прочитать патроны", command=self.read_shells).grid(row=6, column=0, columnspan=2, sticky="we", **pad)
        ttk.Button(m, text="📷 Прочитать всё", command=self.read_all).grid(row=6, column=2, columnspan=2, sticky="we", **pad)

        ttk.Button(m, text="Вышел БОЕВОЙ", command=lambda: self.shot("live")).grid(row=7, column=0, columnspan=2, sticky="we", **pad)
        ttk.Button(m, text="Вышел ХОЛОСТОЙ", command=lambda: self.shot("blank")).grid(row=7, column=2, columnspan=2, sticky="we", **pad)
        ttk.Button(m, text="Лупа: боевой", command=lambda: self.set_known("live")).grid(row=8, column=0, columnspan=2, sticky="we", **pad)
        ttk.Button(m, text="Лупа: холостой", command=lambda: self.set_known("blank")).grid(row=8, column=2, columnspan=2, sticky="we", **pad)

        ph = ttk.LabelFrame(m, text="Бёрнер-телефон: патрон №"); ph.grid(row=9, column=0, columnspan=4, sticky="we", **pad)
        ttk.Spinbox(ph, from_=1, to=12, width=4, textvariable=self.phone_pos).grid(row=0, column=0, **pad)
        ttk.Button(ph, text="боевой", command=lambda: self.set_phone("live")).grid(row=0, column=1, **pad)
        ttk.Button(ph, text="холостой", command=lambda: self.set_phone("blank")).grid(row=0, column=2, **pad)

        ttk.Button(m, text="Использован ИНВЕРТОР", command=self.invert).grid(row=10, column=0, columnspan=2, sticky="we", **pad)
        ttk.Button(m, text="Сброс раунда", command=self.reset).grid(row=10, column=2, columnspan=2, sticky="we", **pad)

    # ---------- калибровка (отдельное окно) ----------
    def open_cal(self):
        if self.cal and self.cal.winfo_exists():
            self.cal.lift(); return
        w = self.cal = tk.Toplevel(self.root)
        w.title("Калибровка"); w.attributes("-topmost", True)
        pad = dict(padx=6, pady=3)
        ttk.Label(w, text="Обводите область мышкой. Область HP: ряд молний. Область предметов: стол игрока.",
                  wraplength=360).grid(row=0, column=0, columnspan=2, **pad)
        ttk.Button(w, text="Область показа патронов", command=lambda: self.pick_roi("shells")).grid(row=1, column=0, columnspan=2, sticky="we", **pad)
        ttk.Button(w, text="Я: область HP", command=lambda: self.pick_roi("hp_me")).grid(row=2, column=0, sticky="we", **pad)
        ttk.Button(w, text="Я: область предметов", command=lambda: self.pick_roi("items")).grid(row=2, column=1, sticky="we", **pad)
        for i in range(3):
            ttk.Button(w, text=f"Игрок {i + 2}: HP", command=lambda i=i: self.pick_roi("hp_o", i)).grid(row=3 + i, column=0, sticky="we", **pad)
            ttk.Button(w, text=f"Игрок {i + 2}: предметы", command=lambda i=i: self.pick_roi("items_o", i)).grid(row=3 + i, column=1, sticky="we", **pad)
        ttk.Button(w, text="⚡ Авто-области HP (игра на весь экран)", command=self.auto_layout).grid(row=6, column=0, columnspan=2, sticky="we", **pad)
        self.tpl = ttk.Combobox(w, values=list(TEMPLATES.values()), state="readonly", width=22)
        self.tpl.current(0); self.tpl.grid(row=7, column=0, **pad)
        ttk.Button(w, text="Вырезать шаблон", command=self.cut_template).grid(row=7, column=1, sticky="we", **pad)

    def auto_layout(self):
        """Области HP четырёх панелей по раскладке стола 4 игроков (слева, сверху, справа и вы).
        Координаты заданы долями экрана, снятыми со скриншота 1919x1008, игра на весь экран."""
        mon = monitor()
        W, H = mon["width"], mon["height"]
        def box(x, y, w, h):
            return [mon["left"] + int(x / 1919 * W), mon["top"] + int(y / 1008 * H), int(w / 1919 * W), int(h / 1008 * H)]
        cfg["hp_me"] = box(870, 770, 190, 60)
        cfg["hp_o"] = [box(150, 480, 230, 190), box(770, 265, 120, 70), box(1320, 320, 170, 130)]
        save_cfg()
        messagebox.showinfo("Готово", "Области HP заданы: игрок 2 слева, игрок 3 сверху, игрок 4 справа.")

    def _select(self):
        wins = [self.cal] if self.cal and self.cal.winfo_exists() else []
        for x in wins: x.withdraw()
        r = select_region(self.root)
        for x in wins: x.deiconify()
        return r

    def pick_roi(self, key, idx=None):
        r = self._select()
        if r:
            if idx is None:
                cfg[key] = list(r[0])
            else:
                cfg[key][idx] = list(r[0])
            save_cfg()
            messagebox.showinfo("Готово", "Область сохранена.")

    def cut_template(self):
        name = [k for k, v in TEMPLATES.items() if v == self.tpl.get()][0]
        r = self._select()
        if r:
            cv2.imwrite(os.path.join(TPL_DIR, name + ".png"), r[1])
            messagebox.showinfo("Готово", f"Шаблон «{TEMPLATES[name]}» сохранён.")

    # ---------- чтение экрана ----------
    def counts_in(self, roi):
        g = cv2.cvtColor(grab(roi), cv2.COLOR_BGRA2GRAY)
        return {n: c for n in ITEMS if (c := count(g, n))}

    def bolts_in(self, roi):
        return count_bolts(cv2.cvtColor(grab(roi), cv2.COLOR_BGRA2BGR))

    def new_round_reset(self):
        self.known, self.phone, self.spent = None, {}, 0
        self.sawed.set(False); self.voodoo_on.set(False)
        for c in self.cuffed: c.set(False)
        self.new_round = True
        for k in [k for k in self.prev if str(k).startswith("hp")]:
            self.prev[k] = None

    def read_shells(self):
        if not cfg["shells"]:
            return messagebox.showwarning("Нет области", "Сначала задайте «Область показа патронов» или введите числа вручную.")
        L, B = count_shells(cv2.cvtColor(grab(cfg["shells"]), cv2.COLOR_BGRA2BGR))
        self.live.set(L); self.blank.set(B)
        self.new_round_reset()
        self.refresh()

    def read_all(self):
        """Однократное чтение всего, что настроено (без ожидания подтверждения)."""
        if cfg["items"]:
            c = self.counts_in(cfg["items"])
            for n in ITEMS: self.items[n].set(c.get(n, 0))
        if cfg["hp_me"]:
            self.me.set(self.bolts_in(cfg["hp_me"]))
        for i in range(3):
            if cfg["hp_o"][i]:
                self.opp_hp[i].set(self.bolts_in(cfg["hp_o"][i]))
            if cfg["items_o"][i]:
                self.opp_det[i] = self.counts_in(cfg["items_o"][i])
                self.opp_n[i].set(sum(self.opp_det[i].values()))
        self.refresh()

    def confirm(self, key, value):
        """True, если то же показание пришло два раза подряд и оно новое."""
        ok = self.pend.get(key) == value and self.prev.get(key) != value
        self.pend[key] = value
        if ok:
            self.prev[key] = value
        return ok

    def tick(self):
        try:
            if self.auto.get():
                self.auto_read()
        except Exception as e:
            self.status.set(f"Ошибка чтения: {e}")
        self.root.after(700, self.tick)

    def auto_read(self):
        changed = False

        # патроны: новый раунд = на экране появились патроны после того, как они пропадали
        if cfg["shells"]:
            L, B = count_shells(cv2.cvtColor(grab(cfg["shells"]), cv2.COLOR_BGRA2BGR))
            if L + B == 0:
                self.shells_gone, self.pend_shells = True, None
            elif self.shells_gone:
                if self.pend_shells == (L, B):
                    self.live.set(L); self.blank.set(B)
                    self.new_round_reset()
                    self.shells_gone, self.pend_shells = False, None
                    self.last_shell, self.start_total = (L, B), L + B
                    changed = True
                else:
                    self.pend_shells = (L, B)
            elif self.track_shells.get():
                if (L, B) == self.pend_track and (L, B) != self.last_shell and L + B < self.start_total:
                    self.live.set(L); self.blank.set(B)
                    self.spent = self.start_total - (L + B)
                    self.known = None; self.sawed.set(False)
                    self.last_shell = (L, B); changed = True
                self.pend_track = (L, B)

        # мои предметы
        if cfg["items"]:
            cur = self.counts_in(cfg["items"])
            if self.confirm("items_me", tuple(sorted(cur.items()))):
                for n in ITEMS: self.items[n].set(cur.get(n, 0))
                changed = True

        # мои HP (+ макс. HP в начале раунда)
        if cfg["hp_me"]:
            c = self.bolts_in(cfg["hp_me"])
            if self.confirm("hp_me", c):
                self.me.set(c); changed = True
                if self.new_round and c > 0:
                    self.maxhp.set(c); self.new_round = False

        # соперники: HP и предметы
        for i in range(3):
            if cfg["hp_o"][i]:
                c = self.bolts_in(cfg["hp_o"][i])
                if self.confirm(f"hp_o{i}", c):
                    self.opp_hp[i].set(c); changed = True
            if cfg["items_o"][i]:
                cur = self.counts_in(cfg["items_o"][i])
                if self.confirm(f"items_o{i}", tuple(sorted(cur.items()))):
                    self.opp_det[i] = cur
                    self.opp_n[i].set(sum(cur.values())); changed = True

        if changed:
            self.refresh()
            self.status.set("Обновлено " + time.strftime("%H:%M:%S"))

    # ---------- события ----------
    def cur_known(self):
        return self.known or self.phone.get(self.spent + 1)

    def shot(self, kind):
        v = self.live if kind == "live" else self.blank
        v.set(max(0, v.get() - 1))
        self.spent += 1
        self.known = None; self.sawed.set(False)
        self.refresh()

    def set_known(self, kind):
        self.known = kind; self.refresh()

    def set_phone(self, kind):
        self.phone[self.phone_pos.get()] = kind; self.refresh()

    def use_voodoo(self):
        v = self.items["voodoo"]
        v.set(max(0, v.get() - 1))
        self.voodoo_on.set(True)
        self.refresh()

    def invert(self):
        k = self.cur_known()
        if k:
            new = "blank" if k == "live" else "live"
            a, b = (self.live, self.blank) if k == "live" else (self.blank, self.live)
            a.set(max(0, a.get() - 1)); b.set(b.get() + 1)
            self.known = new
            self.phone.pop(self.spent + 1, None)
        self.refresh()

    def reset(self):
        for v in (self.live, self.blank): v.set(0)
        for v in self.items.values(): v.set(0)
        for v in self.opp_n: v.set(0)
        self.opp_det = [{} for _ in range(3)]
        self.new_round_reset()
        self.refresh()

    # ---------- логика советов ----------
    def active(self):
        idx = [0, 1, 2] if self.mode.get() == "4 игрока" else [0]
        alive = [i for i in idx if self.opp_hp[i].get() > 0]
        return alive or idx[:1]

    def target(self):
        act = self.active()
        sel = self.tsel.get()
        if sel != "Авто":
            j = int(sel.split()[-1]) - 2
            if j in act:
                return j
        return min(act, key=lambda i: (self.opp_hp[i].get(), i))

    def refresh(self):
        self.advice.config(text=self.compute())

    def best_steal(self, act, k, p, has, me):
        wants = []
        if k is None and not has("magnifier"): wants.append("magnifier")
        if k == "blank" and not has("inverter"): wants.append("inverter")
        if p >= 0.5 and not has("handcuffs"): wants.append("handcuffs")
        if p >= 0.5 and not has("saw"): wants.append("saw")
        if me <= 2 and not has("potion"): wants.append("potion")
        for w in wants:
            for i in act:
                if self.opp_det[i].get(w, 0) > 0:
                    return w, i
        return None

    def compute(self):
        try:
            L, B = self.live.get(), self.blank.get()
            me, mx = self.me.get(), self.maxhp.get()
            four = self.mode.get() == "4 игрока"
            act, ti = self.active(), self.target()
            hp = {i: self.opp_hp[i].get() for i in act}
            cnt = {i: self.opp_n[i].get() for i in act}
            tg, cuffed = hp[ti], self.cuffed[ti].get()
            has = lambda n: self.items[n].get() > 0
        except (tk.TclError, KeyError):
            return "Введите числа в поля."
        who = f"игрока {ti + 2}" if four else "соперника"
        weak = min(act, key=lambda i: (hp[i], i))
        if L + B == 0:
            return "Патронов нет. Нажмите «Прочитать патроны» (или введите числа) в новом раунде."
        k = self.cur_known()
        pos = f"[патрон №{self.spent + 1}] "
        if L == 0:
            return pos + "Боевых не осталось: стреляйте в СЕБЯ, это безопасно."
        if B == 0:
            return pos + f"Остались только боевые: выстрел в {who.upper()}."

        saw_ok = has("saw") and not self.sawed.get() and tg > 1 and (four or tg >= 3)
        p = L / (L + B) if k is None else (1.0 if k == "live" else 0.0)
        src = " (телефон)" if (k and not self.known) else ""

        if k is None and has("magnifier"):
            return pos + "Использовать ЛУПУ."
        mine = sum(v.get() for v in self.items.values()) - (1 if has("mirror") else 0)
        if has("mirror") and cnt:
            bi = max(cnt, key=cnt.get)
            if cnt[bi] > mine:
                whom = f"игроком {bi + 2}" if four else "соперником"
                return pos + f"ЗЕРКАЛО: обменять предметы с {whom} (у него {cnt[bi]}, у вас {mine})."
        if has("adrenaline"):
            st = self.best_steal(act, k, p, has, me)
            if st:
                w, i = st
                return pos + f"АДРЕНАЛИН: украсть {RU[w].upper()} у игрока {i + 2}."
            if k is None and not has("magnifier") and not any(self.opp_det[i] for i in act):
                return pos + "АДРЕНАЛИН: если у соперника есть лупа, украдите её."
        can_heal = has("potion") and me < mx and (four or me >= 2)
        if me <= 2 and can_heal:
            return pos + "Выпить ЗЕЛЬЕ (+1 HP)."
        vd = self.voodoo_on.get()
        if has("voodoo") and not vd and k != "blank":
            vt = f"игрока {weak + 2} (самый слабый; себя и выбывших выбрать нельзя)" if four else "соперника"
            kill = " При 1 HP он умрёт от перенаправленного удара." if hp[weak] <= 1 else ""
            return pos + f"ВУДУ на {vt}: следующий удар по вам уйдёт ему, выстрел в себя станет безопасным.{kill}"
        if vd and k != "live":
            kill = f" Боевой убьёт игрока с малым HP ({hp[weak]})." if hp[weak] <= (2 if self.sawed.get() and four else 1) else ""
            return pos + f"ВУДУ активно: выстрел в СЕБЯ безопасен (холостой оставит ход, боевой ударит выбранного игрока, x2 с ножовкой).{kill} После боевого снимите галочку «Вуду активно»."
        if has("cube") and mx > me >= 2 and max(hp.values()) > me:
            return pos + "КОСТИ: чётная сумма +1 HP, нечётная −1 HP (50/50). Оправдано, пока вы отстаёте по HP и не на последней жизни."
        if k == "blank" and has("inverter"):
            return pos + f"ИНВЕРТОР: холостой станет боевым{src}, затем выстрел в {who.upper()}."
        if p >= 0.5:
            if has("handcuffs") and not cuffed:
                return pos + f"Надеть НАРУЧНИКИ на {who}, затем стрелять."
            if k == "live" and saw_ok and vd and four:
                return pos + "Взять НОЖОВКУ и выстрелить (в цель или в себя: при вуду урон x2 уйдёт выбранному игроку)."
            if k == "live" and saw_ok:
                return pos + f"Взять НОЖОВКУ, затем выстрел в {who.upper()} (урон x2){src}."
            return pos + f"Выстрел в {who.upper()} (HP {tg}, шанс боевого {p:.0%}){src}."
        if has("soda") and 0.3 < p and k is None:
            return pos + f"ГАЗИРОВКА: выбросить текущий патрон (шанс боевого {p:.0%}). Затем отметьте, какой вышел."
        return pos + f"Выстрел в СЕБЯ (шанс боевого {p:.0%}){src}. Если холостой, ход останется у вас."


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
