import tkinter as tk
from tkinter import ttk, filedialog
import re
import os
import time
import threading

from cart_bot.stores import STORES
from cart_bot.state import BotState
from cart_bot.config import ConfigManager
from cart_bot import bot_engine

# --- Colors ---
BG = "#111111"
BG2 = "#1a1a1a"
BG3 = "#222222"
FG = "#ffffff"
FG2 = "#999999"
ACCENT = "#0071dc"
RED = "#d32f2f"
GREEN = "#4CAF50"


class CartBotApp:
    def __init__(self):
        self.state = BotState()
        self.config_mgr = ConfigManager()

        self.profile_labels = []
        self.profile_bars = []
        self.attempt_labels = []
        self.profile_url_labels = []
        self.profile_detail_labels = []
        self.profile_rows = []

        self._build_ui()
        self._load_saved_config()
        self.build_profile_rows()

    def run(self):
        self.window.mainloop()

    # =========================================================
    # UI Construction
    # =========================================================
    def _build_ui(self):
        self.window = tk.Tk()
        self.window.title("Cart Bot")
        self.window.geometry("640x560")
        self.window.resizable(False, False)
        self.window.config(bg=BG)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=BG3, background=BG3,
                        foreground=FG, arrowcolor=FG, borderwidth=0)

        main = tk.Frame(self.window, bg=BG)
        main.pack(fill="both", expand=True, padx=20, pady=(14, 10))
        self.main_frame = main

        self._build_config_section(main)
        self._section_sep(main)
        self._build_url_section(main)
        self._section_sep(main)
        self._build_controls(main)
        self._section_sep(main)
        self._build_status_section(main)
        self._build_legend(main)

    def _section_label(self, parent, text):
        lbl = tk.Label(parent, text=text, font=("Segoe UI", 9, "bold"),
                       bg=BG, fg=ACCENT, anchor="w")
        lbl.pack(fill="x", pady=(0, 4))
        return lbl

    def _section_sep(self, parent):
        tk.Frame(parent, bg="#2a2a2a", height=1).pack(fill="x", pady=(8, 8))

    # --- Config Section ---
    def _build_config_section(self, parent):
        self._section_label(parent, "CONFIGURATION")

        config_frame = tk.Frame(parent, bg=BG2, highlightbackground="#2a2a2a",
                                highlightthickness=1)
        config_frame.pack(fill="x")

        config_inner = tk.Frame(config_frame, bg=BG2)
        config_inner.pack(fill="x", padx=12, pady=10)

        # Row 1: Store + Profiles
        row1 = tk.Frame(config_inner, bg=BG2)
        row1.pack(fill="x", pady=(0, 6))

        tk.Label(row1, text="Store", bg=BG2, fg=FG2,
                 font=("Segoe UI", 9), width=8, anchor="w").pack(side="left")
        self.store_var = tk.StringVar(value="Target")
        self.store_dropdown = ttk.Combobox(row1, textvariable=self.store_var,
                                           values=list(STORES.keys()), state="readonly",
                                           font=("Consolas", 9), width=10)
        self.store_dropdown.pack(side="left", padx=(0, 24))

        tk.Label(row1, text="Profiles", bg=BG2, fg=FG2,
                 font=("Segoe UI", 9)).pack(side="left")
        self.profiles_var = tk.StringVar(value="5")
        self.profiles_dropdown = ttk.Combobox(row1, textvariable=self.profiles_var,
                                              values=[str(i) for i in range(1, 21)], state="readonly",
                                              font=("Consolas", 9), width=4)
        self.profiles_dropdown.pack(side="left", padx=(6, 0))
        self.profiles_dropdown.bind("<<ComboboxSelected>>", lambda e: self.build_profile_rows())

        # Row 2: Email + Password
        row2 = tk.Frame(config_inner, bg=BG2)
        row2.pack(fill="x", pady=(0, 6))

        tk.Label(row2, text="Email", bg=BG2, fg=FG2,
                 font=("Segoe UI", 9), width=8, anchor="w").pack(side="left")
        self.email_entry = tk.Entry(row2, width=28, font=("Consolas", 9), bg=BG3,
                                    fg=FG, insertbackground=FG, relief="flat", bd=0)
        self.email_entry.pack(side="left", ipady=4, padx=(0, 16))

        tk.Label(row2, text="Pass", bg=BG2, fg=FG2,
                 font=("Segoe UI", 9)).pack(side="left")
        self.password_entry = tk.Entry(row2, width=18, font=("Consolas", 9), bg=BG3,
                                       fg=FG, insertbackground=FG, relief="flat", bd=0, show="*")
        self.password_entry.pack(side="left", ipady=4, padx=(6, 0))

        # Row 3: Proxy
        row3 = tk.Frame(config_inner, bg=BG2)
        row3.pack(fill="x")

        tk.Label(row3, text="Proxies", bg=BG2, fg="#555555",
                 font=("Segoe UI", 8), width=9, anchor="w").pack(side="left")
        self.proxy_path_var = tk.StringVar(value="")
        proxy_entry = tk.Entry(row3, textvariable=self.proxy_path_var, width=36,
                               font=("Consolas", 8), bg=BG3, fg="#555555",
                               insertbackground=FG, relief="flat", bd=0)
        proxy_entry.pack(side="left", ipady=3, padx=(0, 4))

        browse_btn = tk.Button(row3, text="...", command=self._browse_proxy_file,
                               font=("Consolas", 8), bg=BG3, fg=FG2,
                               activebackground="#444444", relief="flat", cursor="hand2",
                               padx=6, pady=1)
        browse_btn.pack(side="left")

        tk.Label(row3, text="optional", bg=BG2, fg="#333333",
                 font=("Segoe UI", 7)).pack(side="left", padx=(6, 0))

        # Login buttons row
        login_row = tk.Frame(config_inner, bg=BG2)
        login_row.pack(fill="x", pady=(8, 0))

        self.setup_button = tk.Button(
            login_row, text="SETUP PROFILES",
            command=lambda: self.next_profile() if self.state.setup_index > 0 else self.setup_profiles(),
            font=("Segoe UI", 9, "bold"), bg="#444444", fg=FG,
            activebackground="#555555", relief="flat", cursor="hand2",
            padx=14, pady=4)
        self.setup_button.pack(side="left", padx=(0, 8))

        self.login_button = tk.Button(login_row, text="OPEN ALL AT ONCE", command=self.login_all,
                                      font=("Segoe UI", 8), bg="#333333", fg=FG2,
                                      activebackground="#444444", relief="flat", cursor="hand2",
                                      padx=10, pady=3)
        self.login_button.pack(side="left")

        tk.Label(login_row, text="log in manually — cookies persist", bg=BG2, fg="#444444",
                 font=("Segoe UI", 7)).pack(side="left", padx=(10, 0))

    # --- URL Section ---
    def _build_url_section(self, parent):
        self._section_label(parent, "PRODUCT URLs")

        # Saved library row
        library_row = tk.Frame(parent, bg=BG)
        library_row.pack(fill="x", pady=(0, 4))

        tk.Label(library_row, text="Saved", bg=BG, fg=FG2,
                 font=("Segoe UI", 9), anchor="w").pack(side="left")

        self.library_var = tk.StringVar(value="")
        self.library_dropdown = ttk.Combobox(library_row, textvariable=self.library_var,
                                             state="readonly", font=("Consolas", 9), width=28)
        self.library_dropdown.pack(side="left", padx=(6, 6))

        load_btn = tk.Button(library_row, text="LOAD", command=self._load_from_library,
                             font=("Segoe UI", 8, "bold"), bg=ACCENT, fg=FG,
                             activebackground="#005bb5", relief="flat", cursor="hand2",
                             padx=8, pady=2)
        load_btn.pack(side="left", padx=(0, 4))

        del_lib_btn = tk.Button(library_row, text="DELETE", command=self._delete_from_library,
                                font=("Segoe UI", 8), bg="#333333", fg="#888888",
                                activebackground=RED, activeforeground=FG,
                                relief="flat", cursor="hand2", padx=6, pady=2)
        del_lib_btn.pack(side="left")

        # URL hint + text box
        url_hint = tk.Label(parent, text="one per line  |  use '3x URL' to dedicate multiple profiles  |  extras round-robin",
                            bg=BG, fg="#444444", font=("Segoe UI", 7), anchor="w")
        url_hint.pack(fill="x")

        self.url_text = tk.Text(parent, height=3, font=("Consolas", 9), bg=BG2,
                                fg=FG, insertbackground=FG, relief="flat", bd=0,
                                wrap="none", padx=8, pady=6, highlightbackground="#2a2a2a",
                                highlightthickness=1)
        self.url_text.pack(fill="x", pady=(4, 0))

        # Save row
        save_row = tk.Frame(parent, bg=BG)
        save_row.pack(fill="x", pady=(4, 0))

        tk.Label(save_row, text="Save as", bg=BG, fg=FG2,
                 font=("Segoe UI", 8)).pack(side="left")

        self.save_name_var = tk.StringVar(value="")
        save_name_entry = tk.Entry(save_row, textvariable=self.save_name_var, width=24,
                                   font=("Consolas", 9), bg=BG3, fg=FG,
                                   insertbackground=FG, relief="flat", bd=0)
        save_name_entry.pack(side="left", ipady=3, padx=(6, 6))

        save_url_btn = tk.Button(save_row, text="SAVE", command=self._save_current_url,
                                 font=("Segoe UI", 8, "bold"), bg=GREEN, fg=FG,
                                 activebackground="#388E3C", relief="flat", cursor="hand2",
                                 padx=10, pady=2)
        save_url_btn.pack(side="left")

        tk.Label(save_row, text="persists across restarts", bg=BG, fg="#333333",
                 font=("Segoe UI", 7)).pack(side="left", padx=(8, 0))

        self._refresh_library()

    # --- Controls ---
    def _build_controls(self, parent):
        btn_frame = tk.Frame(parent, bg=BG)
        btn_frame.pack(fill="x")

        self.start_button = tk.Button(btn_frame, text="  START BOT  ", command=self.start_bot,
                                      font=("Segoe UI", 12, "bold"), bg=ACCENT, fg=FG,
                                      activebackground="#005bb5", relief="flat", cursor="hand2",
                                      padx=24, pady=6)
        self.start_button.pack(side="left", padx=(0, 10))

        self.pause_button = tk.Button(btn_frame, text="  PAUSE  ", command=self.toggle_pause,
                                      font=("Segoe UI", 12, "bold"), bg="#FF9800", fg=FG,
                                      activebackground="#E68900", relief="flat", cursor="hand2",
                                      padx=20, pady=6)
        self.pause_button.pack(side="left", padx=(0, 10))

        kill_button = tk.Button(btn_frame, text="  KILL ALL  ", command=self.kill_all,
                                font=("Segoe UI", 12, "bold"), bg=RED, fg=FG,
                                activebackground="#b71c1c", relief="flat", cursor="hand2",
                                padx=24, pady=6)
        kill_button.pack(side="left")

    # --- Status Section ---
    def _build_status_section(self, parent):
        status_header = tk.Frame(parent, bg=BG)
        status_header.pack(fill="x", pady=(0, 4))
        self._section_label(status_header, "LIVE STATUS")

        col_header = tk.Frame(parent, bg=BG)
        col_header.pack(fill="x")
        tk.Label(col_header, text="#", font=("Consolas", 7), bg=BG, fg="#333333",
                 width=3, anchor="w").pack(side="left")
        tk.Label(col_header, text="PROGRESS", font=("Consolas", 7), bg=BG, fg="#333333",
                 width=18, anchor="w").pack(side="left", padx=(2, 0))
        tk.Label(col_header, text="TRIES", font=("Consolas", 7), bg=BG, fg="#333333",
                 width=5).pack(side="left")
        tk.Label(col_header, text="STATUS", font=("Consolas", 7), bg=BG, fg="#333333",
                 width=11, anchor="w").pack(side="left")
        tk.Label(col_header, text="DETAIL", font=("Consolas", 7), bg=BG, fg="#333333",
                 width=14, anchor="w").pack(side="left")
        tk.Label(col_header, text="URL", font=("Consolas", 7), bg=BG, fg="#333333",
                 anchor="w").pack(side="left", fill="x", expand=True)

        self.status_frame = tk.Frame(parent, bg=BG)
        self.status_frame.pack(fill="x")

    # --- Legend ---
    def _build_legend(self, parent):
        legend_frame = tk.Frame(parent, bg=BG)
        legend_frame.pack(side="bottom", fill="x", pady=(6, 0))

        for color, text in [("#81C784", "LOGGED IN"), ("#2196F3", "LOADED"),
                            ("#FF9800", "WAITING"), ("#FFEB3B", "CLICKING"),
                            ("#FFC107", "VERIFYING"), ("#4CAF50", "IN CART"),
                            ("#00E676", "CHECKOUT")]:
            tk.Frame(legend_frame, bg=color, width=6, height=6).pack(side="left", padx=(8, 2))
            tk.Label(legend_frame, text=text, font=("Consolas", 7),
                     bg=BG, fg=color).pack(side="left")

    # =========================================================
    # Helpers
    # =========================================================
    def get_num_profiles(self):
        return int(self.profiles_var.get())

    def get_store(self):
        return self.store_var.get()

    def get_selectors(self):
        return STORES[self.get_store()]

    def get_urls(self):
        raw = self.url_text.get("1.0", "end").strip()
        result = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.match(r'^(\d+)\s*[xX]\s+(.+)$', line)
            if m:
                count = int(m.group(1))
                url = m.group(2).strip()
                result.extend([url] * count)
            else:
                result.append(line)
        return result

    def get_proxies(self):
        path = self.proxy_path_var.get().strip()
        if not path or not os.path.exists(path):
            return []
        with open(path, "r") as f:
            return [line.strip() for line in f if line.strip()]

    def save_config(self):
        data = {
            "email": self.email_entry.get(),
            "password": self.password_entry.get(),
            "urls": self.url_text.get("1.0", "end").strip(),
            "store": self.get_store(),
            "profiles": self.get_num_profiles(),
            "proxy_file": self.proxy_path_var.get(),
        }
        self.config_mgr.save(data)

    def _load_saved_config(self):
        config = self.config_mgr.load()
        self.email_entry.insert(0, config.get("email", ""))
        self.password_entry.insert(0, config.get("password", ""))
        self.url_text.insert("1.0", config.get("urls", ""))
        self.store_var.set(config.get("store", "Target"))
        self.profiles_var.set(str(config.get("profiles", 5)))
        self.proxy_path_var.set(config.get("proxy_file", ""))

    def _browse_proxy_file(self):
        path = filedialog.askopenfilename(
            title="Select Proxy List",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if path:
            self.proxy_path_var.set(path)

    # =========================================================
    # Profile Rows
    # =========================================================
    def build_profile_rows(self):
        for row in self.profile_rows:
            row.destroy()
        self.profile_labels.clear()
        self.profile_bars.clear()
        self.attempt_labels.clear()
        self.profile_url_labels.clear()
        self.profile_detail_labels.clear()
        self.profile_rows.clear()

        num = self.get_num_profiles()

        for i in range(num):
            row = tk.Frame(self.status_frame, bg=BG)
            row.pack(fill="x", pady=1)
            self.profile_rows.append(row)

            tk.Label(row, text=f"{i+1:>2}", font=("Consolas", 8, "bold"),
                     bg=BG, fg=FG2, width=3).pack(side="left")

            bar_bg = tk.Frame(row, bg=BG3, height=16, width=140)
            bar_bg.pack(side="left", padx=(2, 4))
            bar_bg.pack_propagate(False)

            bar = tk.Frame(bar_bg, bg=BG3, height=16, width=0)
            bar.place(x=0, y=0)
            self.profile_bars.append(bar)

            a_label = tk.Label(row, text="", font=("Consolas", 7),
                               bg=BG, fg="#555555", width=5)
            a_label.pack(side="left")
            self.attempt_labels.append(a_label)

            s_label = tk.Label(row, text="READY", font=("Consolas", 7, "bold"),
                               bg=BG, fg="#333333", width=11, anchor="w")
            s_label.pack(side="left")
            self.profile_labels.append(s_label)

            d_label = tk.Label(row, text="", font=("Consolas", 7),
                               bg=BG, fg="#444444", width=14, anchor="w")
            d_label.pack(side="left")
            self.profile_detail_labels.append(d_label)

            u_label = tk.Label(row, text="", font=("Consolas", 7),
                               bg=BG, fg="#333333", anchor="w")
            u_label.pack(side="left", fill="x", expand=True)
            self.profile_url_labels.append(u_label)

        self._resize_window()

    def _resize_window(self):
        num = self.get_num_profiles()
        base = 530
        per_row = 20
        height = base + (num * per_row)
        self.window.geometry(f"640x{height}")

    # =========================================================
    # Status Callbacks (passed to bot_engine)
    # =========================================================
    def set_profile_status(self, profile_num, status, detail=""):
        idx = profile_num - 1
        if idx >= len(self.profile_labels):
            return

        label = self.profile_labels[idx]
        bar = self.profile_bars[idx]

        statuses = {
            "LAUNCHING":  ("#555555", 20),
            "LOGGING IN": ("#29B6F6", 35),
            "LOGGED IN":  ("#81C784", 50),
            "LOADED":     ("#2196F3", 50),
            "CAPTCHA":    ("#AB47BC", 65),
            "WAITING":    ("#FF9800", 80),
            "TRYING":     ("#FF9800", 80),
            "CLICKING":   ("#FFEB3B", 95),
            "VERIFYING":  ("#FFC107", 110),
            "IN CART":    ("#4CAF50", 125),
            "CHECKOUT":   ("#00E676", 140),
            "ERROR":      ("#F44336", 20),
        }

        if status == "STOPPED":
            bar.config(bg="#555555", width=bar.winfo_width())
            label.config(text="STOPPED", fg="#555555")
        elif status in statuses:
            color, width = statuses[status]
            bar.config(bg=color, width=width)
            label.config(text=status, fg=color)

        if idx < len(self.profile_detail_labels):
            detail_color = "#666666"
            if status == "WAITING":
                detail_color = "#FF9800"
            elif status == "IN CART":
                detail_color = GREEN
            elif status == "ERROR":
                detail_color = "#F44336"
            self.profile_detail_labels[idx].config(text=detail[:16], fg=detail_color)

        self.window.update_idletasks()

    def set_attempt_count(self, profile_num, count):
        idx = profile_num - 1
        if idx >= len(self.attempt_labels):
            return
        self.attempt_labels[idx].config(text=f"#{count}")
        self.window.update_idletasks()

    def set_profile_url(self, profile_num, url):
        idx = profile_num - 1
        if idx >= len(self.profile_url_labels):
            return
        short = url.split("/")[-1][:20] if "/" in url else url[:20]
        self.profile_url_labels[idx].config(text=short, fg="#444444")
        self.window.update_idletasks()

    # =========================================================
    # Library
    # =========================================================
    def _refresh_library(self):
        saved = self.config_mgr.get_saved_urls()
        names = list(saved.keys())
        self.library_dropdown["values"] = names
        if names and not self.library_var.get():
            self.library_var.set(names[0])

    def _load_from_library(self):
        name = self.library_var.get()
        if not name:
            return
        saved = self.config_mgr.get_saved_urls()
        if name in saved:
            bot_running = not self.state.stop_all and any(
                i < len(self.profile_labels) and self.profile_labels[i].cget("text") in ("WAITING", "TRYING", "CLICKING", "LOADED")
                for i in range(self.get_num_profiles())
            )
            if bot_running:
                self.soft_stop()
            self.url_text.delete("1.0", "end")
            self.url_text.insert("1.0", saved[name])
            print(f"Loaded '{name}' — hit START BOT when ready")

    def _delete_from_library(self):
        name = self.library_var.get()
        if not name:
            return
        self.config_mgr.delete_url_from_library(name)
        self.library_var.set("")
        self._refresh_library()

    def _save_current_url(self):
        name = self.save_name_var.get().strip()
        urls = self.url_text.get("1.0", "end").strip()
        if not name:
            print("Save failed: enter a product name first")
            return
        if not urls:
            print("Save failed: paste a URL in the box first")
            return
        self.config_mgr.save_url_to_library(name, urls)
        self.save_name_var.set("")
        self._refresh_library()
        self.library_var.set(name)

    # =========================================================
    # Setup / Login
    # =========================================================
    def setup_profiles(self):
        self.state.setup_index = 0
        self.save_config()
        self._open_next_setup_profile()

    def _open_next_setup_profile(self):
        num = self.get_num_profiles()

        if self.state.setup_index >= num:
            self.setup_button.config(text="SETUP PROFILES", bg="#444444")
            print(f"All {num} profiles set up! Cookies are saved. Use START BOT.")
            return

        profile_num = self.state.setup_index + 1
        proxies = self.get_proxies()
        proxy = proxies[self.state.setup_index] if self.state.setup_index < len(proxies) else None
        sel = self.get_selectors()

        self.set_profile_status(profile_num, "LAUNCHING")
        driver = bot_engine.make_driver(profile_num, proxy)
        self.state.drivers[profile_num] = driver
        driver.get(sel["login_url"])
        self.set_profile_status(profile_num, "LOGGING IN", "log in manually")

        self.setup_button.config(text=f"NEXT PROFILE ({profile_num}/{num})", bg=GREEN)
        self.state.setup_index += 1
        print(f"Profile {profile_num}: Browser open — log in manually, then click NEXT PROFILE")

    def next_profile(self):
        num = self.get_num_profiles()
        done_num = self.state.setup_index
        if done_num > 0 and done_num <= num:
            try:
                if done_num in self.state.drivers:
                    self.state.drivers[done_num].quit()
                    del self.state.drivers[done_num]
            except Exception:
                pass
            time.sleep(1)
            self.set_profile_status(done_num, "LOGGED IN", "session saved")
        self._open_next_setup_profile()

    def login_all(self):
        self.save_config()
        sel = self.get_selectors()
        proxies = self.get_proxies()
        num = self.get_num_profiles()

        for i in range(num):
            proxy = proxies[i] if i < len(proxies) else None
            self.set_profile_status(i + 1, "LAUNCHING")
            driver = bot_engine.make_driver(i + 1, proxy)
            self.state.drivers[i + 1] = driver
            driver.get(sel["login_url"])
            self.set_profile_status(i + 1, "LOGGING IN", "log in manually")
            print(f"Profile {i + 1}: Browser open — log in manually")

        self.login_button.config(state="disabled")

    # =========================================================
    # Bot Control
    # =========================================================
    def soft_stop(self):
        self.state.stop_all = True
        self.state.paused = False
        time.sleep(0.3)
        num = self.get_num_profiles()
        for i in range(num):
            if i < len(self.profile_labels):
                cur = self.profile_labels[i].cget("text")
                if cur in ("WAITING", "TRYING", "CLICKING", "VERIFYING", "LOADED"):
                    self.set_profile_status(i + 1, "STOPPED")
                    if i < len(self.attempt_labels):
                        self.attempt_labels[i].config(text="")
        self.start_button.config(state="normal")
        self.pause_button.config(text="  PAUSE  ", bg="#FF9800")

    def start_bot(self):
        # If bot is already running, stop it first then relaunch
        if not self.state.stop_all and any(
            i < len(self.profile_labels) and self.profile_labels[i].cget("text") in ("WAITING", "TRYING", "CLICKING", "LOADED")
            for i in range(self.get_num_profiles())
        ):
            self.soft_stop()
            time.sleep(0.5)

        self.state.stop_all = False
        self.state.paused = False

        urls = self.get_urls()
        if not urls:
            return

        self.save_config()
        self.start_button.config(state="disabled")
        self.pause_button.config(text="  PAUSE  ", bg="#FF9800")

        num = self.get_num_profiles()
        proxies = self.get_proxies()
        sel = self.get_selectors()

        url_assignments = []
        for i in range(num):
            if i < len(urls):
                url_assignments.append(urls[i])
            else:
                url_assignments.append(urls[i % len(urls)])

        print(f"--- Profile URL Assignments ({num} profiles) ---")
        for i, u in enumerate(url_assignments):
            short = u.split("/")[-1][:40] if "/" in u else u[:40]
            print(f"  Profile {i+1}: {short}")

        for i in range(num):
            proxy = proxies[i] if i < len(proxies) else None
            self.set_profile_status(i + 1, "LAUNCHING")
            self.set_profile_url(i + 1, url_assignments[i])
            thread = threading.Thread(
                target=bot_engine.run_bot,
                args=(url_assignments[i], i + 1, num, proxy, self.state, sel,
                      self.set_profile_status, self.set_attempt_count, self.set_profile_url),
                daemon=True
            )
            thread.start()

    def toggle_pause(self):
        self.state.paused = not self.state.paused
        if self.state.paused:
            self.pause_button.config(text="  RESUME  ", bg="#FF9800")
            num = self.get_num_profiles()
            for i in range(num):
                if i < len(self.profile_labels) and self.profile_labels[i].cget("text") in ("WAITING", "TRYING"):
                    self.set_profile_status(i + 1, "WAITING", "PAUSED")
            print("Bot PAUSED — browsers stay open, refresh stopped")
        else:
            self.pause_button.config(text="  PAUSE  ", bg="#FF9800")
            print("Bot RESUMED — refreshing again")

    def kill_all(self):
        self.state.stop_all = True
        self.state.paused = False

        for pnum, driver in list(self.state.drivers.items()):
            try:
                driver.quit()
            except Exception:
                pass

        self.state.drivers.clear()
        num = self.get_num_profiles()

        for i in range(num):
            self.set_profile_status(i + 1, "STOPPED")
            if i < len(self.attempt_labels):
                self.attempt_labels[i].config(text="")

        self.state.setup_index = 0
        self.start_button.config(state="normal")
        self.login_button.config(state="normal")
        self.setup_button.config(text="SETUP PROFILES", bg="#444444")
        self.pause_button.config(text="  PAUSE  ", bg="#FF9800")
