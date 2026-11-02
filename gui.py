import sys
import os
import time
import ctypes
import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk

# Импортируем наши модули
from config import cfg, save_cfg, ITEMS, RU
import vision
import strategy

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass


def select_region_ui(root):
    root.withdraw()
    time.sleep(0.3)
    shot = vision.grab_screen()
    mon = vision.get_monitor()
    img = Image.fromarray(cv2.cvtColor(shot, cv2.COLOR_BGRA2RGB))

    top = tk.Toplevel(root)
    top.attributes("-fullscreen", True, "-topmost", True)
    cv = tk.Canvas(top, cursor="cross", highlightthickness=0)
    cv.pack(fill="both", expand=True)
    top.update_idletasks()

    sw, sh = top.winfo_screenwidth(), top.winfo_screenheight()
    photo = ImageTk.PhotoImage(img.resize((sw, sh)))
    cv.create_image(0, 0, image=photo, anchor="nw")
    cv.image = photo
    cv.create_text(sw // 2, 30, fill="#ff3333", font=("Segoe UI", 18, "bold"),
                   text="Выделите область мышкой (Esc — отмена)")
    res = {}

    def down(e):
        res["x"], res["y"] = e.x, e.y
        res["r"] = cv.create_rectangle(e.x, e.y, e.x, e.y, outline="#ff3333", width=2)

    def move(e):
        if "r" in res:
            cv.coords(res["r"], res["x"], res["y"], e.x, e.y)

    def up(e):
        if "r" not in res:
            return
        k = img.width / sw
        x1, x2 = sorted((res["x"], e.x))
        y1, y2 = sorted((res["y"], e.y))
        x, y, w, h = int(x1 * k), int(y1 * k), int((x2 - x1) * k), int((y2 - y1) * k)
        if w > 3 and h > 3:
            res["roi"] = (mon["left"] + x, mon["top"] + y, w, h)
            res["crop"] = cv2.cvtColor(shot[y:y + h, x:x + w], cv2.COLOR_BGRA2BGR)
        top.destroy()

    cv.bind("<ButtonPress-1>", down)
    cv.bind("<B1-Motion>", move)
    cv.bind("<ButtonRelease-1>", up)
    top.bind("<Escape>", lambda e: top.destroy())
    root.wait_window(top)
    root.deiconify()
    return (res["roi"], res["crop"]) if "roi" in res else None


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("🤖 BUCKSHOT AI")
        self.root.attributes("-topmost", True, "-alpha", 0.96)
        self.root.resizable(False, False)

        # Настройка Темной Темы
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure(".", background="#1e1e24", foreground="#f5f5f7", font=("Segoe UI", 10))
        self.style.configure("TLabel", background="#1e1e24", foreground="#f5f5f7")
        self.style.configure("TLabelframe", background="#1e1e24", foreground="#a1a1aa", bordercolor="#33333c")
        self.style.configure("TLabelframe.Label", background="#1e1e24", foreground="#38bdf8",
                             font=("Segoe UI", 10, "bold"))
        self.style.configure("TButton", background="#2d2d38", foreground="#f5f5f7", borderwidth=0, focuscolor="none")
        self.style.map("TButton", background=[("active", "#3b3b4a")])
        self.style.configure("Action.TButton", background="#0284c7", foreground="white",
                             font=("Segoe UI", 10, "bold"))
        self.style.map("Action.TButton", background=[("active", "#0369a1")])

        # Переменные интерфейса
        self.live, self.blank = tk.IntVar(value=0), tk.IntVar(value=0)
        self.me, self.maxhp = tk.IntVar(value=3), tk.IntVar(value=4)
        self.opp_hp = [tk.IntVar(value=3) for _ in range(3)]
        self.opp_n = [tk.IntVar(value=0) for _ in range(3)]
        self.opp_det = [{} for _ in range(3)]
        self.cuffed = [tk.BooleanVar() for _ in range(3)]
        self.tsel = tk.StringVar(value="Авто")
        self.sawed, self.voodoo_on = tk.BooleanVar(), tk.BooleanVar()
        self.mode = tk.StringVar(value="1 на 1")
        self.items = {n: tk.IntVar(value=0) for n in ITEMS}
        self.phone_pos = tk.IntVar(value=2)

        self.known, self.phone, self.spent = None, {}, 0
        self.auto = tk.BooleanVar(value=True)
        self.track_shells = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Система запущена")

        self.pend, self.prev = {}, {}
        self.pend_shells, self.shells_gone = None, True
        self.pend_track, self.last_shell, self.start_total = None, None, 0
        self.new_round = False
        self.cal = None

        self.build_ui()
        self.refresh()
        self.root.after(700, self.tick)

    def build_ui(self):
        pad = dict(padx=5, pady=3)

        bar = ttk.Frame(self.root, padding=6, style="TFrame")
        bar.pack(fill="x")
        ttk.Checkbutton(bar, text="⚡ Авто-скан", variable=self.auto).pack(side="left", padx=5)
        ttk.Checkbutton(bar, text="Следить за патронами", variable=self.track_shells).pack(side="left", padx=5)
        ttk.Button(bar, text="⚙ Настройки ROI", command=self.open_cal).pack(side="right", padx=5)

        lbl_status = tk.Label(self.root, textvariable=self.status, font=("Segoe UI", 9, "italic"),
                              bg="#1e1e24", fg="#71717a")
        lbl_status.pack(anchor="w", padx=12)

        m = ttk.Frame(self.root, padding=10)
        m.pack()

        self.advice = tk.Label(m, text="", font=("Segoe UI", 13, "bold"), fg="#38bdf8", bg="#151518",
                               wraplength=440, justify="left", height=4, anchor="w", padx=10, relief="solid", bd=1)
        self.advice.grid(row=0, column=0, columnspan=4, sticky="we", pady=(0, 10))

        ttk.Label(m, text="Режим стола:").grid(row=1, column=0, sticky="w", **pad)
        cb = ttk.Combobox(m, textvariable=self.mode, values=["1 на 1", "4 игрока"], state="readonly", width=10)
        cb.grid(row=1, column=1, sticky="w", **pad)
        cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        ttk.Label(m, text="Макс HP:").grid(row=1, column=2, sticky="w", **pad)
        ttk.Spinbox(m, from_=1, to=6, width=5, textvariable=self.maxhp,
                    command=self.refresh).grid(row=1, column=3, sticky="w", **pad)

        ttk.Label(m, text="🔴 Боевых:").grid(row=2, column=0, sticky="w", **pad)
        ttk.Spinbox(m, from_=0, to=8, width=5, textvariable=self.live,
                    command=self.refresh).grid(row=2, column=1, sticky="w", **pad)

        ttk.Label(m, text="⚪ Холостых:").grid(row=2, column=2, sticky="w", **pad)
        ttk.Spinbox(m, from_=0, to=8, width=5, textvariable=self.blank,
                    command=self.refresh).grid(row=2, column=3, sticky="w", **pad)

        ttk.Label(m, text="Мои HP:").grid(row=3, column=0, sticky="w", **pad)
        ttk.Spinbox(m, from_=0, to=6, width=5, textvariable=self.me,
                    command=self.refresh).grid(row=3, column=1, sticky="w", **pad)
        ttk.Checkbutton(m, text="Ствол отпилен", variable=self.sawed,
                        command=self.refresh).grid(row=3, column=2, columnspan=2, sticky="w", **pad)

        pf = ttk.LabelFrame(m, text=" Мониторинг оппонентов ", padding=6)
        pf.grid(row=4, column=0, columnspan=4, sticky="we", pady=8)
        for c, t in enumerate(("Игрок", "HP", "Итемы", "Связан")):
            ttk.Label(pf, text=t, foreground="#71717a",
                      font=("Segoe UI", 9, "bold")).grid(row=0, column=c, padx=6)
        for i in range(3):
            ttk.Label(pf, text=f"Игрок {i + 2}").grid(row=i + 1, column=0, padx=6, pady=2)
            ttk.Spinbox(pf, from_=0, to=6, width=4, textvariable=self.opp_hp[i],
                        command=self.refresh).grid(row=i + 1, column=1, padx=2)
            ttk.Spinbox(pf, from_=0, to=12, width=4, textvariable=self.opp_n[i],
                        command=self.refresh).grid(row=i + 1, column=2, padx=2)
            ttk.Checkbutton(pf, variable=self.cuffed[i],
                            command=self.refresh).grid(row=i + 1, column=3, padx=10)

        ttk.Label(pf, text="Приоритет цели:").grid(row=4, column=0, columnspan=2, sticky="w", pady=4)
        tc = ttk.Combobox(pf, textvariable=self.tsel, values=["Авто", "Игрок 2", "Игрок 3", "Игрок 4"],
                          state="readonly", width=10)
        tc.grid(row=4, column=2, columnspan=2, sticky="we", pady=4)
        tc.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        fr = ttk.LabelFrame(m, text=" Мой инвентарь ", padding=6)
        fr.grid(row=5, column=0, columnspan=4, sticky="we", pady=4)
        for i, n in enumerate(ITEMS):
            ttk.Label(fr, text=RU[n]).grid(row=i // 2, column=(i % 2) * 2, sticky="w", padx=4, pady=1)
            ttk.Spinbox(fr, from_=0, to=8, width=4, textvariable=self.items[n],
                        command=self.refresh).grid(row=i // 2, column=(i % 2) * 2 + 1, pady=1)
        ttk.Checkbutton(fr, text="Вуду кукла активна", variable=self.voodoo_on,
                        command=self.refresh).grid(row=7, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Button(fr, text="Юзнул ВУДУ", command=self.use_voodoo,
                   width=12).grid(row=7, column=2, columnspan=2, sticky="we", padx=4, pady=4)

        btn_f = ttk.Frame(m)
        btn_f.grid(row=6, column=0, columnspan=4, sticky="we", pady=6)
        ttk.Button(btn_f, text="📷 Скан патронов", command=self.read_shells,
                   width=18).pack(side="left", expand=True, padx=2)
        ttk.Button(btn_f, text="📷 Скан всего стола", command=self.read_all,
                   width=18).pack(side="right", expand=True, padx=2)

        act_f = ttk.Frame(m)
        act_f.grid(row=7, column=0, columnspan=4, sticky="we")
        ttk.Button(act_f, text="Вылетел БОЕВОЙ", style="Action.TButton",
                   command=lambda: self.shot("live")).pack(side="left", expand=True, padx=2, pady=2)
        ttk.Button(act_f, text="Вылетел ХОЛОСТОЙ",
                   command=lambda: self.shot("blank")).pack(side="right", expand=True, padx=2, pady=2)

        lp_f = ttk.Frame(m)
        lp_f.grid(row=8, column=0, columnspan=4, sticky="we")
        ttk.Button(lp_f, text="🔎 Лупа: Боевой",
                   command=lambda: self.set_known("live")).pack(side="left", expand=True, padx=2, pady=2)
        ttk.Button(lp_f, text="🔎 Лупа: Холостой",
                   command=lambda: self.set_known("blank")).pack(side="right", expand=True, padx=2, pady=2)

        ph = ttk.LabelFrame(m, text=" Бёрнер-телефон ", padding=4)
        ph.grid(row=9, column=0, columnspan=4, sticky="we", pady=4)

        ttk.Label(ph, text="№ патрона:").grid(row=0, column=0, **pad)
        ttk.Spinbox(ph, from_=1, to=12, width=4, textvariable=self.phone_pos).grid(row=0, column=1, **pad)
        ttk.Button(ph, text="Боевой", command=lambda: self.set_phone("live"),
                   width=8).grid(row=0, column=2, **pad)
        ttk.Button(ph, text="Холостой", command=lambda: self.set_phone("blank"),
                   width=8).grid(row=0, column=3, **pad)

        ut_f = ttk.Frame(m)
        ut_f.grid(row=10, column=0, columnspan=4, sticky="we", pady=4)
        ttk.Button(ut_f, text="Использовать ИНВЕРТОР",
                   command=self.invert).pack(side="left", expand=True, padx=2)
        ttk.Button(ut_f, text="🔄 Сброс раунда",
                   command=self.reset).pack(side="right", expand=True, padx=2)

    def open_cal(self):
        if self.cal and self.cal.winfo_exists():
            self.cal.lift()
            return
        w = self.cal = tk.Toplevel(self.root)
        w.title("Калибровка зон")
        w.attributes("-topmost", True)
        w.configure(background="#1e1e24")
        pad = dict(padx=6, pady=3)
        ttk.Label(w, text="Укажите точные зоны для анализа:",
                  font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=2, **pad, pady=5)
        ttk.Button(w, text="Зона отображения патронов",
                   command=lambda: self.pick_roi("shells")).grid(row=1, column=0, columnspan=2, sticky="we", **pad)
        ttk.Button(w, text="Моя зона HP",
                   command=lambda: self.pick_roi("hp_me")).grid(row=2, column=0, sticky="we", **pad)
        ttk.Button(w, text="Моя зона предметов",
                   command=lambda: self.pick_roi("items")).grid(row=2, column=1, sticky="we", **pad)
        for i in range(3):
            ttk.Button(w, text=f"Игрок {i + 2}: зона HP",
                       command=lambda idx=i: self.pick_roi("hp_o", idx)).grid(row=3 + i, column=0, sticky="we", **pad)
            ttk.Button(w, text=f"Игрок {i + 2}: зона предметов",
                       command=lambda idx=i: self.pick_roi("items_o", idx)).grid(row=3 + i, column=1, sticky="we", **pad)
        ttk.Button(w, text="⚡ Авто-раскладка HP (Фуллскрин)",
                   command=self.auto_layout).grid(row=6, column=0, columnspan=2, sticky="we", **pad, pady=5)
        self.tpl = ttk.Combobox(w, values=[RU[k] for k in ITEMS], state="readonly", width=20)
        self.tpl.current(0)
        self.tpl.grid(row=7, column=0, **pad)
        ttk.Button(w, text="Вырезать паттерн",
                   command=self.cut_template).grid(row=7, column=1, sticky="we", **pad)

    def auto_layout(self):
        mon = vision.get_monitor()
        W, H = mon[0]["width"], mon[0]["height"]

        def box(x, y, w, h):
            return [mon[0]["left"] + int(x / 1919 * W), mon[0]["top"] + int(y / 1008 * H),
                    int(w / 1919 * W), int(h / 1008 * H)]

        cfg["hp_me"] = box(870, 770, 190, 60)
        cfg["hp_o"] = [box(150, 480, 230, 190), box(770, 265, 120, 70), box(1320, 320, 170, 130)]
        save_cfg()
        messagebox.showinfo("Успех", "Автоматические координаты для HP выставлены.")

    def pick_roi(self, key, idx=None):
        if self.cal:
            self.cal.withdraw()
        r = select_region_ui(self.root)
        if self.cal:
            self.cal.deiconify()
        if r:
            if idx is None:
                cfg[key] = list(r[0])
            else:
                cfg[key][idx] = list(r[0])
            save_cfg()
            messagebox.showinfo("Успех", "Зона успешно обновлена.")

    def cut_template(self):
        target_name = [k for k, v in RU.items() if v == self.tpl.get()][0]
        if self.cal:
            self.cal.withdraw()
        r = select_region_ui(self.root)
        if self.cal:
            self.cal.deiconify()
        if r:
            cv2.imwrite(os.path.join(vision.TPL_DIR, target_name + ".png"), r[1])
            messagebox.showinfo("Успех", f"Шаблон для [{self.tpl.get()}] сохранен.")

    def new_round_reset(self):
        self.known, self.phone, self.spent = None, {}, 0
        self.sawed.set(False)
        self.voodoo_on.set(False)
        for c in self.cuffed:
            c.set(False)
        self.new_round = True
        for k in [k for k in self.prev if str(k).startswith("hp")]:
            self.prev[k] = None

    def read_shells(self):
        if not cfg["shells"]:
            return messagebox.showwarning("Внимание", "Не задана область распознавания патронов.")
        L, B = vision.count_shells(cv2.cvtColor(vision.grab_screen(cfg["shells"]), cv2.COLOR_BGRA2BGR))
        self.live.set(L)
        self.blank.set(B)
        self.new_round_reset()
        self.refresh()

    def read_all(self):
        if cfg["items"]:
            c = vision.get_counts_in_roi(cfg["items"])
            for n in ITEMS:
                self.items[n].set(c.get(n, 0))
        if cfg["hp_me"]:
            self.me.set(vision.get_bolts_in_roi(cfg["hp_me"]))
        for i in range(3):
            if cfg["hp_o"][i]:
                self.opp_hp[i].set(vision.get_bolts_in_roi(cfg["hp_o"][i]))
            if cfg["items_o"][i]:
                self.opp_det[i] = vision.get_counts_in_roi(cfg["items_o"][i])
                self.opp_n[i].set(sum(self.opp_det[i].values()))
        self.refresh()

    def confirm(self, key, value):
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
            self.status.set(f"Ошибка парсинга: {e}")
        self.root.after(700, self.tick)

    def auto_read(self):
        changed = False
        if cfg["shells"]:
            L, B = vision.count_shells(cv2.cvtColor(vision.grab_screen(cfg["shells"]), cv2.COLOR_BGRA2BGR))
            if L + B == 0:
                self.shells_gone, self.pend_shells = True, None
            elif self.shells_gone:
                if self.pend_shells == (L, B):
                    self.live.set(L)
                    self.blank.set(B)
                    self.new_round_reset()
                    self.shells_gone, self.pend_shells = False, None
                    self.last_shell, self.start_total = (L, B), L + B
                    changed = True
                else:
                    self.pend_shells = (L, B)
            elif self.track_shells.get():
                if (L, B) == self.pend_track and (L, B) != self.last_shell and L + B < self.start_total:
                    self.live.set(L)
                    self.blank.set(B)
                    self.spent = self.start_total - (L + B)
                    self.known = None
                    self.sawed.set(False)
                    self.last_shell = (L, B)
                    changed = True
                self.pend_track = (L, B)
        if cfg["items"]:
            cur = vision.get_counts_in_roi(cfg["items"])
            if self.confirm("items_me", tuple(sorted(cur.items()))):
                for n in ITEMS:
                    self.items[n].set(cur.get(n, 0))
                changed = True
        if cfg["hp_me"]:
            c = vision.get_bolts_in_roi(cfg["hp_me"])
            if self.confirm("hp_me", c):
                self.me.set(c)
                changed = True
            if self.new_round and c > 0:
                self.maxhp.set(c)
                self.new_round = False
        for i in range(3):
            if cfg["hp_o"][i]:
                c = vision.get_bolts_in_roi(cfg["hp_o"][i])
                if self.confirm(f"hp_o{i}", c):
                    self.opp_hp[i].set(c)
                    changed = True
            if cfg["items_o"][i]:
                cur = vision.get_counts_in_roi(cfg["items_o"][i])
                if self.confirm(f"items_o{i}", tuple(sorted(cur.items()))):
                    self.opp_det[i] = cur
                    self.opp_n[i].set(sum(cur.values()))
                    changed = True
        if changed:
            self.refresh()
            self.status.set("Данные обновлены в " + time.strftime("%H:%M:%S"))

    def shot(self, kind):
        v = self.live if kind == "live" else self.blank
        v.set(max(0, v.get() - 1))
        self.spent += 1
        self.known = None
        self.sawed.set(False)
        self.refresh()

    def set_known(self, kind):
        self.known = kind
        self.refresh()

    def set_phone(self, kind):
        self.phone[self.phone_pos.get()] = kind
        self.refresh()

    def use_voodoo(self):
        self.items["voodoo"].set(max(0, self.items["voodoo"].get() - 1))
        self.voodoo_on.set(True)
        self.refresh()

    def invert(self):
        k = self.known or self.phone.get(self.spent + 1)
        if k:
            new = "blank" if k == "live" else "live"
            a, b = (self.live, self.blank) if k == "live" else (self.blank, self.live)
            a.set(max(0, a.get() - 1))
            b.set(b.get() + 1)
            self.known = new
            self.phone.pop(self.spent + 1, None)
            self.refresh()

    def reset(self):
        for v in (self.live, self.blank):
            v.set(0)
        for v in self.items.values():
            v.set(0)
        for v in self.opp_n:
            v.set(0)
        self.opp_det = [{} for _ in range(3)]
        self.new_round_reset()
        self.refresh()

    def refresh(self):
        idx = [0, 1, 2] if self.mode.get() == "4 игрока" else [0]
        active_players = [i for i in idx if self.opp_hp[i].get() > 0]
        if not active_players:
            active_players = idx[:1]
        target_idx = active_players[0]
        if self.tsel.get() != "Авто" and "Игрок" in self.tsel.get():
            try:
                selected_target = int(self.tsel.get().split()[-1]) - 2
                if selected_target in active_players:
                    target_idx = selected_target
            except Exception:
                pass
        game_state = {
            "live": self.live.get(), "blank": self.blank.get(),
            "me": self.me.get(), "maxhp": self.maxhp.get(),
            "mode": self.mode.get(), "active": active_players, "target": target_idx,
            "opp_hp": {i: self.opp_hp[i].get() for i in active_players},
            "opp_n": {i: self.opp_n[i].get() for i in active_players},
            "opp_det": self.opp_det,
            "cuffed": {i: self.cuffed[i].get() for i in active_players},
            "my_items": {n: self.items[n].get() for n in ITEMS},
            "sawed": self.sawed.get(), "voodoo_on": self.voodoo_on.get(),
            "cur_known": self.known or self.phone.get(self.spent + 1),
            "is_known_direct": self.known is not None,
            "spent": self.spent
        }
        self.advice.config(text=strategy.compute_advice(game_state))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()