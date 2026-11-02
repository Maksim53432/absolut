import os
import time
import ctypes
import tkinter as tk
from tkinter import messagebox
import cv2
from PIL import Image, ImageTk

import customtkinter as ctk

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
    try:
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
        return (res["roi"], res["crop"]) if "roi" in res else None
    finally:
        root.deiconify()


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🤖 BUCKSHOT AI v2")
        self.geometry("900x720")
        self.minsize(820, 640)
        self.attributes("-topmost", True, "-alpha", 0.97)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

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
        self.after(700, self.tick)

    def _cal_alive(self):
        return self.cal is not None and self.cal.winfo_exists()

    def _cal_hide(self):
        if self._cal_alive():
            self.cal.withdraw()

    def _cal_show(self):
        if self._cal_alive():
            self.cal.deiconify()

    # ---------- UI ----------
    def build_ui(self):
        top = ctk.CTkFrame(self, height=42)
        top.pack(fill="x", padx=10, pady=(10, 0))
        ctk.CTkCheckBox(top, text="⚡ Авто-скан", variable=self.auto).pack(side="left", padx=8, pady=6)
        ctk.CTkCheckBox(top, text="Следить за патронами", variable=self.track_shells).pack(side="left", padx=8)
        ctk.CTkButton(top, text="⚙ Настройки ROI", width=140,
                      command=self.open_cal, fg_color="#7c3aed").pack(side="right", padx=8, pady=6)

        ctk.CTkLabel(self, textvariable=self.status, text_color="#9ca3af",
                     font=ctk.CTkFont(size=11, slant="italic"), anchor="w").pack(fill="x", padx=14)

        self.advice = ctk.CTkLabel(self, text="", text_color="#38bdf8",
                                   font=ctk.CTkFont(size=15, weight="bold"),
                                   wraplength=860, justify="left", anchor="w",
                                   fg_color="#111827", corner_radius=10,
                                   height=80)
        self.advice.pack(fill="x", padx=14, pady=10)

        self.tabs = ctk.CTkTabview(self, anchor="nw")
        self.tabs.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        self.tab_main = self.tabs.add("Стол")
        self.tab_opp = self.tabs.add("Оппоненты")
        self.tab_items = self.tabs.add("Инвентарь")
        self.tab_actions = self.tabs.add("Действия")

        self._build_main_tab()
        self._build_opp_tab()
        self._build_items_tab()
        self._build_actions_tab()

    def _spin(self, parent, var, frm=0, to=8, width=60, command=None):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        e = ctk.CTkEntry(f, textvariable=var, width=width, justify="center")
        e.pack(side="left")

        def _get():
            try:
                return int(var.get())
            except (tk.TclError, ValueError):
                return frm

        def up():
            var.set(min(to, _get() + 1))
            if command:
                command()

        def down():
            var.set(max(frm, _get() - 1))
            if command:
                command()

        ctk.CTkButton(f, text="▲", width=24, height=24, command=up,
                      fg_color="#374151", hover_color="#4b5563").pack(side="left", padx=(2, 0))
        ctk.CTkButton(f, text="▼", width=24, height=24, command=down,
                      fg_color="#374151", hover_color="#4b5563").pack(side="left", padx=(2, 0))
        return f

    def _build_main_tab(self):
        p = self.tab_main
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text="Режим стола:", width=110, anchor="w").pack(side="left")
        ctk.CTkOptionMenu(row, values=["1 на 1", "4 игрока"], variable=self.mode,
                          width=140, command=lambda _: self.refresh()).pack(side="left", padx=6)
        ctk.CTkLabel(row, text="Макс HP:", width=90, anchor="w").pack(side="left", padx=(20, 0))
        self._spin(row, self.maxhp, 1, 6, command=self.refresh).pack(side="left", padx=4)

        row2 = ctk.CTkFrame(p, fg_color="transparent")
        row2.pack(fill="x", pady=4)
        ctk.CTkLabel(row2, text="🔴 Боевых:", width=110, anchor="w").pack(side="left")
        self._spin(row2, self.live, 0, 8, command=self.refresh).pack(side="left", padx=4)
        ctk.CTkLabel(row2, text="⚪ Холостых:", width=110, anchor="w").pack(side="left", padx=(20, 0))
        self._spin(row2, self.blank, 0, 8, command=self.refresh).pack(side="left", padx=4)

        row3 = ctk.CTkFrame(p, fg_color="transparent")
        row3.pack(fill="x", pady=4)
        ctk.CTkLabel(row3, text="Мои HP:", width=110, anchor="w").pack(side="left")
        self._spin(row3, self.me, 0, 6, command=self.refresh).pack(side="left", padx=4)
        ctk.CTkCheckBox(row3, text="Ствол отпилен", variable=self.sawed,
                        command=self.refresh).pack(side="left", padx=20)

        btn = ctk.CTkFrame(p, fg_color="transparent")
        btn.pack(fill="x", pady=(16, 4))
        ctk.CTkButton(btn, text="📷 Скан патронов", command=self.read_shells,
                      width=200, height=40, fg_color="#2563eb").pack(side="left", expand=True, padx=4)
        ctk.CTkButton(btn, text="📷 Скан всего стола", command=self.read_all,
                      width=200, height=40, fg_color="#2563eb").pack(side="right", expand=True, padx=4)

        ctk.CTkButton(p, text="🔄 Сброс раунда", command=self.reset,
                      fg_color="#dc2626", hover_color="#b91c1c", height=36).pack(fill="x", pady=(20, 4))

    def _build_opp_tab(self):
        p = self.tab_opp
        header = ctk.CTkFrame(p, fg_color="transparent")
        header.pack(fill="x", pady=(0, 6))
        for text, w in [("Игрок", 100), ("HP", 90), ("Итемы", 90), ("Связан", 70)]:
            ctk.CTkLabel(header, text=text, width=w, anchor="w",
                         font=ctk.CTkFont(weight="bold"), text_color="#9ca3af").pack(side="left", padx=4)

        for i in range(3):
            row = ctk.CTkFrame(p, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=f"Игрок {i + 2}", width=100, anchor="w").pack(side="left")
            self._spin(row, self.opp_hp[i], 0, 6, command=self.refresh).pack(side="left", padx=4)
            self._spin(row, self.opp_n[i], 0, 12, command=self.refresh).pack(side="left", padx=4)
            ctk.CTkCheckBox(row, text="", variable=self.cuffed[i],
                            command=self.refresh, width=24).pack(side="left", padx=20)

        ctk.CTkLabel(p, text="", height=4).pack()
        ctk.CTkLabel(p, text="Приоритет цели:", anchor="w").pack(fill="x", pady=(10, 2))
        ctk.CTkOptionMenu(p, values=["Авто", "Игрок 2", "Игрок 3", "Игрок 4"],
                          variable=self.tsel, command=lambda _: self.refresh(),
                          width=180).pack(fill="x", pady=4)

    def _build_items_tab(self):
        p = self.tab_items
        grid = ctk.CTkFrame(p, fg_color="transparent")
        grid.pack(fill="both", expand=True, pady=4)
        for col in range(2):
            grid.grid_columnconfigure(col, weight=1)
        for i, n in enumerate(ITEMS):
            r, c = i // 2, i % 2
            cell = ctk.CTkFrame(grid, fg_color="#1f2937", corner_radius=8)
            cell.grid(row=r, column=c, padx=6, pady=4, sticky="ew")
            ctk.CTkLabel(cell, text=RU[n], anchor="w").pack(side="left", padx=8, pady=6)
            self._spin(cell, self.items[n], 0, 8, command=self.refresh, width=46).pack(side="right", padx=6)

        ctk.CTkCheckBox(p, text="Вуду кукла активна", variable=self.voodoo_on,
                        command=self.refresh).pack(anchor="w", pady=(14, 4))
        ctk.CTkButton(p, text="Юзнул ВУДУ", command=self.use_voodoo,
                      fg_color="#7c3aed", height=34).pack(fill="x", pady=4)

    def _build_actions_tab(self):
        p = self.tab_actions

        ctk.CTkLabel(p, text="Выстрел", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(6, 2))
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkButton(row, text="Вылетел БОЕВОЙ", command=lambda: self.shot("live"),
                      fg_color="#dc2626", hover_color="#b91c1c", height=38).pack(side="left", expand=True, padx=4)
        ctk.CTkButton(row, text="Вылетел ХОЛОСТОЙ", command=lambda: self.shot("blank"),
                      fg_color="#374151", hover_color="#4b5563", height=38).pack(side="right", expand=True, padx=4)

        ctk.CTkLabel(p, text="Лупа (узнать патрон)", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(14, 2))
        row2 = ctk.CTkFrame(p, fg_color="transparent")
        row2.pack(fill="x", pady=4)
        ctk.CTkButton(row2, text="🔎 Боевой", command=lambda: self.set_known("live"),
                      height=34).pack(side="left", expand=True, padx=4)
        ctk.CTkButton(row2, text="🔎 Холостой", command=lambda: self.set_known("blank"),
                      height=34).pack(side="right", expand=True, padx=4)

        ctk.CTkLabel(p, text="Бёрнер-телефон", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(14, 2))
        row3 = ctk.CTkFrame(p, fg_color="transparent")
        row3.pack(fill="x", pady=4)
        ctk.CTkLabel(row3, text="№ патрона:").pack(side="left")
        self._spin(row3, self.phone_pos, 1, 12, width=46).pack(side="left", padx=6)
        ctk.CTkButton(row3, text="Боевой", command=lambda: self.set_phone("live"),
                      width=100).pack(side="left", padx=6)
        ctk.CTkButton(row3, text="Холостой", command=lambda: self.set_phone("blank"),
                      width=100).pack(side="left", padx=6)

        ctk.CTkLabel(p, text="", height=6).pack()
        ctk.CTkButton(p, text="Использовать ИНВЕРТОР", command=self.invert,
                      fg_color="#7c3aed", height=36).pack(fill="x", pady=6)

    # ---------- Калибровка ----------
    def open_cal(self):
        if self._cal_alive():
            self.cal.lift()
            return
        w = self.cal = ctk.CTkToplevel(self)
        w.title("Калибровка зон")
        w.attributes("-topmost", True)
        w.geometry("520x420")

        ctk.CTkLabel(w, text="Укажите точные зоны для анализа",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=10)

        btns = [
            ("Зона отображения патронов", lambda: self.pick_roi("shells")),
            ("Моя зона HP", lambda: self.pick_roi("hp_me")),
            ("Моя зона предметов", lambda: self.pick_roi("items")),
        ]
        for i in range(3):
            btns.append((f"Игрок {i + 2}: зона HP", lambda idx=i: self.pick_roi("hp_o", idx)))
            btns.append((f"Игрок {i + 2}: зона предметов", lambda idx=i: self.pick_roi("items_o", idx)))

        for text, cmd in btns:
            ctk.CTkButton(w, text=text, command=cmd, height=30).pack(fill="x", padx=20, pady=3)

        ctk.CTkButton(w, text="⚡ Авто-раскладка HP (Фуллскрин)",
                      command=self.auto_layout, fg_color="#7c3aed").pack(fill="x", padx=20, pady=(12, 4))

        self.tpl = ctk.CTkOptionMenu(w, values=[RU[k] for k in ITEMS])
        self.tpl.set(RU[ITEMS[0]])
        self.tpl.pack(fill="x", padx=20, pady=(10, 4))
        ctk.CTkButton(w, text="Вырезать паттерн",
                      command=self.cut_template).pack(fill="x", padx=20, pady=4)

    def auto_layout(self):
        mon = vision.get_monitor()
        W, H = mon["width"], mon["height"]

        def box(x, y, w, h):
            return [mon["left"] + int(x / 1919 * W), mon["top"] + int(y / 1008 * H),
                    int(w / 1919 * W), int(h / 1008 * H)]

        cfg["hp_me"] = box(870, 770, 190, 60)
        cfg["hp_o"] = [box(150, 480, 230, 190), box(770, 265, 120, 70), box(1320, 320, 170, 130)]
        save_cfg()
        messagebox.showinfo("Успех", "Автоматические координаты для HP выставлены.")

    def pick_roi(self, key, idx=None):
        self._cal_hide()
        r = select_region_ui(self)
        self._cal_show()
        if not r:
            return
        if idx is None:
            cfg[key] = list(r[0])
        else:
            cfg[key][idx] = list(r[0])
        save_cfg()
        messagebox.showinfo("Успех", "Зона успешно обновлена.")

    def cut_template(self):
        try:
            name = self.tpl.get()
        except Exception:
            return
        target_name = next((k for k, v in RU.items() if v == name), None)
        if not target_name:
            return
        self._cal_hide()
        r = select_region_ui(self)
        self._cal_show()
        if r:
            cv2.imwrite(os.path.join(vision.TPL_DIR, target_name + ".png"), r[1])
            messagebox.showinfo("Успех", f"Шаблон для [{name}] сохранен.")

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
            if self.auto.get() and self.winfo_viewable():
                self.auto_read()
        except Exception as e:
            self.status.set(f"Ошибка парсинга: {e}")
        self.after(700, self.tick)

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
                if ((L, B) == self.pend_track and (L, B) != self.last_shell
                        and L + B < self.start_total):
                    self.live.set(L)
                    self.blank.set(B)
                    self.spent = max(0, self.start_total - (L + B))
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
            except (ValueError, IndexError):
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
            "spent": self.spent,
        }
        self.advice.configure(text=strategy.compute_advice(game_state))


if __name__ == "__main__":
    app = App()
    app.mainloop()